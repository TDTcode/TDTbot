import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import logging
from ..async_helpers import admin_check, git_log
from ..version import usingV2
from .. import git_manage


logger = logging.getLogger('discord.' + __name__)


class GitTools(commands.Cog):
    """Cog designed for debugging the bot"""
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        """Don't allow everyone to access this cog"""
        return await admin_check(ctx)

    @commands.command()
    async def git_pull(self, ctx):
        """Do a git pull on own code"""
        git_manage.update()
        await ctx.send("Pulled own code")

    @commands.command()
    async def git_log(self, ctx, *args):
        """Print git log to discord chat."""
        return await git_log(ctx, *args)

    @commands.group()
    async def git(self, ctx):
        """Base function for git sub commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid git command passed...')

    @git.command()
    async def pull(self, ctx):
        """Alias for git_pull"""
        await self.git_pull(ctx)

    @git.command()
    async def log(self, ctx):
        """Alias for git_log"""
        await self.git_log(ctx)


if usingV2:
    async def setup(bot):
        cog = GitTools(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(GitTools(bot))
