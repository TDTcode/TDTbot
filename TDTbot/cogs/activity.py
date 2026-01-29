import asyncio
import datetime
import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import logging
import pickle
import os
from .. import param
from ..version import usingV2
from ..helpers import epoch, int_time, find_role, localize
from ..async_helpers import admin_check, split_send
from .supporters import supporters_fn


roles = param.roles
logger = logging.getLogger('discord.' + __name__)
_days_inactive = 14
_limit = 5000
_dbm = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]
_dbm = os.path.join(_dbm, 'config', 'activity.dbm')
_epoch = epoch


class _ActivityFile(param.IntPermaDict):
    def update_activity(self, user_id, in_time=None):
        now = int_time(in_time=in_time)
        if user_id in self:
            try:
                self[user_id] = max(now, self[user_id])
            except pickle.UnpicklingError:
                self[user_id] = now
        else:
            self[user_id] = now

    def inactive(self, dt=None, return_dict=False):
        if dt is None:
            dt = datetime.timedelta(days=_days_inactive)
        dt = int(dt.total_seconds())
        now = int_time()
        if return_dict:
            return {int(i): self.get(i, 0) for i in self.file
                    if now - self.get(i, 0) > dt}
        else:
            return [int(i) for i in self if now - self.get(i, 0) > dt]

    async def fetch_and_sort(self, guild, inactive=None, dt=None):
        if inactive is None:
            inactive = self.inactive(dt=dt, return_dict=True)
        inactive = sorted(inactive.items(), key=lambda x: x[1])
        out = []
        for i in inactive:
            member = guild.get_member(i[0])
            if member is None:
                try:
                    member = await guild.fetch_member(i[0])
                except discord.errors.NotFound:
                    continue
            if member is not None:
                out.append([member, _epoch + datetime.timedelta(seconds=i[1])])
        return out


