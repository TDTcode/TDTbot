import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import asyncio
import datetime
import pytz
import logging
import os
from .. import param
from ..param import channels
from ..helpers import find_role
from ..async_helpers import admin_check, split_send
from ..version import usingV2


logger = logging.getLogger('discord.' + __name__)
_dbm = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]
_dbm = os.path.join(_dbm, 'config', 'lfg.dbm')
_tmax = datetime.timedelta(days=90)
_role2emoji = param.role2emoji
_tz = pytz.timezone(param.rc('timezone'))

# todo: auto react(drop or update?), CoC rxn for role/multi-lfgs


class _ActivityFile(param.IntPermaDict):
    def __init__(self, cog, fn=_dbm):
        self.cog = cog
        super().__init__(fn)

    def _clear_old(self, key):
        old = (datetime.datetime.utcnow() - _tmax).timestamp()
        if key in self:
            pops = [i for i in self[key] if i[1] < old]
            for p in pops:
                self[key].pop(p)

    def update_pings(self, msg, _roles):
        user_id = msg.author.id
        self._clear_old(user_id)
        entry = [msg.id, msg.created_at.timestamp()] + _roles
        if user_id in self:
            self[user_id].append(entry)
        else:
            self[user_id] = [entry]

    def _get_role_id(self, role):
        if isinstance(role, int):
            return role
        out = find_role(self.cog.bot.tdt, role)
        if out is None:
            out = find_role(self.cog.bot.tdt, "d2 " + role)
        return out

    def _row_to_role_ids(self, row):
        return filter(None, [self._get_role_id(r) for r in row[2:]])

    def _fmt_row(self, row):
        msg = row[0]
        # assign UTC timezone
        dt = pytz.utc.localize(datetime.datetime.fromtimestamp(row[1]))
        # convert to server timezone
        dt = dt.astimezone(_tz)
        _roles = [r for r in self._row_to_role_ids(row) if r in _role2emoji]
        _roles = ' '.join([':{}:'.format(_role2emoji[r]) for r in _roles])
        return _roles + ' {}; message ID: {}'.format(dt, msg)

    def member_list(self, mid):
        out = []
        if mid in self:
            out = [self._fmt_row(i) for i in self[mid]]
        return out

    def member_summary(self, mid):
        data = self[mid]
        tot = 0
        _roles = dict()
        for d in data:
            for role in self._row_to_role_ids(d):
                tot += 1
                _roles[role.id] = _roles.get(role, 0) + 1
        return tot, _roles


class LFG(commands.Cog):
    channels = [channels.lfg_pvp, channels.lfg_pve, channels.lfg_shenanigans]

    def __init__(self, bot, debug=False):
        self.bot = bot
        self._last_member = None
        self._kicks = []
        self.data = _ActivityFile(self)
        self._init = False
        self._init_finished = False
        self._debug = debug
        self._cached_search = None

    def _get_emoji(self, role, guild):
        emoji = _role2emoji.get(role, role)
        try:
            return [e for e in guild.emojis if e.name == emoji][0]
        except IndexError:
            return ''

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self._async_init()

    async def _async_init(self):
        if self._init:
            return
        self._init = True

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Parse reactions"""
        pass

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages for new lfg post"""
        # if not lfg channel
        if message.channel.id in self.channels:
            return
        roles_tagged = []
        for role in message.role_mentions:
            try:
                emoji = _role2emoji[role.id]
                emoji = [e for e in message.guild.emojis if e.name == emoji][0]
                await message.add_reaction(emoji)
                roles_tagged.append(role.id)
            except KeyError:
                pass
            except IndexError:
                pass
        if roles_tagged:
            self.data.update_pings(message, roles_tagged)

    @commands.command()
    @commands.check(admin_check)
    async def ping_data(self, ctx, member: discord.User = None):
        """<member (optional:caller)> - Show ping data for a member"""
        if member is None:
            member = ctx.author
        await split_send(ctx, self.data.member_list(member.id))

    @commands.command()
    @commands.check(admin_check)
    async def ping_summary(self, ctx, member: discord.User = None):
        """<member (optional:caller)> - Show ping summary for a member"""
        if member is None:
            member = ctx.author
        tot, data = self.data.member_summary(member.id)
        out = 'Total: {}; '.format(tot)
        out += ', '.join(['{} :{}:'.format(value, self._get_emoji(role, ctx.guild)) for
                          role, value in data.items()])
        await ctx.send(out)


if usingV2:
    async def setup(bot):
        cog = LFG(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(LFG(bot))
