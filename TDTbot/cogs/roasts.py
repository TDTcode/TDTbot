import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import datetime
import logging
import random
import re
import sys
from .. import param
from ..helpers import find_channel
from ..async_helpers import admin_check
from ..version import usingV2

logger = logging.getLogger('discord.' + __name__)
_m_delete = discord.AuditLogAction.message_delete
_min = datetime.timedelta(seconds=60)


def roast_str():
    """Randomly pull a roast from the roasts list"""
    return random.choice(param.rc('roasts'))


class RoastButton(discord.ui.Button['RoastView']):
    def __init__(self, channel: discord.TextChannel, count: int = 1):
        if count < 4:
            style = discord.ButtonStyle.red
        elif count < 7:
            style = discord.ButtonStyle.gray
        elif count < 11:
            style = discord.ButtonStyle.blurple
        else:
            style = discord.ButtonStyle.green
        label = f'Roast {channel.name} ({count})'
        super().__init__(style=style, label=label, emoji='🔥')

    async def callback(self, interaction: discord.Interaction):
        if self.view.count > 0:
            cog: "Roast" = self.view.cog
            self.view.count -= 1
            self.view.add_buttons()
            try:
                await interaction.response.edit_message(view=self.view)
            except discord.errors.NotFound:
                pass
            finally:
                await cog._send_roast(self.view.channel, sender=interaction.user)
        if self.view.count <= 0:
            self.view.stop()
            await interaction.delete_original_response()


class RoastView(discord.ui.View):
    """A view that prompts the user to select an action."""
    def __init__(self, cog: "Roast", channel: discord.TextChannel, count: int = 1):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel = channel
        self.count = count
        self.add_buttons()

    def add_buttons(self):
        self.clear_items()
        self.add_item(RoastButton(self.channel, self.count))


