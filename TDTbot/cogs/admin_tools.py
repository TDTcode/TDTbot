import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import os
import logging
import time
from typing import Union
from ..param import PermaDict
from ..helpers import emotes_equal, find_channel
from ..async_helpers import admin_check
from ..version import usingV2


logger = logging.getLogger('discord.' + __name__)
_dbm = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]
_dbm = os.path.join(_dbm, 'config', 'admin_tools_sticky.dbm')


class AdminTools(commands.Cog):
    """Cog designed for debugging the bot"""
    def __init__(self, bot):
        self.bot = bot
        self.stickies = PermaDict(_dbm)

    async def cog_check(self, ctx):
        """Don't allow everyone to access this cog"""
        return await admin_check(ctx)

    @commands.command()
    async def clear_rxn(self, ctx, emote: str, msg_id: int = None,
                        channel: Union[discord.abc.Messageable, int] = None):
        """<emote> <message id (optional)> <channel (optional)>
        Clear all of the specified reaction for the message

        Can be used as a reply to a message, in this case:
        <message id> defaults to the message that's being replied to.
        <channel> defaults to the channel where this command was entered."""
        logger.info('clear_rxn: {}'.format(dict(ctx=ctx, emote=emote, msg_id=msg_id, channel=channel)))
        ref = ctx.message.reference
        try:
            emote = int(emote)
        except ValueError:
            pass
        if isinstance(channel, int):
            channel = self.bot.find_channel(channel)
            if channel is None:
                channel = await self.bot.fetch_channel(channel)
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
        rxns = [rxn for rxn in msg.reactions if emotes_equal(emote, rxn.emoji)]
        if rxns:
            await rxns[0].clear()

    @commands.command()
    async def reboot(self, ctx):
        """Reboots this bot"""
        await ctx.send("Ok. I will reboot now.")
        logger.info('\nRebooting\n\n\n\n')
        self.bot.reissue = ctx
        # This exits the bot loop, allowing __main__ loop to take over
        await self.bot.loop.run_until_complete(await self.bot.close())

    @commands.command()
    async def speak(self, ctx, message, channel: discord.TextChannel = None, guild: str = None):
        """Speak as the bot"""
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
        await channel.send(message)

    def _add_sticky(self, msg):
        self.stickies[msg.channel.id] = self.stickies.get(msg.channel.id, []) + [msg.id]

    def _rm_sticky(self, message_id, channel_id):
        try:
            self.stickies[channel_id].pop(message_id)
        except IndexError:
            pass
        if not self.stickies[channel_id]:
            self.stickies.delete(channel_id)

    @commands.command()
    async def sticky(self, ctx, message, channel: discord.TextChannel = None,
                     reply: discord.Message = None):
        """<message> <channel (optional)> <reply (optional)> - Make a sticky message (untested)"""
        if channel is None:
            channel = ctx.channel
        msg = await channel.send(message, reference=reply, mention_author=False)
        self._add_sticky(msg)

    @commands.command(aliases=['wd40'])
    async def unsticky(self, ctx, message: discord.Message = None):
        """<message> - Remove a sticky message"""
        if message is None:
            ref = ctx.message.reference
            self._remove_sticky(ref.message_id, ref.channel_id)
        else:
            self._remove_sticky(message.id, message.channel.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        sleep = False
        if message.author == self.bot.user:
            sleep = True
        else:
            try:
                if message.content.startswith(self.bot.command_prefix):
                    sleep = True
            except TypeError:
                for prefix in self.bot.command_prefix:
                    if message.content.startswith(prefix):
                        sleep = True
                        break
        if sleep:
            time.sleep(1)
        if message.channel.id in self.stickies:
            if message.id in self.stickies[message.channel.id]:
                return
            for mid in self.stickies[message.channel.id]:
                msg = await message.channel.fetch_message(mid)
                msg = await message.channel.send(msg.content, reference=msg.reference,
                                                 mention_author=False)
                self._rm_sticky(msg.id, msg.channel.id)
                self._add_sticky(msg)


if usingV2:
    async def setup(bot):
        cog = AdminTools(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(AdminTools(bot))
