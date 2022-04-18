"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some important utility functions.
"""

from __future__ import annotations
import asyncio
from typing import Optional, Sequence, Union


import discord
import pygame
import snakecore

from pgbot import common, db


async def get_channel_feature(
    name: str, channel: common.Channel, defaultret: bool = False
):
    """
    Get the channel feature. Returns True if the feature name is disabled on
    that channel, False otherwise. Also handles category channel
    """
    async with db.DiscordDB("feature") as db_obj:
        db_dict: dict[int, bool] = db_obj.get({}).get(name, {})

    if channel.id in db_dict:
        return db_dict[channel.id]

    if isinstance(channel, discord.TextChannel):
        if channel.category_id is None:
            return defaultret
        return db_dict.get(channel.category_id, defaultret)

    return defaultret


def color_to_rgb_int(col: pygame.Color, alpha: bool = False):
    """
    Get integer RGB representation of pygame color object.
    """
    return (
        col.r << 32 | col.g << 16 | col.b << 8 | col.a
        if alpha
        else col.r << 16 | col.g << 8 | col.b
    )


def split_wc_scores(scores: dict[int, int]):
    """
    Split wc scoreboard into different categories
    """
    scores_list = [(score, f"<@!{mem}>") for mem, score in scores.items()]
    scores_list.sort(reverse=True)

    for title, category_score in common.WC_SCORING:
        category_list = list(filter(lambda x: x[0] >= category_score, scores_list))
        if not category_list:
            continue

        desc = ">>> " + "\n".join(
            (f"`{score}` **•** {mem} :medal:" for score, mem in category_list)
        )

        yield title, desc, False
        scores_list = scores_list[len(category_list) :]


async def give_wc_roles(member: discord.Member, score: int):
    """
    Updates the WC roles of a member based on their latest total score
    """
    got_role: bool = False
    for min_score, role_id in common.ServerConstants.WC_ROLES:
        if score >= min_score and not got_role:
            # This is the role to give
            got_role = True
            if role_id not in map(lambda x: x.id, member.roles):
                await member.add_roles(
                    discord.Object(role_id),
                    reason="Automatic bot action, adds WC event roles",
                )

        else:
            # any other event related role to be removed
            if role_id in map(lambda x: x.id, member.roles):
                await member.remove_roles(
                    discord.Object(role_id),
                    reason="Automatic bot action, removes older WC event roles",
                )


async def message_delete_reaction_listener(
    msg: discord.Message,
    invoker: Union[discord.Member, discord.User],
    emoji: Union[discord.Emoji, discord.PartialEmoji, str],
    role_whitelist: Sequence[int] = None,
    timeout: Optional[float] = None,
):
    """Allows for a message to be deleted using a specific reaction.
    If any HTTP-related exceptions are raised by `discord.py` within this function,
    it will fail silently.

    Args:
        msg (discord.Message): The message to use.
        invoker (Union[discord.Member, discord.User]): The member/user who can delete
          a message.
        emoji (Union[discord.Emoji, discord.PartialEmoji, str]): The emoji to
          listen for.
        role_whitelist (Sequence[int]): A sequence (that supports `__contains__`) of
          role IDs whose reactions can also be picked up by this function.
        timeout (Optional[float]): A timeout for waiting, before automatically
          removing any added reactions and returning silently.

    Raises:
        TypeError: Invalid argument types.
    """

    role_whitelist = role_whitelist or ()

    if not isinstance(emoji, (discord.Emoji, discord.PartialEmoji, str)):
        raise TypeError("invalid emoji given as input")

    try:
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            return

        check = None
        if isinstance(invoker, discord.Member):
            check = (
                lambda event: event.message_id == msg.id
                and (event.guild_id == getattr(msg.guild, "id", None))
                and (
                    event.user_id == invoker.id
                    or any(
                        role.id in role_whitelist
                        for role in getattr(event.member, "roles", ())[1:]
                    )
                )
                and snakecore.utils.is_emoji_equal(event.emoji, emoji)
            )
        elif isinstance(invoker, discord.User):
            check = (
                lambda event: event.message_id == msg.id
                and (event.guild_id == getattr(msg.guild, "id", None))
                and (event.user_id == invoker.id)
                and snakecore.utils.is_emoji_equal(event.emoji, emoji)
            )
        else:
            raise TypeError(
                f"argument 'invoker' expected discord.Member/.User, not {invoker.__class__.__name__}"
            )

        event: discord.RawReactionActionEvent = await common.bot.wait_for(
            "raw_reaction_add", check=check, timeout=timeout
        )

        try:
            await msg.delete()
        except discord.HTTPException:
            pass

    except (asyncio.TimeoutError, asyncio.CancelledError) as a:
        try:
            await msg.clear_reaction(emoji)
        except discord.HTTPException:
            pass

        if isinstance(a, asyncio.CancelledError):
            raise a
