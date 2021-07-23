"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some utility functions for pg!help command
"""

from __future__ import annotations

import re
import typing

import discord

from pgbot import common
from pgbot.utils import embed_utils


# regex for doc string
regex = re.compile(
    # If you add a new "section" to this regex dont forget the "|" at the end
    # Does not have to be in the same order in the docs as in here.
    r"(->type|"
    r"->signature|"
    r"->description|"
    r"->example command|"
    r"->extended description\n|"
    r"\Z)|(((?!->).|\n)*)"
)


def get_doc_from_func(func: typing.Callable):
    """
    Get the type, signature, description and other information from docstrings.

    Args:
        func (typing.Callable): The function to get formatted docs for

    Returns:
        Dict[str] or Dict[]: The type, signature and description of
        the string. An empty dict will be returned if the string begins
        with "->skip" or there was no information found
    """
    string = func.__doc__
    if not string:
        return {}

    string = string.strip()
    if string.startswith("->skip"):
        return {}

    finds = regex.findall(string.split("-----")[0])
    current_key = ""
    data = {}
    if finds:
        for find in finds:
            if find[0].startswith("->"):
                current_key = find[0][2:].strip()
                continue

            if not current_key:
                continue

            # remove useless whitespace
            value = re.sub("  +", "", find[1].strip())
            data[current_key] = value
            current_key = ""

    return data


async def send_help_message(
    original_msg: discord.Message,
    invoker: discord.Member,
    commands: tuple[str, ...],
    cmds_and_funcs: dict[str, typing.Callable],
    groups: dict[str, list],
    page: int = 0,
):
    """
    Edit original_msg to a help message. If command is supplied it will
    only show information about that specific command. Otherwise sends
    the general help embed.

    Args:
        original_msg: The message to edit
        invoker: The member who requested the help command
        commands: A tuple of command names passed by user for help.
        cmds_and_funcs: The name-function pairs to get the docstrings from
        groups: The name-list pairs of group commands
        page: The page of the embed, 0 by default
    """

    doc_fields = {}
    embeds = []

    if not commands:
        functions = {}
        for key, func in cmds_and_funcs.items():
            if hasattr(func, "groupname"):
                key = f"{func.groupname} {' '.join(func.subcmds)}"
            functions[key] = func

        for func in functions.values():
            data = get_doc_from_func(func)
            if not data:
                continue

            if not doc_fields.get(data["type"]):
                doc_fields[data["type"]] = ["", "", True]

            doc_fields[data["type"]][0] += f"{data['signature'][2:]}\n"
            doc_fields[data["type"]][1] += (
                f"`{data['signature']}`\n" f"{data['description']}\n\n"
            )

        doc_fields_cpy = doc_fields.copy()

        for doc_field_name in doc_fields:
            doc_field_list = doc_fields[doc_field_name]
            doc_field_list[1] = f"```\n{doc_field_list[0]}\n```\n\n{doc_field_list[1]}"
            doc_field_list[0] = f"__**{doc_field_name}**__"

        doc_fields = doc_fields_cpy

        embeds.append(
            discord.Embed(
                title=common.BOT_HELP_PROMPT["title"],
                description=common.BOT_HELP_PROMPT["description"],
                color=common.BOT_HELP_PROMPT["color"],
            )
        )
        for doc_field in list(doc_fields.values()):
            body = f"{doc_field[0]}\n\n{doc_field[1]}"
            embeds.append(
                embed_utils.create(
                    title=common.BOT_HELP_PROMPT["title"],
                    description=body,
                    color=common.BOT_HELP_PROMPT["color"],
                )
            )

    elif commands[0] in cmds_and_funcs:
        func_name = commands[0]
        funcs = groups[func_name] if func_name in groups else []
        funcs.insert(0, cmds_and_funcs[func_name])

        for func in funcs:
            if (
                commands[1:]
                and commands[1:] != getattr(func, "subcmds", ())[: len(commands[1:])]
            ):
                continue

            doc = get_doc_from_func(func)
            if not doc:
                # function found, but does not have help.
                return await embed_utils.replace(
                    original_msg,
                    title="Could not get docs",
                    description="Command has no documentation",
                    color=0xFF0000,
                )

            body = f"`{doc['signature']}`\n`Category: {doc['type']}`\n\n"

            desc = doc["description"]

            ext_desc = doc.get("extended description")
            if ext_desc:
                desc = f"> *{desc}*\n\n{ext_desc}"

            desc_list = desc.split(sep="+===+")

            body += f"**Description:**\n{desc_list[0]}"

            embed_fields = []

            example_cmd = doc.get("example command")
            if example_cmd:
                embed_fields.append(["Example command(s):", example_cmd, True])

            if len(desc_list) == 1:
                embeds.append(
                    embed_utils.create(
                        title=f"Help for `{func_name}`",
                        description=body,
                        color=common.BOT_HELP_PROMPT["color"],
                        fields=embed_fields,
                    )
                )
            else:
                embeds.append(
                    embed_utils.create(
                        title=f"Help for `{func_name}`",
                        description=body,
                        color=common.BOT_HELP_PROMPT["color"],
                    )
                )
                desc_list_len = len(desc_list)
                for i in range(1, desc_list_len):
                    embeds.append(
                        embed_utils.create(
                            title=f"Help for `{func_name}`",
                            description=desc_list[i],
                            color=common.BOT_HELP_PROMPT["color"],
                            fields=embed_fields if i == desc_list_len - 1 else (),
                        )
                    )

    if not embeds:
        return await embed_utils.replace(
            original_msg,
            title="Command not found",
            description="No such command exists",
            color=0xFF0000,
        )

    await embed_utils.PagedEmbed(
        original_msg, embeds, invoker, f"help {' '.join(commands)}", page
    ).mainloop()
