import asyncio
import discord
import datetime
from discord.ext import commands
from . import param


async def find_channel(guild, name=None):
    if name is None:
        name = param.rc['channel']
    return [i for i in guild.channels if i.name.lower() == name.lower()][0]


async def find_role(guild, name):
    return [i for i in guild.roles if i.name.lower() == name.lower()][0]


class MainCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None

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
    async def inactivity(self, ctx, role: discord.Role = None):
        """<role (optional)> shows how long members have been inactive for."""
        await ctx.send("Hold on while I parse the server history.")
        if role is None:
            members = ctx.guild.members
        else:
            members = role.members
        data = dict()
        channels = [i for i in ctx.guild.channels if hasattr(i, "history")]
        oldest = datetime.datetime.now()
        old_af = datetime.datetime(1, 1, 1)
        for channel in channels:
            try:
                async for msg in channel.history(limit=1000):
                    oldest = min(oldest, msg.created_at)
                    if msg.author in members:
                        try:
                            data[msg.author] = max(data[msg.author], msg.created_at)
                        except KeyError:
                            data[msg.author] = msg.created_at
            except discord.Forbidden:
                # await ctx.send("Cannot read channel {0}.".format(channel))
                pass
        for member in members:
            if member not in data:
                if member.joined_at > oldest:
                    data[member] = member.joined_at
                else:
                    data[member] = old_af
        items = sorted(data.items(), key=lambda x: x[1])
        msg = '\n'.join(['{0.display_name} {1}'.format(i[0], i[1].date().isoformat())
                         for i in items])
        await ctx.send('```' + msg + '```')

    @commands.command()
    async def roles(self, ctx):
        """List server roles"""
        await ctx.send("\n".join([i.name for i in ctx.guild.roles
                                  if 'everyone' not in i.name]))

    @commands.command()
    async def channel_hist(self, ctx, channel: discord.ChannelType = None):
        """<member (optional)> shows member history"""
        if channel is None:
            channel = ctx.channel
        hist = await channel.history(limit=10).flatten()
        msg = '\n'.join(["Item {0:d}\n{1.content}".format(i + 1, m)
                         for i, m in enumerate(hist)])
        if not msg:
            msg = "No history available."
        await ctx.send(msg)

    @commands.command()
    async def member_hist(self, ctx, member: discord.Member = None):
        """<member (optional)> shows member history"""
        if member is None:
            member = ctx.author
        hist = await member.history(limit=10).flatten()
        if not hist:
            user = self.bot.get_user(member.id)
            hist = await user.history(limit=10).flatten()
        msg = '\n'.join(["Item {0:d}\n{1.content}".format(i + 1, m)
                         for i, m in enumerate(hist)])
        if not msg:
            msg = "No history available."
        print(str(hist))
        await ctx.send(msg)

    @commands.command()
    async def bots(self, ctx):
        """Lists server bots"""
        bots = [m for m in ctx.guild.members if m.bot]
        electro = ctx.guild.get_member_named('UnknownElectro#1397')
        if electro:
            bots.insert(0, electro)
        msg = 'Listing bots for {0.guild}:\n'.format(ctx)
        msg += '\n'.join([str(i + 1) + ') ' + b.display_name for i, b in enumerate(bots)])
        await ctx.send(msg)

    @commands.command()
    async def nou(self, ctx, channel: str = None, guild: str = None):
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
            channel = await find_channel(guild, channel)
        else:
            channel = ctx.channel
        await channel.send("NO U")


class Debugging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def RuntimeError(self, ctx):
        """Raise a runtime error (because why not)"""
        raise RuntimeError("Per user request")

    @commands.command()
    async def flush(self, ctx, n: int = 10):
        """<n=10 (optional)> flushes stdout with n newlines"""
        print('\n' * n)

    @commands.command()
    async def reboot(self, ctx):
        """Reboots this bot"""
        await ctx.send("Ok. I will reboot now.")
        print('\nRebooting\n\n\n\n')
        await self.bot.loop.run_until_complete(self.bot.logout())


class Alerts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.get_channel('Debugging')
        roles = [await find_role(member.guild, i) for i in ["Admin", "Devoted"]]
        roles = " ".join([i.mention for i in roles if hasattr(i, 'mention')])
        if channel is not None:
            await channel.send(roles + ' new member {0.name} joined.'.format(member))


class MainBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        if 'command_prefix' not in kwargs:
            kwargs['command_prefix'] = param.rc['cmd_prefix']
        if 'loop' not in kwargs:
            kwargs['loop'] = asyncio.new_event_loop()
        super().__init__(*args, **kwargs)
        self.add_cog(MainCommands(self))
        self.add_cog(Alerts(self))
        self.add_cog(Debugging(self))

        @self.event
        async def on_ready():
            print('We have logged in as {0.user}'.format(self))
            activity = discord.Activity(name='UnknownElectro be a bot',
                                        type=discord.ActivityType.listening)
            await self.change_presence(activity=activity)
