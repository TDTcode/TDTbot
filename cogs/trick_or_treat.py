import asyncio
import datetime
import discord
from discord.ext import commands
import random
from .. import param
from ..helpers import *
from ..config import UserConfig
from ..async_helpers import split_send, sleep, admin_check
import logging


logger = logging.getLogger("discord." + __name__)
year = "{:04d}".format(datetime.datetime.utcnow().year)

# main settings:
_channel = "the_neighborhood"   # trick-or-treat channel name or id
_rule_id = 892838986882617385   # message id for rules/reaction check
_game_on = False                # flag to run game
_role = "SPOOKY"                # role name or id for game participation
_nmin = 3                       # minimum number of votes to start count
# secondary settings
_tmin, _tmax = 5 * 60, 15 * 60  # min/max time between rounds
_start = 0                      # starting score
_trick = "😈"                   # trick emoji
_treat = "🍬"                   # treat emoji
_enroll = "🎃"                  # enroll in game emoji/reaction
_msg = "Trick ({:}) or Treat ({:})!".format(_trick, _treat)
# keywords for player/bot config storage
_score = "tdt.trick_or_treat.score." + year
_bot = "tdt.trick_or_treat.msg." + year

# alt accounts
_alts = {547171042565685250: [856003669090369536, 522962175690539008],  # eyes
         604505229593149462: [901988686277804073, 901984697805049916],  # bob
         }
_all_alts = []
for i in _alts.values():
    _all_alts.extend(i)


def sign(x):
    return bool(x > 0) - bool(x < 0)


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
        logger.printv('TrickOrTreat.send_message waiting for {:} s'.format(dt))
        # send new active game message
        msg = await self.channel.send(_msg)
        self._set_msg_id(msg.id)
        await msg.add_reaction(_trick)
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
        logger.printv('TrickOrTreat.send_later')
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
        logger.printv('TrickOrTreat.finish_count waiting for {:} s'.format(dt))
        if self._awaiting is None:
            self._awaiting = mid
        await sleep(dt)
        msg = await self._get_message()
        if not msg:
            if set_timer:
                logger.printv('Finish TrickOrTreat.finish_count (no message)')
                self._awaiting = None
                return await self.send_message(dt=set_timer)
        if msg.id != mid:
            logger.printv('Finish TrickOrTreat.finish_count (bad id)')
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
                    logger.printv('trick_or_treat.finish_count: removing rxn {}'.format(rxn))
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
                logger.printv('Finish TrickOrTreat.finish_count (too few real votes)')
                self._awaiting = None
                if not random.randint(0, 2):
                    alt = random.choice(alts_used)
                    for rxn in msg.reactions:
                        if rxn.emoji in [_trick, _treat]:
                            try:
                                rxn.remove(alt)
                                msg = 'Removed reaction {} by alt "{}"'
                                logger.printv(msg.format(rxn.emoji, alt))
                            except (discord.HTTPException, discord.Forbidden, discord.Not):
                                pass
                return self.count_later(dt=set_timer, mid=mid)
        elif len(set(trickers + treaters)) < _nmin:
            logger.printv('Finish TrickOrTreat.finish_count (too few votes)')
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
                logger.printv(msg)
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
        logger.printv('Finish TrickOrTreat.finish_count (end)')

    def count_later(self, **kwargs):
        if not self._game_on:
            return
        logger.printv('TrickOrTreat.channel')
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


def setup(bot):
    bot.add_cog(TrickOrTreat(bot))
