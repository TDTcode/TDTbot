import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import asyncio
from ..param import roles
from ..helpers import find_role
from ..async_helpers import admin_check
from ..version import usingV2
import logging
import re


logger = logging.getLogger('discord.' + __name__)
_startup_debugging = True
spam_msg = "I have parsed this message as spam. Please don't spam. This is a bot and I don't like spam. ({:})"


class SpamFilter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._init = False
        self._tdt = None
        self._com = None
        self._admin = None
        self._debug = _startup_debugging
        self._log_channel = None

    async def _async_init(self):
        if self._init:
            return
        _ = self.tdt
        _ = self.com
        _ = self.admin
        self._log_channel = self.bot.find_channel("admin_log")
        self._init = True

    @property
    def log_channel(self):
        if self._log_channel is None:
            self._log_channel = self.bot.find_channel("admin_log")
        return self._log_channel

    @property
    def tdt(self):
        if self._tdt is None:
            self._tdt = self.bot.tdt()
        return self._tdt

    @property
    def com(self):
        if self._com is None:
            self._com = find_role(self.tdt, roles.community)
        return self._com

    @property
    def admin(self):
        if self._admin is None:
            self._admin = find_role(self.tdt, roles.admin)
        return self._admin

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self._async_init()

    async def reply_to_spam(self, message):
        """Reply to a spam post"""
        await message.channel.send(spam_msg.format(self.admin.mention), reference=message)

    async def log_spam(self, message):
        msg = "Spam message detected:\n{0.content}\n{0.link}"
        return await self.log_channel.send(msg.format(message))

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages for spam posts"""
        # ignore all messages from our bot
        if message.author == self.bot.user:
            return
        if not self._init:
            await self._async_init()
        if not isinstance(message.author, discord.Member):
            message.author = await self.bot.get_or_fetch_user(message.author.id)
        if not re.search(r'https://dis[discorle]{3,6}(.gift|[.]?com)+/[\w]+( |$)', message.content):
            return
        low_role = False
        if isinstance(message.author, discord.Member):
            if message.author.top_role <= self.com:
                low_role = True
        if self._debug:
            return self.log_spam(message)
        if low_role:
            try:
                await message.delete()
            except discord.Forbidden:
                if not isinstance(message.channel, discord.DMChannel):
                    try:
                        await self.reply_to_spam(message)
                    except discord.Forbidden:
                        await self.log_spam(message)
        else:
            await self.reply_to_spam(message)

    @commands.group()
    @commands.check(admin_check)
    async def spam_debug(self, ctx):
        """Base function for spam_debug sub commands"""
        if ctx.invoked_subcommand is None:
            msg = 'Spam debugging is set to {}. Use `tdt$spam_debug [on/off]` to change value.'
            await ctx.send(msg.format(self._debug))

    @spam_debug.command()
    @commands.check(admin_check)
    async def on(self, ctx):
        """Turn spam debugging on."""
        self._debug = True
        await ctx.send("Spam filter is now in debugging mode.")

    @spam_debug.command()
    @commands.check(admin_check)
    async def off(self, ctx):
        """Turn spam debugging off."""
        self._debug = False
        await ctx.send("Spam filter is NOT in debugging mode.")


if usingV2:
    async def setup(bot):
        cog = SpamFilter(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(SpamFilter(bot))
