import datetime
import discord
from discord.ext import commands
import logging
from .. import param, users
from ..config import UserConfig
from ..helpers import *
from ..async_helpers import *


logger = logging.getLogger('discord.' + __name__)

_bot = "tdt.dms"


class DirectMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
        self._kicks = []
        self._configs = {}
        self._channel = None

    def _get_config(self, user=None):
        """Get a user's config file"""
        if user is None:
            user = self.bot.user
        try:
            return self._configs[user.id]
        except KeyError:
            self._configs[user.id] = UserConfig(user)
            return self._configs[user.id]

    @property
    def data(self):
        """Get the data file for the bot"""
        try:
            return self._get_config()[_bot]
        except KeyError:
            self._get_config()[_bot] = {}
            return self._get_config()[_bot]

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __contains__(self, item):
        return item in self.data

    def keys(self):
        return self.data.keys()

    @property
    def channel(self):
        """Get the log channel for the bot"""
        if self._channel is None:
            self._channel = self.bot.find_channel(param.rc('log_channel'))
        return self._channel

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for DMs and post them in the bot log channel"""
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
        # if DM
        if type(message.channel) == discord.DMChannel:
            channel = self.bot.find_channel(param.rc('log_channel'))
            roles = [find_role(channel.guild, i).mention for i in ["admin", "devoted"]]
            msg = ' '.join(roles) + '\n'
            msg += 'From: {0.author}\n"{0.content}"'.format(message)
            sent = await channel.send(msg)
            self[sent.id] = message.channel.id
            return
        # if message from log channel
        if message.channel == self.channel:
            if admin_check(bot=self.bot, author=message.author, guild=self.channel.guild):
                # if message is reply to a previous message
                if message.reference:
                    if message.reference.message_id in self:
                        channel = self.bot.get_channel(self[message.reference.message_id])
                        await channel.send(message.content)


def setup(bot):
    """This is required to add this cog to a bot as an extension"""
    bot.add_cog(DirectMessages(bot))
