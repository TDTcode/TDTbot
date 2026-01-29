"""
Trick or Treat game cog

Intructions for initiation:
- Create a channel named "the_neighborhood" (or change the _channel variable)
- Create a message in #manual_page and copy the id to param.messages.trick_or_treat
- Make sure _game_on is set to "auto" or True
- Create a role named "SPOOKY" (or change the _role variable)
"""

import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import asyncio
import datetime
import pytz
import random
from .. import param
from ..param import messages, channels
from ..helpers import find_role, second, day
from ..config import UserConfig
from ..async_helpers import split_send, sleep, admin_check, wait_until
from ..version import usingV2
import logging
try:
    import ephem
    moon = ephem.Moon()
except ImportError:
    moon = None
    print("ephem not installed, moon phase will not be available")


logger = logging.getLogger("discord." + __name__)
_utc = pytz.utc
year = "{:04d}".format(datetime.datetime.now(_utc).year)
iyear = int(year)

# main settings:
_channel = "the_neighborhood"       # trick-or-treat channel name or id
# MAKE SURE TO UPDATE MESSAGE ID IN param.py
_rule_id = messages.trick_or_treat  # message id for rules/reaction check
_game_on = "auto"                   # flag to run game, "auto" for auto start/stop
_role = "SPOOKY"                    # role name or id for game participation
_nmin = 2, 5                        # minimum number (range) of votes to start count
# secondary settings
_start = 0                     # starting score
_trick = "😈"                   # trick emoji
_treat = "🍬"                   # treat emoji
_enroll = "🎃"                  # enroll in game emoji/reaction
_msg = "Trick ({:}) or Treat ({:})!".format(_trick, _treat)
# keywords for player/bot config storage
_score = "tdt.trick_or_treat.score." + year
_bot = "tdt.trick_or_treat.msg." + year
_nlast = "tdt.trick_or_treat.nlast." + year
# start/stop datetime
_tz = pytz.timezone(param.rc('timezone'))
_start_time = datetime.datetime(iyear, 10, 1, 0, 0, 0, 0, _tz)
_stop_time = datetime.datetime(iyear, 11, 1, 0, 0, 0, 0, _tz)

# manual page
_manual = channels.manual_page

# alt accounts
_alts = {547171042565685250: [856003669090369536, 522962175690539008],  # eyes
         604505229593149462: [901988686277804073, 901984697805049916],  # bob
         }
_all_alts = []
for i in _alts.values():
    _all_alts.extend(i)


def sign(x):
    return bool(x > 0) - bool(x < 0)


def random_time(nlast=None, add_random=True):
    """Return a random time in seconds. nlast is the number of votes last time."""
    if nlast is None:
        nlast = 5
    if add_random:
        nlast += random.uniform(-1, 1)
    nlast = min(max(1, nlast), 10)
    shape = 22 - 2 * nlast
    scale = -1.4 * nlast + 16.4
    ratio = 5 * (16 - nlast)
    t = (random.weibullvariate(shape, scale) + .5) * ratio
    return min(max(30, t), 3600)


def get_phase(dt=None):
    """Returns a floating-point number from 0-1. where 0=new, 0.5=full, 1=new"""
    # Ephem stores its date numbers as floating points, which the following uses
    # to conveniently extract the percent time between one new moon and the next
    # This corresponds (somewhat roughly) to the phase of the moon.

    if dt is None:
        dt = datetime.datetime.now()
    date = ephem.Date(dt)

    nnm = ephem.next_new_moon(date)
    pnm = ephem.previous_new_moon(date)

    lunation = (date-pnm)/(nnm-pnm)

    return lunation


def phase_to_emoji(phase=None):
    """Convert lunar phase (not illumination fraction) to nearest emoji"""
    phase = get_phase() if phase is None else phase
    phases = "🌑🌒🌓🌔🌕🌖🌗🌘"
    x = (phase * len(phases) + .5) % len(phases)
    return phases[int(x)]


