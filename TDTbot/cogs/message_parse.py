import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import logging
from ..helpers import parse_message
from ..async_helpers import admin_check
from .. import param
from ..version import usingV2


logger = logging.getLogger('discord.' + __name__)


class MessageParse(commands.Cog):
    """Cog designed for debugging the bot"""
    def __init__(self, bot):
        self.bot = bot
        self._stfu = True

    async def _can_run(self, ctx):
        """Don't allow everyone to access this cog"""
        if ctx.channel != self.bot.find_channel(param.rc('log_channel')):
            return False
        a = ctx.author
        if a.roles[0].name in ['Admin', 'Devoted']:
            return True
        if await self.bot.is_owner(a):
            return True
        if ctx.guild.owner == a:
            return True
        return False

    async def cog_check(self, ctx):
        return await self._can_run(ctx)

    @commands.command(hidden=True)
    @commands.check(admin_check)
    async def stfu(self, ctx):
        """Silent this cog"""
        self._stfu = True

    @commands.Cog.listener()
    async def on_message(self, message):
        if self._stfu:
            return
        if message.author == self.bot.user:
            return
        if not await self._can_run(message):
            return
        # await message.channel.send(str(message))
        data = parse_message(message)
        for key in sorted(data.keys()):
            if data[key]:
                await message.channel.send(key + ":\n```" + str(data[key]) + '```')
                # print(key + ":\n```" + str(data[key]) + '```')


if usingV2:
    async def setup(bot):
        cog = MessageParse(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(MessageParse(bot))