class Activity(commands.Cog):
    def __init__(self, bot, debug=False):
        self.bot = bot
        self._last_member = None
        self._kicks = []
        self.data = _ActivityFile(_dbm)
        self._init = False
        self._init_finished = False
        self._debug = debug
        self._cached_search = None
        self._my_role = None

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
        self._init = True
        data = await self._hist_search(limit=100, use_ids=True, save=True)
        for i in data:
            self.data.update_activity(i, data[i])
        data = await self._hist_search(limit=_limit, use_ids=True, save=True)
        for i in data:
            self.data.update_activity(i, data[i])
        try:
            self._my_role = (await self.bot.get_or_fetch_user(self.bot.user.id)).top_role
        except AttributeError:
            pass
        self._init_finished = True

    async def _hist_search(self, guild=None, members=None, limit=1000, use_ids=False,
                           ctx=None, save=None):
        if guild is None:
            if ctx is None:
                guild = [g for g in self.bot.guilds if g.name == "The Dream Team"][0]
            else:
                guild = ctx.guild
        if members is None:
            members = guild.members
        data = dict()
        # get all channels with a history attribute
        channels = [i for i in guild.channels if hasattr(i, "history")]
        oldest = datetime.datetime.utcnow()  # store the oldest time parsed
        old_af = _epoch  # just some really old date
        for channel in channels:
            try:
                # loop through messages in history (limit 1000 messages per channel)
                async for msg in channel.history(limit=limit):
                    # update oldest
                    oldest = min(localize(oldest), localize(msg.created_at))
                    # add/update data for message author
                    if msg.author in members:
                        key = msg.author
                        if use_ids:
                            key = key.id
                        try:
                            # use the most recent date
                            data[key] = max(localize(data[key]), localize(msg.created_at))
                        except KeyError:
                            data[key] = msg.created_at
            except discord.Forbidden:
                # We do not have permission to read this channel's history
                logger.debug("Cannot read channel {0}.".format(channel))
        # make sure we have data for each member
        for member in members:
            key = member
            if use_ids:
                key = key.id
            if key not in data:
                # use join date if it's more recent than oldest
                try:
                    if localize(member.joined_at) > oldest:
                        data[key] = member.joined_at
                    else:
                        data[key] = old_af
                        logger.debug('old af: {}'.format(member))
                except TypeError:
                    print("no member join date", member)
                    data[key] = old_af
                    logger.debug('old af: {}'.format(member))
        if save is None and self._cached_search is None:
            save = True
        if save:
            self._cached_search = data.copy()
            self._cached_search['use_ids'] = use_ids
        return data

    @commands.command()
    async def inactivity(self, ctx, role: discord.Role = None, dt: int = None):
        """<role (optional)> shows how long members have been inactive for."""
        await ctx.send("Hold on while I parse the server history.")
        await self._async_init()
        if dt is None:
            dt = datetime.timedelta(seconds=-1)
        else:
            dt = datetime.timedelta(days=dt)
        items = await self.data.fetch_and_sort(ctx.guild, dt=dt)
        if role in ['none', 'None']:
            role = None
        if role is not None:
            items = [i for i in items if role in i[0].roles]
        msg = ['{0.display_name} {1}'.format(i[0], i[1].date().isoformat())
               for i in items]
        await split_send(ctx, msg, style='```')

    @commands.command()
    @commands.check(admin_check)
    async def set_activity_debug(self, ctx):
        """Turns on debug mode for activity."""
        self._debug = True
        await ctx.send("Activity cog now in debugging mode.")

    @commands.command()
    @commands.check(admin_check)
    async def unset_activity_debug(self, ctx):
        """Turns off debug mode for activity."""
        self._debug = False
        await ctx.send("Activity cog now in normal mode.")

    @commands.command()
    async def purge(self, ctx, skip_supporters: bool = False):
        """<role (optional)> purges the activity data for the given role."""
        if self._debug:
            await ctx.send("`<Running in debug mode>`")
        await ctx.send("Hold on while I purge the activity data.")
        com = find_role(ctx.guild, roles.community)
        com_p = find_role(ctx.guild, roles.community_plus)
        items = await self.data.fetch_and_sort(ctx.guild, dt=datetime.timedelta(days=30))
        items = [i for i in items if i[0].top_role in [com, com_p]]

        output = []
        errors = []

        recruit = find_role(ctx.guild, roles.recruit)
        for m, date in items:
            if skip_supporters:
                support = param.IntPermaDict(supporters_fn)
                if m.id in support:
                    if self._debug:
                        output.append('{0.display_name} in supporters (last active {1})'.format(m, date.isoformat()))
                    continue
            if not self._debug:
                _roles = [r for r in m.roles if r > recruit]

                try:
                    if self._my_role and m.top_role > self._my_role:
                        raise discord.Forbidden()
                    await m.remove_roles(*_roles)
                    await m.add_roles(recruit)
                    output.append('{0.display_name} demoted (last active {1})'.format(m, date))
                except discord.Forbidden:
                    errors.append('⚠️{0.display_name} cannot be demoted (last active {1})'.format(m, date))
            else:
                output.append('{0.display_name} (not) demoted (last active {1})'.format(m, date))
        await split_send(ctx, errors + output)
        return

    @commands.command()
    async def full_purge(self, ctx, role: discord.Role = None):
        """<role (optional)> shows members that have been inactive for over a week."""
        if self._debug:
            await ctx.send("`<Running in debug mode>`")
        await ctx.send("Hold on while I parse the server history.")
        if not self._debug:
            await self._async_init()
        recruit = find_role(ctx.guild, roles.recruit)
        items = await self.data.fetch_and_sort(ctx.guild)
        if role is not None:
            items = [i for i in items if role in i[0].roles]

        lowers = []
        output = []

        for i in items:
            if i[0].top_role == recruit:
                output.append(await self._clear_roles(*i))
            elif i[0].top_role <= recruit:
                if i[0].top_role.name not in ['Lone Wolf'] and not i[0].bot:
                    lowers.append(i)
                elif not i[0].bot:
                    logger.info('Skipping', i)
        await split_send(ctx, output)

        for i in lowers:
            await self._prompt_kick(*i)

        return

    async def _clear_roles(self, m, dt, debug=None):
        if debug is None:
            debug = self._debug
        _roles = [r for r in m.roles if r.name not in ['@everyone', 'Nitro Booster']]
        if not debug:
            await m.remove_roles(_roles, reason='Inactivity')
        date = dt.date().isoformat()
        if not debug:
            return '{0.display_name} demoted (last active {1})'.format(m, date)
        else:
            return '{0.display_name} (not) demoted (last active {1})'.format(m, date)

    async def _prompt_kick(self, m, dt, channel=None):
        if channel is None:
            channel = self.bot.find_channel(param.rc('log_channel'))
        date = dt.date().isoformat()
        msg = 'Should I kick {0.display_name} (#{0.discriminator}), last active {1}?'
        msg = await channel.send(msg.format(m, date))
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')
        self._kicks.append([msg, m])

    @commands.Cog.listener()
    async def on_message(self, message):
        self.data.update_activity(message.author.id)
        if not self._init:
            await self._async_init()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Parse reactions"""
        self.data.update_activity(payload.user_id)
        # if reaction is to a kick quarry
        ids = [k[0].id for k in self._kicks]
        if payload.message_id in ids:
            emoji = str(payload.emoji)
            if emoji in ['✅', '❌']:
                guild = await self.bot.fetch_guild(payload.guild_id)
                if await admin_check(author=payload.member, guild=guild):
                    if emoji == '✅':
                        index = ids.index(payload.message_id)
                        msg, member = self._kicks.pop(index)
                        if not self._debug:
                            await member.kick(reason='Inactivity')
                        await msg.add_reaction('🔨')
                        return
                    if emoji == '❌':
                        index = ids.index(payload.message_id)
                        msg, member = self._kicks.pop(index)
                        await msg.add_reaction('👌')
                        return

    @commands.command()
    async def activity_init_status(self, ctx):
        """Shows the status of the activity init."""
        await ctx.send('init = {0._init}, init_finished = {0._init_finished}.'.format(self))

    @commands.command()
    async def parse_cached(self, ctx, member: discord.Member = None):
        """<member (optional:caller)> parses the cached activity data for a member."""
        if member is None:
            member = ctx.author
        name = member.display_name
        if self._cached_search.get('use_ids'):
            member = member.id
        value = self._cached_search[member]
        print(member, value)
        msg = ' '.join([str(i) for i in [name, value]])
        await ctx.send(msg)

    @commands.command()
    async def parse_data(self, ctx, member: discord.Member = None):
        """<member (optional:caller)> parses the activity data for a member."""
        if member is None:
            member = ctx.author
        name = member.display_name
        value = self.data[member.id]
        date = _epoch + datetime.timedelta(seconds=value)
        msg = ' '.join([str(i) for i in [name, value, date]])
        await ctx.send(msg)


if usingV2:
    async def setup(bot):
        cog = Activity(bot, debug=False)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(Activity(bot, debug=False))
