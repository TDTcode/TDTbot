import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import asyncio
from .. import param  # roles
from ..helpers import find_role
from ..async_helpers import split_send
from ..version import usingV2
import logging
import re


logger = logging.getLogger('discord.' + __name__)
BAN_TDT = False  # set to True to ban members with 'tdt' in their name


# below are unacceptable words and phrases
_bad_words = ['fag', 'faggot', 'nigger', 'nigga', "debug_testing_bad_word"]
_discord_link = r'\b(https:\/\/)?discord\.gg(\/\w+)\b'
_searches = [r'(?i)\bkill\byourself\b',
             _discord_link,
             ]
_searches += [r'(?i)\b{:}[s]?\b'.format(i) for i in _bad_words]


class _Spam():
    def __init__(self, author=None, content=None, log_msg=None, count=0):
        self.author = author
        self.content = content
        self.log_msg = log_msg
        self.count = count

    def __eq__(self, message):
        return self.author == message.author.id and self.content == message.content


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._log_channel = None
        self._init = False
        self._mentions = None
        self._coc_link = None
        self._last_spam = None

    async def _async_init(self):
        if self._init:
            return
        self.log_channel
        self.mentions
        self._init = True

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self._async_init()

    @property
    def mentions(self):
        if self._mentions is None:
            self._mentions = " ".join([find_role(self.bot.tdt(), i).mention
                                      for i in ["admin", "devoted"]])
        return self._mentions

    @property
    def log_channel(self):
        if self._log_channel is None:
            self._log_channel = self.bot.find_channel(param.rc('log_channel'))
        return self._log_channel

    async def fetch_coc_link(self):
        if self._coc_link:
            return self._coc_link
        channel = self.bot.find_channel('manual_page')
        msg = await channel.fetch_message(param.messages.CoC)
        self._coc_link = msg.jump_url
        return self._coc_link

    @commands.Cog.listener()
    async def on_message(self, message):
        # ignore messages from this bot
        if message.author == self.bot.user:
            return
        if message.channel.id == param.channels.banning_channel:
            msg = ["Auto banning message ({:}):".format(message.channel.mention),
                   "```{:}```".format(message.content),
                   "From: {:} ({:}, {:})".format(message.author.mention, message.author.name, message.author.id),
                   ]
            await split_send(self.log_channel, msg)
            await message.delete()
            await message.author.ban(reason="Auto ban: message in banning channel")
            return
        # ignore commands
        try:
            if message.content.startswith(self.bot.command_prefix):
                return
        except TypeError:
            for prefix in self.bot.command_prefix:
                if message.content.startswith(prefix):
                    return
        for search in _searches:
            if re.search(search, message.content):
                if self._last_spam:
                    if self._last_spam == message:
                        self._last_spam.count += 1
                        if self._last_spam.count <= 11:
                            if self._last_spam.count == 2:
                                await self._last_spam.log_msg.add_reaction("1️⃣")
                            emoji = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣🔟➕"[self._last_spam.count]
                            await self._last_spam.log_msg.add_reaction(emoji)
                        await message.delete()
                        if self._last_spam.count >= 5:
                            msg = "Repeated spam from {:} has been deleted; this will auto-ban in the future."
                            log_msg = self._last_spam.log_msg
                            await log_msg.reply(msg.format(message.author.mention))
                            return
                            await message.author.ban(reason="Repeated spam")
                            await self._last_spam.log_msg.add_reaction("🔨")
                        return
                if search == _discord_link:
                    if message.channel.id in [param.channels.tdt_events,
                                              param.channels.content_hub]:
                        return
                msg = ["I have parsed this message as spam as against the CoC and deleted it:",
                       "```{:}```".format(message.content),
                       "From: {:} ({:}, {:})".format(message.author.mention, message.author.name, message.author.id),
                       "In: {:} ({:})".format(message.channel.mention, message.channel.name),
                       "{:}".format(self.mentions),
                       ]
                log_msg = (await split_send(self.log_channel, msg))[-1]
                msg = "I have parsed this message as spam as against the Code of Conduct (CoC) and deleted it.\n"
                msg += "Please read the CoC: " + await self.fetch_coc_link()
                await message.channel.send(msg, reference=message)
                self._last_spam = _Spam(message.author.id, message.content, log_msg, 1)
                await message.delete()
                return

    @commands.Cog.listener()
    async def on_member_join(self, member):
        names = [member.name, member.display_name, member.nick]
        names = [i for i in names if isinstance(i, str)]
        for name in names:
            token = name.lower()
            for i in "-_ ":
                token = token.replace(i, "")
            if re.match(r"^([\d_\s\-]+)?tdt", token):
                roles = [find_role(self.log_channel.guild, i).mention for i in ["admin", "devoted"]]
                msg = ' '.join(roles)
                msg += "\nI have detected a new member with 'tdt' in their name: {:} ({:})"
                if not BAN_TDT:
                    msg += "\n\nPlease check their account for legitimacy."
                    msg += "\nYou can right click (or long press) on the mention to initiate a ban."
                    await self.log_channel.send(msg.format(member.mention, member.id))
                else:
                    msg += "\nBanning them now."
                    await self.log_channel.send(msg.format(member.mention, member.id))
                    await member.ban(reason="Intimidating TDT")
                break


if usingV2:
    async def setup(bot):
        cog = AutoMod(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(AutoMod(bot))
