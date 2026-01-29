import asyncio
import datetime
import pytz
import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import logging
from .. import param
# from ..helpers import *
from ..async_helpers import admin_check, wait_until
from ..version import usingV2

logger = logging.getLogger('discord.' + __name__)

_mesome = param.users.mesome


class ChronTask:
    def __init__(self, cog, freq, offset, func, *args, context=True, **kwargs):
        self.cog = cog
        self.freq = freq.lower()
        if isinstance(offset, dict):
            offset = datetime.timedelta(**offset)
        self.offset = offset
        if isinstance(func, str):
            if '.' in func:
                cog, func = func.split('.')
                func = getattr(self.cog.bot.get_cog(cog), func)
            else:
                func = self.cog.bot.get_command(func)
        self.func = func
        self.args = list(args)
        self.kwargs = kwargs
        self.context = context
        self.tz = pytz.timezone(param.rc('timezone'))

    def enroll(self):
        self.cog.bot.loop.create_task(self.proc())

    async def proc(self):
        args = self.args[:]
        if self.context is True:
            self.context = await self.cog.manifest_context()
        if self.context:
            if not args:
                args.append(self.context)
            elif not isinstance(args[0], discord.Context):
                args.insert(0, self.context)
        dt = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if self.freq == 'monthly':
            next = dt.replace(month=dt.month + 1, day=1)
        elif self.freq == 'weekly':
            next = dt + datetime.timedelta(days=7-dt.weekday())
        elif self.freq == 'daily':
            next = dt + datetime.timedelta(days=1)
        else:
            raise ValueError('Invalid frequency')
        next = self.tz.localize(next + self.offset)
        next = next.astimezone(pytz.utc).replace(tzinfo=None)
        await wait_until(next)
        await self.func(args, **self.kwargs)
        await asyncio.sleep(2)
        self.enroll()


class Chron(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._init = False
        self._channel = param.rc('chron_channel')
        self.tasks = [
            ChronTask(self, 'monthly', dict(hours=9), self.list_supporters),
            ChronTask(self, 'weekly', dict(hours=9, days=6), 'aar'),
        ]

    @property
    def channel(self):
        """Return channel and fetch it if needed"""
        if hasattr(self._channel, 'id'):
            return self._channel
        channel = self.bot.find_channel(self._channel)
        if channel:
            self._channel = channel
            return channel

    async def cog_check(self, ctx):
        """Don't allow everyone to access this cog"""
        return await admin_check(ctx)

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self._async_init()

    async def _async_init(self):
        if self._init:
            return
        for task in self.tasks:
            task.enroll()
        self._init = True

    @commands.command()
    async def monthly_task(self, ctx):
        pass

    async def list_supporters(self):
        """List all supporters"""
        mesome = await self.bot.get_or_fetch_user(_mesome)
        msg = self.channel.send('{} Listing all supporters...'.format(mesome.mention))
        ctx = await self.bot.get_context(msg)
        func = await self.bot.get_command('list_supporters')
        await func(ctx)

    async def manifest_context(self, n=100):
        msg = None
        async for message in self.channel.history(limit=n):
            if message.author.id == self.bot.user.id:
                continue
            msg = message
            if await self.bot.is_owner(message.author):
                break
        if not msg:
            raise ValueError('No message found')
        return await self.bot.get_context(msg)


if usingV2:
    async def setup(bot):
        cog = Chron(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(Chron(bot))
