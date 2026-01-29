import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import datetime
import logging
import numpy as np
from ..helpers import parse_message, find_role
from ..async_helpers import split_send
from ..config import UserConfig
from ..version import usingV2


logger = logging.getLogger('discord.' + __name__)

_channel = 'dresstiny'
_role = 'Dresstiny'
_rule_id = 778026917802410014
_bot_key = 'tdt.fashion.entries.2022'
_emoji = '<:StrangeCoin:319276617727737866>'


class _Entry:
    # emotes = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
    emotes = ['👎', '👍']
    _scores = np.arange(len(emotes), dtype=int) + (0 if len(emotes) == 2 else 1)

    def __init__(self, message_id, author_id, cog):
        self.id = message_id
        self.author_id = author_id
        self.key = ':'.join([str(i) for i in [message_id, author_id]])
        self.cog = cog
        self._message = None
        self._retrieved = datetime.datetime.utcfromtimestamp(0)

    def __repr__(self):
        return '{} {}'.format(str(type(self)), self.key)

    def __eq__(self, other):
        return self.id == other.id and self.author_id == other.author_id

    async def message(self, dt_max=2.0):
        """Fetch and return the message associated with this event"""
        if self._message is None:
            self._retrieved = datetime.datetime.utcnow()
            try:
                self._message = await self.cog.channel.fetch_message(self.id)
            except discord.HTTPException:
                return None
        elif (datetime.datetime.utcnow() - self._retrieved).total_seconds() > dt_max:
            self._retrieved = datetime.datetime.utcnow()
            try:
                self._message = await self.cog.channel.fetch_message(self.id)
            except discord.HTTPException:
                return None
        return self._message

    async def name(self, message=None):
        if message is None:
            message = await self.message()
        if message is None:
            return None
        if message.content:
            return message.content.split(':')[-1]
        data = parse_message(message)
        for i in data['attachments']:
            if i[-1].startswith('image/'):
                return i[0].filename
        out = str(message.created_at)
        return out

    async def votes(self, message=None):
        if message is None:
            message = await self.message()
        voted = []
        votes = np.zeros(len(self.emotes), dtype=int)
        for rxn in message.reactions:
            if rxn.emoji in self.emotes:
                users = [u async for u in rxn.users()
                         if u != self.cog.bot.user and u not in voted]
                votes[self.emotes.index(rxn.emoji)] += len(users)
                voted += users
        return votes

    async def add_reactions(self):
        msg = await self.message(dt_max=3.14e7)
        for i in self.emotes:
            await msg.add_reaction(i)

    async def score_stats(self, message=None):
        votes = await self.votes(message=message)
        try:
            mean = np.average(self._scores, weights=votes)
        except ZeroDivisionError:
            return dict(n=0, mean=0., votes=votes, std=np.nan, total=0)
        std = np.sqrt(np.average((self._scores - mean)**2, weights=votes))
        total = np.sum(self._scores * votes)
        out = dict(n=votes.sum(), mean=mean, votes=votes, std=std, total=total)
        return out

    async def _old_summary(self, data=None, message=None):
        if data is None:
            data = await self.score_stats(message=message)
        out = ", ".join(['{0:}: {1:}'.format(i, data[i]) for i in ['n', 'mean', 'total']])
        return out

    async def summary(self, data=None, message=None):
        if data is None:
            data = await self.score_stats(message=message)
        out = ", ".join(['{0:} x {1:}'.format(data['votes'][i], self.emotes[i]) for i in range(len(self.emotes))])
        return out


