import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import asyncio
import datetime
import random
from .. import param
from ..helpers import find_role
from ..config import UserConfig
from ..async_helpers import split_send, sleep, admin_check
from ..version import usingV2
import logging


logger = logging.getLogger("discord." + __name__)

_init_time = datetime.datetime.utcnow()
_month = _init_time.month
_year = _init_time.year
_year = (_year - 1, _year) if _month < 7 else (_year, _year + 1)
_year = '{:04d}-{:04d}'.format(*_year)
_year = 'debug_' + _year

# main settings:
_channel = "winter_wonderland"   # trick-or-treat channel name or id
_rule_id = 0   # message id for rules/reaction check
_game_on = True                  # flag to run game
_role = "Snow_Day"               # role name or id for game participation
_max_walls = 3                   # Maximum number of walls
# secondary settings
_tmin, _tmax = 5 * 60, 15 * 60  # min/max time between rounds
_start = 0                      # starting snow
_snowstorm = "🌨"              # treat emoji
_enroll = "❄️"                  # enroll in game emoji/reaction
_msg = "Snowstorm inbound. Collect it before it melts"
_snow_name = "snow (grams)"
# keywords for player/bot config storage
_name_base = "tdt.snowstorm." + _year + "."
_score = _name_base + "score"
_bot = _name_base

# holdovers from trick_or_treat.py copy
_trick = "😈"                   # trick emoji
_treat = "🍬"                   # treat emoji
_nmin = 3                     # minimum number of votes to start count
# alt accounts
_alts = {547171042565685250: [856003669090369536, 522962175690539008],  # eyes
         604505229593149462: [901988686277804073, 901984697805049916],  # bob
         }
_all_alts = []
for i in _alts.values():
    _all_alts.extend(i)
# end of holdovers from trick_or_treat.py copy


class Item:
    def __init__(self, name, cost, description):
        self.name = name
        self.cost = cost
        self.description = description

    def blerb(self):
        out = '**{}**\n{}\nCost to make: '.format(self.name, self.description)
        out += ', '.join(['{} {}'.format(self.cost[i], i) for i in self.cost])
        return out


_items = [Item("Snowball", {_snow_name: 100}, "Toss a snowball at another player"),
          Item("Ice Wall", {_snow_name: 200}, "Build an ice wall to protect your self"),
          ]
_items = {i.name: i for i in _items}


def sign(x):
    return bool(x > 0) - bool(x < 0)


class Participant:
    """Class for The Wilds participant"""
    _stat_base = _name_base + 'snow.'
    _item_base = _name_base + 'item.'
    stat_names = [_snow_name]

    def __init__(self, bot, user, config=None, guild=None):
        self.bot = bot
        self.user = user
        if config is None:
            config = UserConfig(user, guild=guild)
        self.config = config

    def __getitem__(self, item):
        if item in self.stat_names:
            return self.config.set_if_not_set(self._stat_base + item, 1)
        if item in _items:
            return self.config.set_if_not_set(self._item_base + item.replace(' ', '_'), 0)
        KeyError("Invalid key: {:}".format(item))

    def __setitem__(self, key, value):
        if value < 0:
            raise ValueError("Stat values cannot be less than zero.")
        if key in self.stat_names:
            self.config[self._stat_base + key] = value
        if key in _items:
            self.config[self._item_base + key.replace(' ', '_')] = value
        else:
            KeyError("Invalid key: {:}".format(key))

    def stats(self):
        return {i: self[i] for i in self.stat_names}

    def stat_str(self):
        stats = self.stats()
        return ', '.join(['{}: {}'.format(i, stats[i]) for i in stats])

    def items(self):
        return {i: self[i] for i in _items}

    def item_str(self):
        items = self.items()
        out = ', '.join(['{}: {}'.format(i, items[i]) for i in items if items[i]])
        if not out:
            out = 'No items found.'
        return out


