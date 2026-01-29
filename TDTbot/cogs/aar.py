import datetime
import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import logging
import pytz
from ..async_helpers import git_log
# from ..helpers import *
from .. import param
from ..version import usingV2

logger = logging.getLogger('discord.' + __name__)
_tz = pytz.timezone(param.rc('timezone'))
_day = datetime.timedelta(days=1)


class AAR(commands.Cog):
    """Cog designed to handel Stellar's AAR, cause he's lazy"""
    channel_id = param.channels.bounty_board

    def __init__(self, bot):
        self.bot = bot
        self._last_post = None
        self._channel = None

    @property
    def channel(self):
        if self._channel is None:
            self._channel = self.bot.find_channel(self.channel_id)
        return self._channel

    async def _aar(self, channel=None):
        channel = self.channel if channel is None else channel
        await channel.send("Stellar's AAR:")
        await git_log(channel)
        self._last_post = datetime.datetime.utcnow()

    @commands.command()
    async def aar(self, ctx):
        """Post Stellar's AAR"""
        await self._aar(ctx.channel)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages for Mesome asking for AARs"""
        # if not devoted_chat channel
        if message.channel.id != self.channel_id:
            return
        # if not Mesome, return
        try:
            if message.author != message.guild.owner:
                return
        except AttributeError:
            return
        if 'aar' not in message.content.lower():
            return
        # if we posted an AAR in the last day, return
        if self._last_post is not None:
            if datetime.datetime.utcnow() - self._last_post < _day:
                return
        # assign UTC timezone to message creation timestamp
        dt = pytz.utc.localize(message.created_at)
        # convert to server timezone
        dt = dt.astimezone(_tz)
        # if it is not sunday return
        if dt.today().weekday() != 6:
            return
        # Now it is time to print Stellar's AAR
        await self._aar()


if usingV2:
    async def setup(bot):
        cog = AAR(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(AAR(bot))