class Roast(commands.Cog):
    """Cog to roast people"""

    def __init__(self, bot):
        self.bot = bot
        self._nemeses = [i for i in param.rc('nemeses')]
        self._last_roast = None
        self._snipes = dict()
        self._botting = dict()
        self._react_snipe = dict()
        self._roasts = []

    def _log_roast(self, mid):
        while sys.getsizeof(self._roasts) > 1048576:
            self._roasts.pop(0)
        self._roasts.append(mid)

    async def _send_roast(self, channel, prefix=None, parse_ignore=True, sender=None,
                          last=None, roast=None):
        if parse_ignore and channel.name in param.rc('ignore_list', []):
            return
        if sender is not None:
            perm = channel.permissions_for(sender)
            if not perm.send_messages:
                msg = '{:} does not have send privileges in {:}.'
                raise discord.Forbidden(msg.format(sender, channel))
        msg = roast_str() if roast is None else roast
        if prefix is not None:
            msg = prefix.rstrip() + ' ' + msg
        if isinstance(last, discord.Message):
            msg = await last.reply(msg)
        else:
            msg = await channel.send(msg)
        self._log_roast(msg.id)
        if last is not None:
            self._last_roast = last
        return True

    async def cog_check(self, ctx):
        """Don't allow everyone to access this cog"""
        return await admin_check(ctx)

    @commands.command(aliases=['burn'])
    async def roast(self, ctx, channel: discord.TextChannel = None, guild: str = None):
        """<channel (optional)> <server (optional)> sends random roast message"""
        if guild is None:
            guild = ctx.guild
        else:
            try:
                guild = [i for i in self.bot.guilds if i.name == guild][0]
            except IndexError:
                ctx.send('ERROR: server "{0}" not found.'.format(guild))
                return
        if channel:
            channel = find_channel(guild, channel)
        else:
            channel = ctx.channel
        last = await channel.fetch_message(channel.last_message_id)
        await self._send_roast(channel, parse_ignore=False, sender=ctx.author, last=last)

    @commands.command()
    async def nou(self, ctx, channel: discord.TextChannel = None, guild: str = None):
        """<channel (optional)> <server (optional)> NO U"""
        if guild is None:
            guild = ctx.guild
        else:
            try:
                guild = [i for i in self.bot.guilds if i.name == guild][0]
            except IndexError:
                ctx.send("NO U (need to type a reasonable server name)")
                return
        if channel:
            channel = find_channel(guild, channel)
        else:
            channel = ctx.channel
        await self._send_roast(channel, parse_ignore=False, sender=ctx.author,
                               roast="NO U")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.message_id in self._roasts:
            now = datetime.datetime.utcnow().replace(tzinfo=None)
            guild = await self.bot.fetch_guild(payload.guild_id)
            opt = dict(action=_m_delete, after=now - _min)
            out = []
            async for entry in guild.audit_logs(**opt):
                if abs(entry.created_at - now) < _min:
                    if entry.target == self.bot.user:
                        if entry.extra.channel.id == payload.channel_id:
                            if entry.user not in [self.bot.owner, guild.owner]:
                                out.append([entry.user, abs(now - entry.created_at)])
            if out:
                user = sorted(out, key=lambda x: x[1])[0][0]
                channel = await self.bot.fetch_channel(payload.channel_id)
                await self._send_roast(channel, prefix=user.mention)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages to see if we should roast even without a command"""
        # ignore commands
        try:
            if message.content.startswith(self.bot.command_prefix):
                return
        except TypeError:
            for prefix in self.bot.command_prefix:
                if message.content.startswith(prefix):
                    return
        # ignore messages from this bot
        if message.author == self.bot.user:
            return
        # if author in botting
        try:
            if self._botting[message.author.id] > 0:
                await message.add_reaction("🤖")
                self._botting[message.author.id] -= 1
            if self._botting[message.author.id] <= 0:
                self._botting.pop(message.author.id)
        except KeyError:
            pass
        # if author in react_snipe
        try:
            if self._react_snipe[message.author.id][1] > 0:
                await message.add_reaction(self._react_snipe[message.author.id][0])
                self._react_snipe[message.author.id][1] -= 1
            if self._react_snipe[message.author.id][1] <= 0:
                self._react_snipe.pop(message.author.id)
        except KeyError:
            pass
        # if author in snipes
        try:
            if self._snipes[message.author.id] > 0:
                if await self._send_roast(message.channel, last=message):
                    self._snipes[message.author.id] -= 1
            if self._snipes[message.author.id] <= 0:
                self._snipes.pop(message.author.id)
            return
        except KeyError:
            pass
        # set a trigger list for sending roasts
        triggers = ['<:lenny:333101455856762890> <:OGTriggered:433210982647595019>']
        # if some trigger then roast
        if message.content.strip() in triggers:
            if not random.randrange(3):
                logger.debug('Ignoring trigger')
                return
            await self._send_roast(message.channel, last=message)
            return
        if '🍞' in message.content.strip():
            if random.randrange(3):
                logger.debug('Ignoring trigger')
            else:
                await self._send_roast(message.channel, last=message)
                return
        # respond to any form of REEE
        if re.match('^[rR]+[Ee][Ee]+$', message.content.strip()):
            r = random.randrange(7)
            if r < 2:
                logger.debug('Ignoring trigger')
                return
            if r < 4:
                await self._send_roast(message.channel, last=message, roast="NO U")
            else:
                await self._send_roast(message.channel, last=message)
            return
        old = self._last_roast
        if old:
            # if the message author is the last person we roasted and in the same channel
            if message.author == old.author and message.channel == old.channel:
                # if this message is < 1 min from the last one
                if (message.created_at - old.created_at).total_seconds() < 120:
                    if (message.content.lower().strip() in ['omg', 'bruh']
                            or re.findall('aaa+', message.content.lower())):
                        await self._send_roast(message.channel)
                        self._last_roast = None
                        return
                    self._last_roast = None
        # if the nemesis of this bot posts a non command message
        try:
            if message.author.id in self._nemeses:
                logger.debug('Nemesis: {0.author}'.format(message))
                # if nemesis posts boomer type word
                if re.findall('[bz]oome[rt]', message.content.lower()):
                    logger.debug('[bz]oome[rt]')
                    if random.randrange(2):
                        logger.debug('Ignoring trigger')
                        return
                    if not random.randrange(3):  # 1/3 prob
                        logger.debug('roast')
                        await self._send_roast(message.channel, last=message)
                    else:  # 2/3 prob
                        logger.debug('no u')
                        await self._send_roast(message.channel, last=message,
                                               roast="NO U")
                    return
                # regex list of triggers
                matches = ['your m[ao]m', 'shut it bot', 'aaa+']
                for m in matches:
                    if random.randrange(2):
                        logger.debug('Ignoring trigger')
                        return
                    if re.findall(m, message.content.lower()):
                        logger.debug('Nemesis message matched "{:}"'.format(m))
                        await self._send_roast(message.channel, last=message)
                        return
                # Roast nemesis with 1/30 probability
                if not random.randrange(30):
                    logger.info("Decided to roast nemesis.")
                    await self._send_roast(message.channel, last=message)
                    return
        # catch self._nemeses = None
        except TypeError:
            pass
        return

    @commands.command(hidden=True)
    @commands.check(admin_check)
    async def roast_snipe(self, ctx, user: discord.User, n: int = 1):
        """<user> <int (optional:1)> - Roast a user n times"""
        self._snipes[user.id] = n
        if self._snipes[user.id] <= 0:
            self._snipes.pop(user.id)

    @commands.command(hidden=True)
    @commands.check(admin_check)
    async def you_are_a_bot(self, ctx, user: discord.User, n: int = 1):
        """<user> <int (optional:1)> - Bot a user n times"""
        self._botting[user.id] = n
        if self._botting[user.id] <= 0:
            self._botting.pop(user.id)

    @commands.command(hidden=True)
    @commands.check(admin_check)
    async def react_snipe(self, ctx, user: discord.User, emoji: discord.Emoji,
                          n: int = 1):
        """<user> <emoji> <int (optional:1)> - React to user with emoji n times"""
        self._react_snipe[user.id] = [emoji, n]
        if self._react_snipe[user.id][1] <= 0:
            self._react_snipe.pop(user.id)

    @commands.command(hidden=True)
    @commands.check(admin_check)
    async def roast_button(self, ctx, channel: discord.TextChannel, count: int = 1):
        """<channel> <int (optional:1)> - Create a button to roast a channel"""
        view = RoastView(self, channel, count)
        await ctx.send('Roast button:', view=view)


if usingV2:
    async def setup(bot):
        cog = Roast(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(Roast(bot))
