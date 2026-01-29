import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import asyncio
import datetime
import pytz
import random
from .. import param
from ..helpers import find_role
from ..config import UserConfig
from ..async_helpers import split_send, sleep, admin_check, wait_until
from ..version import usingV2
import logging


logger = logging.getLogger('discord.' + __name__)


_stale = '<:never:588737463376412692>'
_bot = 'tdt.wilds.msg'
_channel = "the-wilds"
_role = "Lone Wolf"
_hour = 3600
_tmin, _tmax = 45 * 60, 75 * 60
# _tmin, _tmax = 10, 30
_dday = datetime.timedelta(days=1)
_dhour = datetime.timedelta(hours=1)
_dmin = datetime.timedelta(minutes=1)
_dsec = datetime.timedelta(seconds=1)


def time_mod(time, delta, epoch=None, tz=None):
    if tz is None:
        tz = time.tzinfo
    if epoch is None:
        epoch = datetime.datetime(2000, 1, 1, tzinfo=tz)
    return (time - epoch) % delta


def next_time(delta, epoch=None, tz=None):
    if tz is None:
        tz = pytz.utc
    time = tz.localize(datetime.datetime.now())
    mod = time_mod(time, delta, epoch=epoch)
    return time.astimezone(pytz.utc).replace(tzinfo=None) + (delta - mod) + _dsec


async def send_wilds_info(member):
    """Sends welcome message to member"""
    msg = '**The Wilds Rules**\n' \
          '1. Rewards\n' \
          '  - Immediate promotion or interview for promotion\n' \
          '  - Special Wolf badge\n' \
          '  - Ability to change/set their wolfpack role\n' \
          '2. Consequences\n' \
          '  - Demoted one rank\n' \
          '  - Locked in the Wilds for one week until rescue (and banned if player tries to leave and rejoin during lockout)\n' \
          '  - Shame upon your whole family\n' \
          '3. What your Signing up for\n' \
          '  - You forfeit all rank\n' \
          '  - You loose all access to all chat rooms except "the wilds" and the "lfg" chat BUT lfg doesnt allow read message history\n' \
          '  - You must agree to "appear offline" on all gaming profiles.\n' \
          '  - All challenges either test your wolfpack knowledge or require playing Destiny 2\n' \
          '  - You will need to complete group/team challenges.\n' \
          '4. Playing\n' \
          '  - You will receive challenges, these challenges award special crafting materials and test your strength, teamwork, and knowledge.\n' \
          '  - Challenges range from combat, wolfpack knowledge, to teamwork. There is no penalty for failing however no awards will be given for "stale" challenges (admins discretion)\n' \
          '  - Use these crafting materials to craft Boons, Marks, or create "The Call".\n' \
          '  - Using "The Call" summons a much: harder "Trial" challenge.\n' \
          '  - Complete all 3 trials to beat The Wilds and earn your reward.\n' \
          '  - all in game challenges must be verified using a picture/video/eye witness posted to the Wilds chat room. Admins will award you materials if they deem you succeeded.\n\n' \
          "Wilds Commands:\n" \
          "```tdt$craft         Craft item for The Wilds\n" \
          "tdt$item_check    <member (optional)> Prints member's items.\n" \
          "tdt$stat_check    <member (optional)> Prints member's stats.\n" \
          "tdt$use_item      Use item for The Wilds\n" \
          "tdt$wolf          <member (optional)> starts enrollment into the wilds.```"
    channel = member.dm_channel
    if not channel:
        await member.create_dm()
        channel = member.dm_channel
    await channel.send(msg.format(member))


class Item:
    def __init__(self, name, cost, description):
        self.name = name
        self.cost = cost
        self.description = description

    def blerb(self):
        out = '**{}**\n{}\nCost to make: '.format(self.name, self.description)
        out += ', '.join(['{} {}'.format(self.cost[i], i) for i in self.cost])
        return out


_items = [Item("The Call", {"strength": 6, "spirit": 6, "wit": 6}, "Beckon a Trial..."),
          Item("Boon of Preparation", {"strength": 3, "spirit": 1, "wit": 1}, "Victories "
               "award double materials for the next several challenges (Doesn't stack)"),
          Item("Boon of Companions", {"strength": 1, "spirit": 1, "wit": 3}, "Admins "
               "will grant one random TDT Member and one Community member access to the "
               "wilds chat room for a few hours, they can complete challenges for you as "
               "well."),
          Item("Boon of Light", {"strength": 1, "spirit": 3, "wit": 1}, "Makes any "
               "active trial slightly easier (stackable)."),
          Item("Mark of the Trial", {"strength": 2, "spirit": 2, "wit": 2}, "Adds "
               "additional daily challenges for ALL Lone Wolves for a few hours.")
          ]
