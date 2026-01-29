import os
import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import logging
from ..config import UserConfig
from .. import param
from ..version import usingV2
# from ..helpers import *
# from ..async_helpers import admin_check, split_send


logger = logging.getLogger('discord.' + __name__)
ff_fn = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]
ff_fn = os.path.join(ff_fn, 'config', 'fight_forever.dbm')


class FightForever(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = param.IntPermaDict(ff_fn)
        self._channel = None

    @commands.group()
    async def fight_forever(self, ctx):
        """Base function for git sub commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid git command passed...')

    @fight_forever.command()
    async def list(self, ctx):
        """Alias for git_pull"""
        await self.git_pull(ctx)

    def _get_config(self, user=None):
        """Get a user's config file"""
        if user is None:
            user = self.bot.user
        try:
            return self._configs[user.id]
        except KeyError:
            self._configs[user.id] = UserConfig(user)
            return self._configs[user.id]


if usingV2:
    async def setup(bot):
        return
        cog = FightForever(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        return
        bot.add_cog(FightForever(bot))