class TrickOrTreat(commands.Cog):
    """Cog for trick or treat game"""
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
        self._configs = dict()
        self._init = False
        self._active_message_id = None
        self._awaiting = None
        self._last = datetime.datetime.now()
        self._game_on = _game_on
        self._role = None
        self._channel = None
        self._log = None
        self._rule_id = _rule_id
        self._enrolled = False
        self._lock = False

    def _enroll_emoji_role(self):
        if self._enrolled:
            return
        if not self._rule_id:
            return
        self.bot.enroll_emoji_role({_enroll: _role}, message_id=self._rule_id)
        self._enrolled = True

    async def _post_or_fetch_start_message(self):
        if self._rule_id:
            self._enroll_emoji_role()
            return self._rule_id
        msg = "**Candy Cartel**\nIn this world it's trick or be treated. Click the {:} reaction below to sign up for our seasonal trick or treating game. Outsmart, coerce, and backstab your friends to become this neighborhood candy king. The winner is announced at the end of the October month and is given a 1 month special title/role which operates like being promoted to community rank!"  # noqa: E501
        msg = msg.format(_enroll)
        channel = await self.bot.fetch_channel(_manual)
        async for message in channel.history(limit=200):
            if message.author == self.bot.user and message.content == msg:
                self._rule_id = message.id
                self._enroll_emoji_role()
                return message.id
        message = await channel.send(msg)
        await message.add_reaction(_enroll)
        self._rule_id = message.id
        self._enroll_emoji_role()
        return message.id

    @property
    def game_on(self):
        """Return game on/off flag"""
        self._enroll_emoji_role()
        if not self._game_on:
            return False
        if self._game_on == "auto":
            return _start_time <= datetime.datetime.now(_utc) <= _stop_time
        if self._game_on is True:
            return True
        return True

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
        if not self.game_on:
            return True
        # otherwise only the designated channel and log channel have access
        if ctx.channel == self.channel:
            return True
        return ctx.channel == self.log

    async def send_message(self, dt=0, set_timer=True, nlast=None):
        """Send trick-or-treat message"""
        # print("send_message", dt, set_timer, nlast)
        # if game is not active then quit
        if not self.game_on:
            # print("sm: return not game on")
            return
        # if we have an active game message already then quit
        if self.message_id:
            # print("sm: return active", self.message_id)
            return
        # if we are awaiting responses then quit
        if self._awaiting:
            # print("sm: return awaiting", self._awaiting)
            return
        # print("msg dt", dt)
        if dt is True:
            dt = random_time()
        await sleep(dt)
        # ensure some funny business didn't happen while we were waiting
        if self.message_id:
            return
        if self._awaiting:
            return
        msg = 'TrickOrTreat.send_message waiting for {:} s ({:})'
        logger.info(msg.format(dt, datetime.datetime.now() + dt * second))
        # send new active game message
        msg = await self.channel.send(_msg)
        self._set_msg_id(msg.id)
        await msg.add_reaction(_trick)
        await msg.add_reaction(_treat)
        if set_timer == 0:
            set_timer = .01
        if set_timer:
            # launch task for delayed count tally/finish
            self.bot.loop.create_task(self.finish_count(dt=set_timer, mid=msg.id, nlast=nlast))

    def send_later(self, **kwargs):
        """Non-async wrapper for send_message"""
        if not self.game_on:
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

    async def finish_count(self, dt=0, set_timer=True, mid=0, nmin=None, nlast=None):
        """Finish/tally count on active game message"""
        # print("finish_count", dt, set_timer, mid, nmin, nlast, self._lock)
        if self._lock:
            # print("lock return")
            return
        self._lock = True
        try:
            if nlast is None:
                nlast = self._get_config().set_if_not_set(_nlast, 5)
            else:
                self._get_config()[_nlast] = nlast
            if self._game_on is False:
                # print("finish_count return no game")
                self._lock = False
                return
            if dt is True:
                dt = random_time()
            msg = 'TrickOrTreat.finish_count waiting for {:} s ({:})'
            logger.info(msg.format(dt, datetime.datetime.now() + dt * second))
            if self._awaiting is None:
                self._awaiting = mid
            await sleep(dt)
            msg = await self._get_message()
            if not msg:
                if set_timer:
                    logger.info('Finish TrickOrTreat.finish_count (no message)')
                    self._awaiting = None
                    self._lock = False
                    return await self.send_message(dt=2)
            if msg.id != mid:
                logger.info('Finish TrickOrTreat.finish_count (bad id)')
                self._awaiting = None
                self._lock = False
                return
            trickers = []
            treaters = []
            ntrick, ntreat = 0, 0
            noa_trick, noa_treat = [], []
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
                        logger.info('trick_or_treat.finish_count: removing rxn {}'.format(rxn))
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
            if nmin is None:
                nmin = random.randint(_nmin[0], _nmin[1])
            # if alt accounts are used
            if noa_tot >= nmin > ntot:
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
                    self._lock = False
                    return self.count_later(dt=set_timer, mid=mid, nlast=max(noa_tot, nlast - 1))
            # if not enough votes
            elif len(set(trickers + treaters)) < nmin:
                logger.info('Finish TrickOrTreat.finish_count (too few votes)')
                # self._awaiting = None
                self._lock = False
                return self.count_later(dt=set_timer, mid=mid, nlast=max(noa_tot, nlast - 1))
            self._last = datetime.datetime.now()
            ntrick -= 1
            ntreat -= 1
            results = ' {:} x {:} vs {:} x {:}'
            results = results.format(ntrick, _trick, ntreat, _treat)
            ntot = max(noa_tot, 1)
            scale = (_stop_time - _start_time) / max(_stop_time - datetime.datetime.now(_utc), day)
            scale = max(1, int(scale + .5))
            delta = random.randint(1, ntot * scale)
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
            # based on moon phase swap trickers/treaters
            phase = .5
            if moon:
                moon.compute()
                phase = moon.phase * 0.01
            else:
                print("No moon phase data")
            trickers = [await self._member(u) for u in trickers]
            treaters = [await self._member(u) for u in treaters]
            msg = "{:}The light of the moon brings forth a treat for the tricksters, and a trick for the treaters.{:}"
            if random.random() < .05 * phase:
                a = b = ""
                if moon:
                    luna = phase_to_emoji()
                    a = luna + " "
                    b = " " + luna
                await self.channel.send(msg.format(a, b))
                tmp = trickers
                trickers = treaters
                treaters = tmp
            # apply deltas
            deltas = {user: dtrick for user in trickers}
            for user in treaters:
                deltas[user] = deltas.get(user, 0) + dtreat
            users = sorted(deltas.keys(), key=lambda u: u.display_name)
            fmt = "{0.display_name} : {1:d}{2:+d} => {3:d} (current)"
            summary = [fmt.format(u, *self.apply_delta(u, deltas[u]))
                       for u in users if deltas[u]]
            # print("summary", summary)
            await self.channel.send(txt)
            await split_send(self.channel, summary, style='```')
            self._set_msg_id(0)
            if self._game_on == "auto" and datetime.datetime.now(_utc) > _stop_time:
                self._awaiting = None
                msg = "Thank you all for playing this year. Here is the final tally:"
                await self.channel.send(msg)
                await self.rankings(self.channel)
                self._game_on = False
                logger.info('Finish TrickOrTreat.finish_count (Finished Game)')
            if set_timer == 0:
                set_timer = .01
            self.send_later(dt=1)
            self._awaiting = None
            self._lock = False
            logger.info('Finish TrickOrTreat.finish_count (end)')
        finally:
            self._lock = False

    def count_later(self, **kwargs):
        if not self.game_on:
            return
        logger.info('TrickOrTreat.channel')
        if kwargs.get('nlast', None) is not None:
            self._get_config()[_nlast] = kwargs.get('nlast')
        self.bot.loop.create_task(self.finish_count(**kwargs))

    @commands.Cog.listener()
    async def on_ready(self):
        # print("on_ready")
        await asyncio.sleep(5)
        await self._async_init()

    async def _async_init(self):
        # print("_async_init")
        sent = False
        if not self._init:
            if not self._rule_id:
                if self.game_on:
                    await self._post_or_fetch_start_message()
                elif datetime.datetime.now() < _start_time:
                    await wait_until(_start_time)
                    await asyncio.sleep(1)
                    await self._post_or_fetch_start_message()
            self._init = True
            if not await self._get_message():
                await self.send_message(dt=3)
                return
            else:
                self.count_later(dt=True, mid=self.message_id)
                sent = True
        if not self.message_id:
            if datetime.datetime.now() - self._last > datetime.timedelta(minutes=5):
                await self.send_message(dt=1)
                return
        if not self._awaiting and not sent:
            self.count_later(mid=self.message_id)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages"""
        # ignore all messages from our bot
        if message.author == self.bot.user:
            return
        if not self.game_on:
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
        channel = self.channel if self.game_on else ctx
        await split_send(channel, summary, style='```')

    @commands.command()
    async def alt_rankings(self, ctx):
        """Show current rankings for trick or treat"""
        configs = await self.bot.get_user_configs()
        players = [c for c in configs if _score in c]
        data = {await self._member(p.user): p[_score] for p in players}
        users = sorted(data.keys(), key=lambda u: (data[u], u.display_name), reverse=True)
        summary = ['{0.display_name} : {1}'.format(u, data[u]) for u in users]
        channel = self.channel if self.game_on else ctx
        await split_send(channel, summary, style='```')

    @commands.command()
    @commands.check(admin_check)
    async def set_score(self, ctx, n: int, member: discord.Member = None):
        """<n> <member (optional:caller)> sets trick or treat points"""
        if member is None:
            member = ctx.author
        UserConfig(member)[_score] = n
        await ctx.send('Set score of {:} to {:}.'.format(member, n))

    @commands.command()
    @commands.check(admin_check)
    async def force_count(self, ctx):
        """Force a count"""
        await self.finish_count(mid=self.message_id)

    @commands.command()
    @commands.check(admin_check)
    async def end_game(self, ctx):
        """Finish Trick or Treat game"""
        mid = self.message_id
        if mid:
            await self.finish_count(dt=0, set_timer=False, mid=mid)
        self._game_on = False
        await self.rankings(ctx)

    @commands.command()
    @commands.check(admin_check)
    async def clear_neighborhood(self, ctx, limit: int = 200):
        """<limit=200 (optional)> Clear the events channel.
        "limit" sets the max number of messages deleted.
        If this command is used as a reply then it will clear messages before that message
        """
        before = None
        check = None
        ref = ctx.message.reference
        if ref:
            if hasattr(ref, 'resolved'):
                msg = ref.resolved
            else:
                channel = self.bot.find_channel(ref.channel_id)
                if channel is None:
                    channel = await self.bot.fetch_channel(ref.channel_id)
                if channel is None:
                    msg = ref
                else:
                    msg = await channel.fetch_message(ref.message_id)
            before = msg.created_at

            def purge_check(message):
                if message.author != self.bot.user:
                    return True
                return message.content != ""

            check = purge_check

        await self.channel.purge(limit=limit, before=before, check=check)
        if ctx.channel == self.channel:
            await asyncio.sleep(5)
            try:
                await ctx.message.delete()
            except discord.errors.NotFound:
                pass


if usingV2:
    async def setup(bot):
        if _game_on:
            cog = TrickOrTreat(bot)
            await bot.add_cog(cog)
else:
    def setup(bot):
        if _game_on:
            bot.add_cog(TrickOrTreat(bot))
