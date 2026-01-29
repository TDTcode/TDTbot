import asyncio
import datetime
import logging
import time

import discord  # type: ignore

from . import git_manage
from .helpers import localize
from .param import roles

logger = logging.getLogger("discord." + __name__)


async def split_send(channel, message, deliminator="\n", n=2000, style=""):
    """Split a message into chunks and send them in chunks."""
    out = []
    if not message:
        return
    if type(message) not in [tuple, list]:
        message = message.split(deliminator)
    msg = message.pop(0)
    while message:
        tmp = message.pop(0)
        if len(msg + deliminator + tmp + style * 2) >= n:
            out.append(await channel.send(style + msg + style))
            msg = tmp
        else:
            msg += deliminator + tmp
    out.append(await channel.send(style + msg + style))
    return out


async def sleep(dt):
    now = datetime.datetime.now()
    try:
        await asyncio.sleep(dt)
    except discord.HTTPException:
        dt -= (datetime.datetime.now() - now).total_seconds()
        time.sleep(dt)
    return


async def admin_check(ctx=None, bot=None, author=None, guild=None):
    if author is None:
        if ctx is None:
            raise ValueError("Either ctx or author must be specified")
        author = ctx.author
    if guild is None:
        guild = ctx.guild
    logger.debug("admin_check", author, getattr(author, "top_role", "NO_ROLE"))
    try:
        if author.top_role.id in [roles.admin, roles.devoted]:
            return True
    except AttributeError:
        pass
    if guild is not None:
        if guild.owner == author:
            return True
    if bot is not None:
        if await bot.is_owner(author):
            return True
    # await ctx.send('Must be an admin to issue this command.')
    return False


async def wait_until(dt):
    """sleep until the specified datetime (assumes UTC)"""
    while True:
        now = localize(datetime.datetime.utcnow())
        remaining = (localize(dt) - now).total_seconds()
        if remaining < 86400:
            break
        # asyncio.sleep doesn't like long sleeps, so don't sleep more than a day at a time
        await asyncio.sleep(86400)
    await asyncio.sleep(remaining)


async def git_log(channel, *args):
    """Print git log to discord chat."""
    await split_send(channel, git_manage.git_log_items(), style="```")


async def parse_payload(payload, bot, *fields):
    fields = list(fields)
    if not fields:
        fields = ["guild", "member"]
    reqiers = {"member": ["guild"], "messsage": ["channel"]}

    for i in fields:
        add = reqiers.get(i, [])
        for j in add:
            if j not in fields:
                fields.append(j)

    out = dict()
    if "guild" in fields:
        try:
            out["guild"] = [g for g in bot.guilds if g.id == payload.guild_id][0]
        except IndexError:
            out["guild"] = await bot.fetch_guild(payload.guild_id)
    if "member" in fields:
        member = payload.member
        if not member:
            member = await bot.get_or_fetch_user(payload.user_id, out["guild"])
        out["member"] = member
    if "channel" in fields:
        channel = bot.find_channel(payload.channel_id)
        if channel is None:
            channel = await bot.fetch_channel(payload.channel_id)
        out["channel"] = channel
    if "message" in fields:
        out["message"] = await out["channel"].fetch_message(payload.message_id)
    return out
