import discord  # type: ignore
from discord.ext import commands  # type: ignore
import logging
# from typing import Tuple
from .. import param
from ..param import messages, roles, rc
from ..helpers import emotes_equal, find_channel
from ..async_helpers import admin_check, split_send
from ..version import usingV2


logger = logging.getLogger('discord.' + __name__)


async def _parings_perms(ctx=None, bot=None, author=None, guild=None):
    if author is None:
        if ctx is None:
            raise ValueError("Either ctx or author must be specified")
        author = ctx.author
    if guild is None:
        guild = ctx.guild
    logger.debug('parings_perms_check', author, getattr(author, "top_role", "NO_ROLE"))
    try:
        if author.top_role.id in [roles.admin, roles.devoted, roles.member]:
            return True
    except AttributeError:
        pass
    return False


class MainCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
        self._kicks = []
        self.bot.enroll_emoji_role({'👍': "Wit Challengers"}, message_id=809302963990429757)
        self.bot.enroll_emoji_role({'🏆': "Tourney Challengers"}, message_id=822744897505067018)
        self.bot.enroll_emoji_role(param.emoji2role, message_id=param.messages.CoC)
        try:
            with open(rc('art_file'), 'r') as f:
                msg = f.read()
            accept = msg.split('`')[1].strip().lower()
            for p in ".,?!;:":
                accept = accept.replace(p, '')
            self.bot.enroll_emoji_role({'🎨': param.roles.artist},
                                       message_id=param.messages.CoC,
                                       # Testing ##
                                       # send_message=msg,
                                       # accept_string='',
                                       target=param.roles.artist)
        except FileNotFoundError:
            logger.warning("Cannot find art file for emoji role, skipping.")
        _roles = ['alpha', 'beta', 'gamma', 'omega']
        _dict = {i: i for i in _roles}
        self.bot.enroll_emoji_role(_dict, message_id=messages.wolfpack, remove=_roles, min_role='Recruit')

    @commands.command()
    async def guild(self, ctx):
        """Prints guild/server name."""
        await ctx.channel.send(ctx.guild.name)

    @commands.command()
    async def hello(self, ctx, *, member: discord.Member = None):
        """<member (optional)> Says hello"""
        member = member or ctx.author
        if self._last_member is None or self._last_member.id != member.id:
            await ctx.send('Hello {0.name}!'.format(member))
        else:
            await ctx.send('Hello {0.name}... This feels familiar.'.format(member))
        self._last_member = member

    @commands.command()
    async def roles(self, ctx):
        """List server roles"""
        await ctx.send("\n".join([i.name for i in ctx.guild.roles
                                  if 'everyone' not in i.name]))

    @commands.command()
    async def bots(self, ctx):
        """Lists server bots"""
        bots = [m for m in ctx.guild.members if m.bot]
        # electro is a bot, so make sure he's included
        electro = await self.bot.get_or_fetch_user(param.users.electro, ctx.guild)
        if electro and electro not in bots:
            bots.insert(0, electro)
        # add other members to bots for fun
        adds = param.rc('add_bots')
        adds = [ctx.guild.get_member_named(i) for i in adds]
        adds = [i for i in adds if i and i not in bots]
        bots += adds
        # construct message
        msg = 'Listing bots for {0.guild}:\n'.format(ctx)
        msg += '\n'.join([str(i + 1) + ') ' + b.display_name for i, b in enumerate(bots)])
        await ctx.send(msg)

    async def emote(self, ctx, emote, n: int = 1, channel: discord.TextChannel = None,
                    guild: str = None):
        """emote <n (optional)> <channel (optional)> <server (optional)>
        posts emote"""
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
        n = min(10, n)
        msg = " ".join([emote] * n)
        await channel.send(msg)

    @commands.command()
    async def blob(self, ctx, n: int = 1, channel: discord.TextChannel = None,
                   guild: str = None):
        """<n (optional)> <channel (optional)> <server (optional)> posts dancing blob"""
        emote = "<a:blobDance:738431916910444644>"
        await self.emote(ctx, emote, n=n, channel=channel, guild=guild)

    @commands.command()
    async def vibe(self, ctx, n: int = 1, channel: discord.TextChannel = None, guild: str = None):
        """<n (optional)> <channel (optional)> <server (optional)> posts vibing cat"""
        emote = "<a:vibe:761582456867520532>"
        await self.emote(ctx, emote, n=n, channel=channel, guild=guild)

    @commands.command()
    async def karen_electro(self, ctx, n: int = 1, channel: discord.TextChannel = None, guild: str = None):
        """<n (optional)> <channel (optional)> <server (optional)> posts karen electro"""
        emote = "<:karen_electro:779088291496460300>"
        await self.emote(ctx, emote, n=n, channel=channel, guild=guild)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Template for message listeners"""
        # ignore messages from this bot
        if message.author == self.bot.user:
            return
        # ignore commands
        try:
            if message.content.startswith(self.bot.command_prefix):
                return
        except TypeError:
            for prefix in self.bot.command_prefix:
                if message.content.startswith(prefix):
                    return
        # Do something with the message below
        return

    @commands.command()
    @commands.check(admin_check)
    async def recruits(self, ctx, role: discord.Role = None):
        """<role (optional)> sorted list of recruit join dates (in UTC)."""
        if role is None:
            members = ctx.guild.members
        else:
            members = role.members
        data = dict()
        for member in members:
            data[member] = member.joined_at
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)
        msg = ['{0.display_name} {1}'.format(i[0], i[1].date().isoformat())
               for i in items]
        await split_send(ctx, msg, style='```')

    @commands.command()
    @commands.check(admin_check)
    async def add_roles(self, ctx, role: discord.Role, emote: str = None,
                        msg_id: int = None, channel: discord.abc.Messageable = None):
        """<role> <emote (optional)> <message id (optional)> <channel (optional)>
        For all members who have already reacted to given message with given emote,
        assign them the given role.

        Can be used as a reply to a message, in this case:
        <message id> defaults to the message that's being replied to.
        <emote> defaults to the emote with the most reactions.
        <channel> defaults to the channel where this command was entered."""

        ref = ctx.message.reference
        if channel is None:
            channel = ctx.channel
        msg = None
        if msg_id is not None:
            msg = await channel.fetch_message(msg_id)
        if msg is None and msg_id is None and ref:
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
        if not msg:
            raise ValueError("Cannot identify message.")
        rxns = sorted([rxn for rxn in msg.reactions], key=lambda x: x.count, reverse=True)
        try:
            if emote is not None:
                rxns = [rxn for rxn in rxns if emotes_equal(emote, rxn.emoji)]
            else:
                emote = rxns[0].emoji
            users = [u async for u in rxns[0].users()]
        except IndexError:
            users = []
        n = 0
        errors = []
        for user in users:
            try:
                await user.add_roles(role)
                n += 1
            except Exception as e:
                err = "Cannot add {} role to user {} with error {}."
                errors.append(err.format(role, user, e))
        if errors:
            await split_send(ctx, errors, style='```')
        out = 'Added role {} to {} player{} who reacted with {} to message {}.'
        out.format(role, n, 's' if n > 1 else 0, emote, msg.id)
        try:
            msg.reply(out, mention_author=False)
        except (discord.HTTPException, discord.Forbidden, discord.InvalidArgument):
            ctx.send(out)

    @commands.command()
    async def source(self, ctx):
        """Source code for this bot."""
        await ctx.send('My source code is available at https://github.com/TDTcode/TDTbot')

    @commands.command()
    @commands.check(_parings_perms)
    async def pairings(self, ctx, *args):
        """<role1> <role2> <role3> ... <roleN>
        1v1 parings for members in listed roles."""
        from random import shuffle
        converter = commands.RoleConverter()

        if not args:
            await ctx.send("Please specify at least one role.")
            return
        people = []
        for role in args:
            role = await converter.convert(ctx, role)
            people.extend(role.members)
        if not people:
            await ctx.send("No members found in specified roles.")
            return
        people = list(set(people))
        shuffle(people)
        n = len(people)
        i = 0
        matches = []
        while i < n - 1:
            matches.append("{} vs {}".format(people[i].mention, people[i+1].mention))
            i += 2
        if n % 2:
            matches.append("{} has no match.".format(people[-1].mention))
        await split_send(ctx, matches)


if usingV2:
    async def setup(bot):
        cog = MainCommands(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(MainCommands(bot))
