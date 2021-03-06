import discord
from discord.ext import commands
import logging
from ..helpers import *
from ..async_helpers import admin_check, git_log, split_send
from .. import git_manage


logger = logging.getLogger('discord.' + __name__)


class Debugging(commands.Cog):
    """Cog designed for debugging the bot"""
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        """Don't allow everyone to access this cog"""
        return await admin_check(ctx)

    @commands.command()
    async def channel_id(self, ctx, channel: discord.TextChannel = None, guild: str = None):
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
        await ctx.send('Channel "{0.name}" has id {0.id}.'.format(channel))

    @commands.command()
    async def member_id(self, ctx, member: str = None, guild: str = None):
        """<channel (optional)> <server (optional)> sends random roast message"""
        if guild is None:
            guild = ctx.guild
        else:
            try:
                guild = [i for i in self.bot.guilds if i.name == guild][0]
            except IndexError:
                ctx.send('ERROR: server "{0}" not found.'.format(guild))
                return
        if member:
            member = guild.get_member_named(member)
        else:
            member = ctx.author
        await ctx.send('{0.name} has id {0.id}.'.format(member))

    @commands.command()
    async def reload_cogs(self, ctx, option=None):
        """Reloads all cogs that were added as extensions"""
        if option == 'pull':
            git_manage.update()
        msg = 'Reloading ' + ', '.join([i.split('.')[-1] for i in self.bot.extensions])
        for i in self.bot.extensions:
            self.bot.reload_extension(i)
        await ctx.send(msg.rstrip(', '))

    @commands.command()
    async def print(self, ctx, *args):
        """Print text following command to terminal. This is useful for emojis."""
        logger.printv(' '.join(args))

    @commands.command()
    async def param(self, ctx, *args):
        """Print param to discord chat."""
        from .. import param
        if param.rc:
            msg = '\n'.join(["{:}: {:}".format(*[i, param.rc[i]]) for i in param.rc
                             if i not in ['roasts', 'token']])
            await ctx.send('```' + msg + '```')
        else:
            await ctx.send("Param is empty.")

    @commands.command()
    async def reload_extension(self, name):
        self.bot.reload_extension(name)

    @commands.command()
    async def id_this(self, ctx):
        ref = ctx.message.reference
        msg = ctx.message
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
        if hasattr(msg, 'id'):
            txt = ['message id: ' + str(msg.id),
                   'channel id: ' + str(msg.channel.id),
                   'guild id: ' + str(msg.guild.id)]
        else:
            txt = ['{}: {}'.format(i.replace('_', ' '), getattr(msg, i, 'unknown'))
                   for i in ['message_id', 'channel_id', 'guild_id']]
        if hasattr(msg, 'author'):
            a = msg.author
            txt.append('author: {}'.format(a.display_name))
            txt.append('author id: {0}'.format(a.id))
        await split_send(ctx, txt)

    @commands.command()
    async def channel_hist(self, ctx, channel: discord.TextChannel = None, n: int = 10):
        """<channel (optional)> shows channel history (past 10 entries)"""
        if channel:
            channel = find_channel(ctx.guild, channel)
        else:
            channel = ctx.channel
        hist = await channel.history(limit=n).flatten()
        msg = ["Item {0:d} {1.id}\n{1.content}".format(i + 1, m)
               for i, m in enumerate(hist)]
        if not msg:
            msg = ["No history available."]
        print(msg)
        await split_send(ctx, msg)

    @commands.command()
    async def member_hist(self, ctx, member: discord.Member = None):
        """<member (optional)> shows member history (past 10 entries)"""
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
        logger.printv(str(hist))
        await split_send(ctx, msg)


def setup(bot):
    bot.add_cog(Debugging(bot))