_items = {i.name: i for i in _items}


class Challenge:
    def __init__(self, name, reward, tasks, stale_last=False, stale_after=None, weight=1):
        self.name = name
        self.reward = reward
        self.tasks = tasks
        self.weight = weight
        self.stale_last = stale_last
        self.stale_after = stale_after
        self._last = None

    def task_text(self, task=None):
        reward = ', '.join(['{} {}'.format(self.reward[i], i) for i in self.reward])
        if task is None:
            task = random.choice(self.tasks)
        return '**{}** (awards {})\n{}'.format(self.name, reward, task)

    def pick_n_tasks(self, n=None):
        out = [self.task_text(i) for i in self.tasks]
        random.shuffle(out)
        return out[:n]

    async def react(self, msg):
        await asyncio.sleep(self.stale_after)
        await msg.add_reaction(_stale)

    async def send_to(self, channel, bot_config, loop, task=None):
        if task is None:
            task = self.task_text()
        msg = await channel.send(task)
        if self.stale_last:
            if self._last is None:
                key = 'tdt.the_wilds.' + self.name.replace(' ', '_')
                tmp = int(bot_config.set_if_not_set(key, 0))
                if tmp:
                    self._last = tmp
            if self._last:
                last = await channel.fetch_message(self._last)
                await last.add_reaction(_stale)
            self._last = msg.id
        if self.stale_after:
            loop.create_task(self.react(msg))
        return msg

    async def send_multiple(self, channel, bot_config, loop, n):
        for t in self.pick_n_tasks(n):
            await self.send_to(channel, bot_config, loop, task=t)


_challenges = [Challenge("Of Body", {"strength": 2},
                         ["Win a game where you scored a 5.0 KD or better and were in the top 3 players",
                          "Win a game where you scored 35 kills or more",
                          "Win 2 comp matches",
                          "Win 2 elims top fragging each",
                          'Score a "we ran" medal',
                          'Score an "undefeated" medal',
                          'Score a "ghost in the night" medal.'],
                         stale_after=24 * _hour, weight=0
                         ),
               Challenge("Of Mind", {"wit": 2},
                         ['What is the position of the Alpha?',
                          'What are the responsibilities of the Alpha?',
                          'What is the position of the Beta?',
                          'What are the responsibilities of the Beta?',
                          'What is the position of the Gamma?',
                          'What are the responsibilities of the Gamma?',
                          'What is the position of the Omega?',
                          'What are the responsibilities of the Omega?',
                          'What is "Call this to a friendly who is unable to be covered or has left the team formation without calling it out."?',
                          'What is "Call to signal a swap in responsibility or current position in order to maintain pressure or regain health."?',
                          'What is "Call this when you or your team is being flanked while in an engagement. Destroy the threat as quickly and as efficiently as possible."?',
                          'What is "Call out to denote a high threat target. Call if your planning on retreating or burning."?',
                          'What is "a state of health when someone is over 50% health."',
                          'What is "a state of health when someone is under 50% health."',
                          'In a "Suppress and Flank" who *primarily* is responsible for the flank, what call out must they give and when?',
                          'In a "Suppress and Flank" who *primarily* is responsible for the suppression, what call out must they give and when?',
                          'What is "a defensive tactic in which the team positions in cover and each covers a different zone."?',
                          'In an alamo, where should Alphas and Betas be located in terms of their team and their enemies location?',
                          'When is it time to change coverage points in an Alamo?',
                          'What is "an aggressive engagement tactic to take over a space. All units leap-frog from cover to cover to over take a zone"?',
                          'What is "An aggressive strategy in which all members call a location and YEET a grenade at a enemy location of cover."?',
                          'What is "A defensive tactic in which a back line player waits looking at a lane in an area where a front line player is battling. The front line player drags the fight into the line of sight of the back line player."?'],
                         stale_last=True, weight=1
                         ),
               Challenge("Of Soul", {"spirit": 2},
                         ["Win a game where you and your fireteam all have 3.0's or higher (minimum 3 players)",
                          'Win a game of Control where B is kept neutral the whole game.',
                          'Win a game of comp where you only use blue tier (or lower) weaponry (must have at least one other fireteam member with you)',
                          'Win a game of elim where you have your HUD disabled (must have at least one other fireteam member with you)',
                          'Win a game where a fireteam member scores a undefeated medal.',
                          'Win a game where no one else in your fireteam speaks except you (minimum 3 players)'],
                         stale_after=24 * _hour, weight=0
                         )
               ]