class FashionContest(commands.Cog):
    """Cog designed for fashion contest"""
    def __init__(self, bot):
        self.bot = bot
        self._channel = _channel
        self._entries = None
        self._bot_config = None
        self.bot.enroll_emoji_role({_emoji: _role}, message_id=_rule_id)

    @property
    def bot_config(self):
        if self._bot_config is None:
            self._bot_config = UserConfig(self.bot.user)
            self._bot_config.set_if_not_set(_bot_key, [])
        return self._bot_config

    @property
    def channel(self):
        out = self.bot.find_channel(_channel)
        # print(out)
        return out

    async def enroll_entry(self, entry):
        try:
            for e in self._entries:
                if entry == e:
                    return
        except TypeError:
            pass
        msg = await entry.message()
        if msg is None:
            return
        await entry.add_reactions()
        await msg.pin()
        try:
            self._entries.append(entry)
        except AttributeError:
            self._entries = [entry]
        if entry.key not in self.bot_config[_bot_key]:
            self.bot_config[_bot_key] += [entry.key]

    @property
    def role(self):
        return find_role(self.channel.guild, _role)

    async def _get_saved_entries(self):
        saved = self.bot_config[_bot_key]
        for i in saved:
            message_id, author_id = [int(j) for j in i.split(':')]
            try:
                if message_id not in [e.id for e in self._entries]:
                    await self.enroll_entry(_Entry(message_id, author_id, self))
            except TypeError:
                await self.enroll_entry(_Entry(message_id, author_id, self))

    async def _can_run(self, ctx):
        return ctx.channel == self.channel

    async def cog_check(self, ctx):
        return await self._can_run(ctx) or ctx.channel == self.bot.find_channel('debugging')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if not await self._can_run(message):
            return
        # if self._entries is None:
        #    await self._get_saved_entries()
        # await message.channel.send(str(message))
        data = parse_message(message)
        for i in data['type']:
            if i.startswith('image/'):
                await self.enroll_entry(_Entry(message.id, message.author.id, self))

    @commands.command()
    async def list_user_posts(self, ctx, member: discord.Member = None):
        """<member (optional)> lists member's entries"""
        await ctx.send('Please wait while I reload all the posts.')
        if member is None:
            member = ctx.author
        if self._entries is None:
            await self._get_saved_entries()
        entries = {i: (await e.message(dt_max=3.14e7)).created_at
                   for i, e in enumerate(self._entries) if e.author_id == member.id}
        ordered = sorted(entries, key=entries.get)
        fmt = '{:d}) {} - {}'
        txt = ['Posts from {:}:'.format(member.displayname)]
        for i, j in enumerate(ordered):
            e = self._entries[j]
            msg = await e.message()
            txt.append(fmt.format(i + 1, await e.name(message=msg),
                                  await e.summary(message=msg)))
        await split_send(ctx, txt, style="```")

    @commands.command()
    async def sort_posts(self, ctx, keyword: str = "total"):
        """<keyword=total> Sort all post by option keyword"""
        await ctx.send('Please wait while I reload all the posts.')
        _vote = keyword.startswith('votes[') and keyword.endswith(']')
        _index = None
        if _vote:
            _index = int(keyword.split('[')[1].rstrip(']'))

        async def value(entry: _Entry):
            data = await entry.score_stats()
            if _vote:
                out = data['votes'][_index]
            else:
                out = data[keyword]
            return out

        if self._entries is None:
            await self._get_saved_entries()
        entries = {i: await value(e) for i, e in enumerate(self._entries)}
        ordered = sorted(entries, key=entries.get, reverse=True)
        txt = []
        fmt = '{:d}) {}: {} - {}'
        for i, j in enumerate(ordered):
            e: _Entry = self._entries[j]
            msg = await e.message()
            name = await e.name(message=msg)
            data = await e.score_stats(message=msg)
            summary = await e.summary(data=data)
            if _vote:
                tmp = '{}: {}, '.format(e.emotes[_index], data['votes'][_index])
                summary = tmp + summary
            author = await self.channel.guild.fetch_member(e.author_id)
            txt.append(fmt.format(i + 1, author.display_name, name, summary))
        await split_send(ctx, txt, style="```")


if usingV2:
    async def setup(bot):
        cog = FashionContest(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(FashionContest(bot))