class Snowstorm(commands.Cog):
    """Cog for trick or treat game"""
    def __init__(self, bot):
        self.bot = bot
        self._configs = dict()
        self._init = False
        self._active_message_id = None
        self._awaiting = None
        self._last = datetime.datetime.now()
        self._game_on = _game_on
        self._role = None
        self._channel = None
        self._log = None
        self.bot.enroll_emoji_role({_enroll: _role}, message_id=_rule_id)

    @property
    def role(self):
        """Trick-or-treat role"""
        if self._role is None:
            self._role = find_role(self.channel.guild, _role)
        return self._role

    @property
    def channel(self):
        """Trick-or-treat channel"""
        if self._channel is None:
            self._channel = self.bot.find_channel(_channel)
        return self._channel

    @property
    def log(self):
        """Log channel"""
        if self._log is None:
            self._log = self.bot.find_channel(param.rc('log_channel'))
        return self._log

    @property
    def message_id(self):
        """Active trick-or-treat game message id"""
        if self._active_message_id is None:
            try:
                self._active_message_id = self._get_config().set_if_not_set(_bot, 0)
            except AttributeError:
                self._active_message_id = None
        return self._active_message_id

    def cog_check(self, ctx):
        """Permission check for this cog"""
        # if game is not active, we can access this cog from any channel
        if not self._game_on:
            return True
        # otherwise only the designated channel and log channel have access
        if ctx.channel == self.channel:
            return True
        return ctx.channel == self.log

    async def send_message(self, dt=0, set_timer=True):
        """Send trick-or-treat message"""
        # if game is not active then quit
        if not self._game_on:
            return
        # if we have an active game message already then quit
        if self.message_id:
            return
        # if we are awaiting responses then quit
        if self._awaiting:
            return
        if dt is True:
            dt = random.randint(_tmin, _tmax)
        await sleep(dt)
        # ensure some funny business didn't happen while we were waiting
        if self.message_id:
            return
        if self._awaiting:
            return
        logger.info('TrickOrTreat.send_message waiting for {:} s'.format(dt))
        # send new active game message
        msg = await self.channel.send(_msg)
        self._set_msg_id(msg.id)
        await msg.add_reaction(_snowstorm)
        await msg.add_reaction(_treat)
        if set_timer == 0:
            set_timer = .01
        if set_timer:
            # launch task for delayed count tally/finish
            self.bot.loop.create_task(self.finish_count(dt=set_timer, mid=msg.id))

    def send_later(self, **kwargs):
        """Non-async wrapper for send_message"""
        if not self._game_on:
            return
        logger.info('TrickOrTreat.send_later')
        self.bot.loop.create_task(self.send_message(**kwargs))

    async def _get_message(self):
        """Get active game message id"""
        if self.message_id:
            try:
                return await self.channel.fetch_message(self.message_id)
            except discord.NotFound:
                self._set_msg_id(0)

    def _set_msg_id(self, idn):
        """set active message id and return old one"""
        old = self.message_id
        self._active_message_id = idn
        self._get_config(self.bot.user)[_bot] = idn
        return old

    def _get_config(self, user=None):
        """Get a user's config file"""
        if user is None:
            user = self.bot.user
        try:
            return self._configs[user.id]
        except KeyError:
            self._configs[user.id] = UserConfig(user)
            return self._configs[user.id]

    def apply_delta(self, user, delta):
        """Update user's score by delta"""
        config = self._get_config(user)
        old = config.set_if_not_set(_score, _start)
        config[_score] += delta
        return old, delta, old + delta

    def get_score(self, user):
        """Return a user's current score"""
        return self._get_config(user).set_if_not_set(_score, _start)

    async def _member(self, user):
        """Get a user/member object"""
        try:
            out = [m for m in self.role.members if m.id == user.id]
            if out:
                return out[0]
        except AttributeError:
            pass
        try:
            out = await self.channel.guild.fetch_member(user.id)
            if not out:
                return user
        except discord.HTTPException:
            pass
        out = self.channel.guild.get_member_named(user.name)
        if out:
            return out
        return user

    async def finish_count(self, dt=0, set_timer=True, mid=0):
        """Finish/tally count on active game message"""
        if not self._game_on:
            return
        if dt is True:
            dt = random.randint(_tmin, _tmax)
        logger.info('TrickOrTreat.finish_count waiting for {:} s'.format(dt))
        if self._awaiting is None:
            self._awaiting = mid
        await sleep(dt)
        msg = await self._get_message()
        if not msg:
            if set_timer:
                logger.info('Finish TrickOrTreat.finish_count (no message)')
                self._awaiting = None
                return await self.send_message(dt=set_timer)
        if msg.id != mid:
            logger.info('Finish TrickOrTreat.finish_count (bad id)')
            self._awaiting = None
            return
        trickers = []
        treaters = []
        ntrick, ntreat = 0, 0
        # tally up the votes
        for rxn in msg.reactions:
            if rxn.emoji == _trick:
                ntrick = rxn.count
                trickers = [user async for user in rxn.users() if user != self.bot.user]
                noa_trick = [u for u in trickers if u.id not in _all_alts]
            elif rxn.emoji == _treat:
                ntreat = rxn.count
                treaters = [user async for user in rxn.users() if user != self.bot.user]
                noa_treat = [u for u in trickers if u.id not in _all_alts]
            else:
                try:
                    logger.info('snowstorm.finish_count: removing rxn {}'.format(rxn))
                    await rxn.clear()
                except discord.HTTPException:
                    pass
        voters = set(trickers + treaters)
        noa_voters = [u for u in voters if u.id not in _all_alts]
        ntot, noa_tot = len(voters), len(set(noa_trick + noa_treat))
        if ntot > noa_tot:
            alting = [u for u in noa_voters if u.id in _all_alts]
            alts_used = list(set([u for u in treaters + trickers if u in _all_alts]))
        else:
            alting = []
            alts_used = []
        if noa_tot >= _nmin > ntot:
            if random.randint(0, 1):
                logger.info('Finish TrickOrTreat.finish_count (too few real votes)')
                self._awaiting = None
                if not random.randint(0, 2):
                    alt = random.choice(alts_used)
                    for rxn in msg.reactions:
                        if rxn.emoji in [_trick, _treat]:
                            try:
                                rxn.remove(alt)
                                msg = 'Removed reaction {} by alt "{}"'
                                logger.info(msg.format(rxn.emoji, alt))
                            except (discord.HTTPException, discord.Forbidden, discord.Not):
                                pass
                return self.count_later(dt=set_timer, mid=mid)
        elif len(set(trickers + treaters)) < _nmin:
            logger.info('Finish TrickOrTreat.finish_count (too few votes)')
            self._awaiting = None
            return self.count_later(dt=set_timer, mid=mid)
        self._last = datetime.datetime.now()
        ntrick -= 1
        ntreat -= 1
        results = ' {:} x {:} vs {:} x {:}'
        results = results.format(ntrick, _trick, ntreat, _treat)
        ntot = max(noa_tot, 1)
        delta = random.randint(3, ntot * 5)
        stealth_nerf = 0
        if alts_used:
            alting = [u for u in noa_voters if u.id in _all_alts]
            if noa_tot == len(alting):
                delta = random.randint(1, 3)
            else:
                stealth_nerf = 1
                if sign(ntrick - ntreat) != sign(len(noa_trick) - len(noa_treat)):
                    stealth_nerf = 2
        if ntrick > ntreat:
            dtrick, dtreat = 0, -3 * delta
            txt = "The tricksters have won:"
        elif ntrick < ntreat:
            dtrick, dtreat = 0, 2 * delta
            txt = "The treaters get a treat!"
        else:
            dtrick, dtreat = 0, 0
            txt = "Tied voting."
        txt += results
        if stealth_nerf:
            for u in alting:
                delt = -abs(dtrick) * stealth_nerf
                msg = 'Stealth nerf "{}" by {} ({})'.format(u, delt, stealth_nerf)
                logger.info(msg)
                self.apply_delta(u, delt)
        trickers = [await self._member(u) for u in trickers]
        treaters = [await self._member(u) for u in treaters]
        deltas = {user: dtrick for user in trickers}
        for user in treaters:
            deltas[user] = deltas.get(user, 0) + dtreat
        users = sorted(deltas.keys(), key=lambda u: u.display_name)
        fmt = "{0.display_name} : {1:d}{2:+d} => {3:d} (current)"
        summary = [fmt.format(u, *self.apply_delta(u, deltas[u]))
                   for u in users if deltas[u]]
        print("summary", summary)
        await self.channel.send(txt)
        await split_send(self.channel, summary, style='```')
        self._set_msg_id(0)
        if set_timer == 0:
            set_timer = .01
        if set_timer:
            self.send_later(dt=True)
        self._awaiting = None
        logger.info('Finish TrickOrTreat.finish_count (end)')

    def count_later(self, **kwargs):
        if not self._game_on:
            return
        logger.info('TrickOrTreat.channel')
        self.bot.loop.create_task(self.finish_count(**kwargs))

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self._async_init()

    async def _async_init(self):
        if not self._init:
            self._init = True
            if not await self._get_message():
                await self.send_message()
                return
            else:
                self.count_later(dt=True, mid=self.message_id)
        if not self.message_id:
            if datetime.datetime.now() - self._last > datetime.timedelta(minutes=15):
                await self.send_message(dt=True)
                return
        if not self._awaiting:
            self.count_later(mid=self.message_id)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages"""
        # ignore all messages from our bot
        if message.author == self.bot.user:
            return
        if not self._game_on:
            return
        await self._async_init()

    @commands.command()
    async def show_points(self, ctx, member: discord.Member = None):
        """<member (optional)> shows trick or treat points"""
        if member is None:
            member = ctx.author
        txt = "{:} has {:} points.".format(member.display_name, self.get_score(member))
        await ctx.send(txt)

    @commands.command()
    @commands.check(admin_check)
    async def print_id(self, ctx):
        """Print current message id"""
        await ctx.send(str(self.message_id))

    @commands.command()
    async def rankings(self, ctx):
        """Show current rankings for trick or treat"""
        role = self.role
        if role is None:
            return await self.alt_rankings(ctx)
        data = {m: self.get_score(m) for m in role.members}
        users = sorted(data.keys(), key=lambda u: (data[u], u.display_name), reverse=True)
        summary = ['{0.display_name} : {1}'.format(u, data[u]) for u in users]
        print(role, data, role.members, self.channel.guild)
        channel = self.channel if self._game_on else ctx
        await split_send(channel, summary, style='```')

    @commands.command()
    async def alt_rankings(self, ctx):
        """Show current rankings for trick or treat"""
        configs = await self.bot.get_user_configs()
        players = [c for c in configs if _score in c]
        data = {await self._member(p.user): p[_score] for p in players}
        users = sorted(data.keys(), key=lambda u: (data[u], u.display_name), reverse=True)
        summary = ['{0.display_name} : {1}'.format(u, data[u]) for u in users]
        channel = self.channel if self._game_on else ctx
        await split_send(channel, summary, style='```')

    @commands.command()
    @commands.check(admin_check)
    async def set_score(self, ctx, n: int, member: discord.Member = None):
        if member is None:
            member = ctx.author
        UserConfig(member)[_score] = n
        await ctx.send('Set score of {:} to {:}.'.format(member, n))

    @commands.command()
    @commands.check(admin_check)
    async def force_count(self, ctx):
        await self.finish_count(mid=self.message_id)

    @commands.command()
    @commands.check(admin_check)
    async def end_game(self, ctx):
        mid = self.message_id
        if mid:
            await self.finish_count(dt=0, set_timer=False, mid=mid)
        self._game_on = False

        await self.rankings(ctx)


if usingV2:
    async def setup(bot):
        return
        cog = Snowstorm(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        return
        bot.add_cog(Snowstorm(bot))