_c_weights = [c.weight for c in _challenges]


class Participant:
    """Class for The Wilds participant"""
    _stat_base = 'tdt.the_wilds.stat.'
    _item_base = 'tdt.the_wilds.item.'
    stat_names = ["strength", "spirit", "wit"]

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


class Wilds(commands.Cog):
    """Cog for The Wilds/Trials of the Wolf"""
    def __init__(self, bot, tmin=_tmin, tmax=_tmax):
        self.bot = bot
        self.tmin = tmin
        self.tmax = tmax
        self._participants = {}
        self._init = False
        self._active_message_id = None
        self._configs = dict()

    def __getitem__(self, key):
        try:
            return self._participants[key.id]
        except KeyError:
            self._participants[key.id] = Participant(self.bot, key)
            return self._participants[key.id]
        except AttributeError:
            return self._participants[key]

    def __contains__(self, item):
        if item in self._participants:
            return True
        try:
            return item.id in self._participants
        except AttributeError:
            return item in self._participants

    def init_daily_bounties(self):
        self.bot.loop.create_task(self.post_daily_bounty(tomorrow=True))

    async def post_daily_bounty(self, additional=False, tomorrow=False):
        tz = pytz.timezone(param.rc('timezone'))
        if tomorrow:
            nt = next_time(_dday, tz=tz)
            # now = datetime.datetime.now()
            # print(nt, '|',  now, '|',  nt - now, '|', tz)
            await wait_until(nt)
        now = datetime.datetime.now().astimezone(tz).replace(tzinfo=None)
        if additional:
            date = now.strftime("%B %d, %Y (%X)")
            await self.channel.send('**Bonus Bounties for {:}**'.format(date))
        else:
            date = now.strftime("%B %d, %Y")
            await self.channel.send('**Daily Challenges for {:}**'.format(date))
        for c in _challenges:
            if c.name in ["Of Body", "Of Soul"]:
                await c.send_multiple(self.channel, self._get_config(self.bot.user),
                                      self.bot.loop, 3)
        if not additional:
            await self.post_daily_bounty(tomorrow=True)

    @property
    def message_id(self):
        if self._active_message_id is None:
            try:
                self._active_message_id = self._get_config(self.bot.user).set_if_not_set(_bot, 0)
            except AttributeError:
                self._active_message_id = None
        return self._active_message_id

    async def enroll(self, user, guild=None):
        if guild is not None:
            role = find_role(guild, "Lone Wolf")
            if role:
                user = await guild.fetch_member(user.id)
                await user.add_roles(role)
        self._participants[user.id] = Participant(self.bot, user, guild=guild)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Parse reaction adds for agreeing to code of conduct and rank them up to
        Recruit"""
        # if not code of conduct message
        if payload.message_id is not None:
            return

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages for new event post"""
        # ignore all messages from our bot
        if message.author == self.bot.user:
            return
        await self._do_init()

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self._do_init()

    def _is_stale(self, m):
        if m.author != self.bot.user:
            return False
        challenge = None
        for c in _challenges:
            if c.name in m.content:
                challenge = c
                break
        if challenge is None:
            return False
        dt = (datetime.datetime.utcnow() - m.created_at).total_seconds()
        if challenge.stale_after:
            if dt > challenge.stale_after:
                return True
        if dt > 24 * _hour:
            return True
        return False

    async def _do_init(self):
        """Initialization involving asynchronous functions"""
        # if we have not run this function yet
        if not self._init:
            # make sure we have the challenge messages going
            self._init = True
            self.init_daily_bounties()
            msg = await self._get_message()
            if not msg:
                await self.send_message()
                return
            dt = int((datetime.datetime.utcnow() - msg.created_at).total_seconds())
            dt = random.randint(self.tmin, self.tmax) - dt
            await self.send_message(dt)
            # react to stale challenges
            async for m in self.channel.history(limit=500):
                if self._is_stale(m):
                    await m.add_reaction(_stale)
            return
        # if we have not yet sent out a challenge
        if not self.message_id:
            await self.send_message(dt=True)
            return
        # if our challenge message is too old
        msg = await self._get_message()
        if msg:
            dt = int((datetime.datetime.utcnow() - msg.created_at).total_seconds())
            if dt > self.tmax + 1:
                await self.send_message()
                return

    @property
    def role(self):
        return find_role(self.channel.guild, _role)

    @property
    def channel(self):
        return self.bot.find_channel(_channel)

    def cog_check(self, ctx):
        if ctx.command.name in ['wolf', 'challenger']:
            return True
        if ctx.channel == self.channel:
            return True
        return ctx.channel == self.bot.find_channel(param.rc('log_channel'))

    def _get_config(self, user):
        try:
            return self._configs[user.id]
        except KeyError:
            self._configs[user.id] = UserConfig(user)
            return self._configs[user.id]

    @commands.command()
    async def wolf(self, ctx, channel: discord.TextChannel = None):
        """<member (optional)> starts enrollment into the wilds"""
        await send_wilds_info(ctx.author)
        admin = find_role(self.channel.guild, "admin")
        if channel is None:
            channel = self.bot.find_channel(param.rc("main_channel", "general_chat"))
        txt = "{:} has entered the wolf command. {:} please ensure they are serious in " \
              "the {:}.".format(ctx.author.display_name, admin.mention, channel.mention)
        debugging = self.bot.find_channel(param.rc('log_channel'))
        await debugging.send(txt)

    @commands.command()
    @commands.check(admin_check)
    async def challenger(self, ctx, member: discord.Member):
        """<member> Enrols member in the Wilds."""
        # todo: ask Mesome what he want's this to do
        top_role = member.top_role.name
        await self.enroll(member, guild=ctx.guild)
        channel = self.bot.find_channel(param.rc('log_channel'))
        await channel.send('Enrolled {} ({}) into The Wilds'.format(member.display_name, top_role))
        await self.channel.send('{} has entered The Wilds and may only attempt challenges from after this message.'.format(member.display_name))

    @commands.command()
    @commands.check(admin_check)
    async def stat_adjust(self, ctx, member: discord.User, strength: int, spirit: int,
                          wit: int):
        """<member> <strength> <spirit> <wit> adds stat points to member"""
        player: Participant = self[member]
        for i, stat in enumerate(player.stat_names):
            try:
                player[stat] += [strength, spirit, wit][i]
            except ValueError:
                msg = "Cannot set {:} below zero, setting it to zero instead.".format(stat)
                player[stat] = 0
                await ctx.send(msg)
        msg = '{} current stats:\n{}'.format(member.display_name, player.stat_str())
        await self.channel.send(msg)

    @commands.command()
    @commands.check(admin_check)
    async def stealth_stat_adjust(self, ctx, member: discord.User, strength: int,
                                  spirit: int, wit: int):
        """<member> <strength> <spirit> <wit> adds stat points to member"""
        player: Participant = self[member]
        for i, stat in enumerate(player.stat_names):
            try:
                player[stat] += [strength, spirit, wit][i]
            except ValueError:
                msg = "Cannot set {:} below zero, setting it to zero instead.".format(
                    stat)
                player[stat] = 0
                await ctx.send(msg)
        msg = '{} current stats:\n{}'.format(member.display_name, player.stat_str())
        channel = self.bot.find_channel(param.rc('log_channel'))
        await channel.send(msg)

    @commands.command()
    async def stat_check(self, ctx, member: discord.User = None):
        """<member (optional)> Prints member's stats."""
        if not member:
            member = ctx.author
        player: Participant = self[member]
        msg = '{} current stats:\n{}'.format(member.display_name, player.stat_str())
        await ctx.send(msg)

    @commands.command()
    async def item_check(self, ctx, member: discord.User = None):
        """<member (optional)> Prints member's items."""
        if not member:
            member = ctx.author
        player: Participant = self[member]
        msg = '{} current items:\n{}'.format(member.display_name, player.item_str())
        await ctx.send(msg)

    @commands.command()
    async def craft(self, ctx, *args):
        """Craft item for The Wilds"""
        if not args:
            await split_send(ctx, [i.blerb() for i in _items.values()])
            return
        arg = ' '.join([str(i) for i in args]).strip().lower()
        if arg == 'help':
            await split_send(ctx, [i.blerb() for i in _items.values()])
            return
        items_lower = {i.lower(): i for i in _items.keys()}
        if arg in _items:
            item = arg
        elif arg.lower() in items_lower:
            item = items_lower[arg]
        else:
            await ctx.send("Unknown item: {:}".format(arg))
            await split_send(ctx, [i.blerb() for i in _items.values()])
            return
        item = _items[item]
        player = self[ctx.author]
        for i in item.cost:
            if player[i] < item.cost[i]:
                args = ctx.author.display_name, player[i], i, item.cost[i], item.name
                msg = '{} has {} {} but {} is required to make {}'.format(*args)
                await ctx.send(msg)
                return
        for i in item.cost:
            player[i] -= item.cost[i]
        player[item.name] += 1
        await ctx.send('{} has crafted {}'.format(ctx.author.display_name, item.name))
        return

    async def _get_message(self):
        if self.message_id:
            try:
                return await self.channel.fetch_message(self.message_id)
            except discord.NotFound:
                self._set_msg_id(0)

    def _set_msg_id(self, idn):
        old = self.message_id
        self._active_message_id = idn
        self._get_config(self.bot.user)[_bot] = idn
        return old

    async def send_message(self, dt=0, set_timer=True, n=None):
        if n is not None:
            if n <= 0:
                return
            n -= 1
        if dt is True:
            dt = random.randint(self.tmin, self.tmax)
        role = find_role(self.channel.guild, "Lone Wolf")
        if not role.members:
            return
        logger.debug('Wilds.send_message waiting for {:} s'.format(dt))
        await sleep(dt)
        challenge = random.choices(_challenges, weights=_c_weights)[0]
        msg = await challenge.send_to(self.channel, self._get_config(self.bot.user),
                                      self.bot.loop)
        self._set_msg_id(msg.id)
        if set_timer == 0:
            set_timer = .01
        if set_timer:
            self.send_later(dt=set_timer, set_timer=set_timer, n=n)

    def send_later(self, **kwargs):
        self.bot.loop.create_task(self.send_message(**kwargs))

    @commands.command()
    @commands.check(admin_check)
    async def wilds_send(self, ctx, *args):
        """Send a message to the wilds"""
        arg = ' '.join([str(i) for i in args]).strip()
        await self.channel.send('"' + arg + '"')

    @commands.command()
    async def use_item(self, ctx, *args):
        """Use item for The Wilds"""
        if not args:
            return await self.craft(ctx)
        arg = ' '.join([str(i) for i in args]).strip().lower()
        if arg == 'help':
            return await self.craft(ctx)
        items_lower = {i.lower(): i for i in _items.keys()}
        if arg in _items:
            item = arg
        elif arg.lower() in items_lower:
            item = items_lower[arg]
        else:
            ctx.send("Unknown item: {:}".format(arg))
            return
        player = self[ctx.author]
        _i = item
        item = _items[item]
        if player[_i] <= 0:
            args = ctx.author.display_name, item.name
            msg = '{} does not have and {}'.format(*args)
            ctx.send(msg)
            return
        player[_i] -= 1
        msg = '{} has used {} and has {} remianing'
        msg = msg.format(ctx.author.display_name, item.name, player[_i])
        await ctx.send(msg)
        admin = find_role(self.channel.guild, "admin")
        channel = self.bot.find_channel(param.rc('log_channel'))
        await channel.send(msg + ' ' + admin.mention)
        if item.name == "Mark of the Trial":
            await self.post_daily_bounty(additional=True)
        return

    @commands.command()
    @commands.check(admin_check)
    async def clear_wilds(self, ctx):
        """Clears the wilds chat"""
        await self.channel.purge(limit=200)

    @commands.command()
    @commands.check(admin_check)
    async def give_item(self, ctx, member: discord.User = None, *args):
        """<member> <item>; gives a member an item"""
        if not args:
            await split_send(ctx, [i.blerb() for i in _items.values()])
            return
        arg = ' '.join([str(i) for i in args]).strip().lower()
        if arg == 'help':
            await split_send(ctx, [i.blerb() for i in _items.values()])
            return
        items_lower = {i.lower(): i for i in _items.keys()}
        if arg in _items:
            item = arg
        elif arg.lower() in items_lower:
            item = items_lower[arg]
        else:
            await ctx.send("Unknown item: {:}".format(arg))
            await split_send(ctx, [i.blerb() for i in _items.values()])
            return
        item = _items[item]
        player = self[member]
        player[item.name] += 1
        await ctx.send('{} has been given {}'.format(member.display_name, item.name))
        return

    @commands.command()
    @commands.check(admin_check)
    async def print_wilds_user_stats(self, ctx, member: discord.User = None):
        """<user (optional)>; Prints user's wilds stats"""
        player = self[member]
        prefix = _bot + '.'
        n = len(prefix)
        out = {i[n:]: player[i] for i in player if i.startswith(prefix)}
        await ctx.send(str(out))

    @commands.command()
    @commands.check(admin_check)
    async def set_wilds_user_stat(self, ctx, member: discord.User, key, value):
        """<user> <key> <value>"""
        player = self[member]
        t = type(player[key])
        player[key] = t(value)
        await ctx.send("{:}[{:}] set to {:}".format(member.display_name, key, value))

    @commands.command()
    @commands.check(admin_check)
    async def post_wilds_help(self, ctx):
        """Post Wilds Help"""
        # await self.bot.help_command.
        pass


if usingV2:
    async def setup(bot):
        return
        cog = Wilds(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        return
        bot.add_cog(Wilds(bot))
