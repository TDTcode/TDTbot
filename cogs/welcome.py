import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import asyncio
import datetime
from ..helpers import find_channel, find_role, localize
from ..param import rc, channels, messages, roles, emoji2role
from ..version import usingV2
from ..async_helpers import admin_check
import logging


logger = logging.getLogger('discord.' + __name__)
_CoC_id = messages.CoC
_wolfpack_id = messages.wolfpack
_trick_or_treat = messages.trick_or_treat
_recruit = roles.recruit
_log_in_discord = False
# clear reactions on manual page reactions to message posted before this
_before = datetime.datetime(2022, 1, 22, 0, 0, 0)
# don't clear reactions from these messages
_protected = [_CoC_id, _wolfpack_id, _trick_or_treat]
_welcome_file = rc('welcome_file')

try:
    with open(_welcome_file, 'r') as f:
        _welcome_text = f.read()
except IOError:
    logger.warning(f'Welcome file ({_welcome_file}) not found, using default welcome message.', exc_info=True)
    _welcome_text = 'Greetings {member.name}! Part of my duties as TDTbot are to welcome ' \
                    'newcomers to The Dream Team. \n\nSo welcome!\n\nWe have a few questions ' \
                    'we ask everyone, so please post the answers to the following questions ' \
                    'in the general chat:\n' \
                    '1) How did you find out about TDT?\n' \
                    '2) What games and platforms do you play?\n' \
                    '3) Are you a YouTube subscriber?\n' \
                    '4) Are you a Patreon supporter, or a Twitch sub (tier 2 or higher)? If so, what\'s your account name?\n\n'\
                    'If you\'re interested in learning wolf pack (see our #manual_page), ping ' \
                    '@member, and if you want to send any feedback to the TDT admins then leave ' \
                    'me a DM.\n\n'\
                    'And... finally... we have a code of conduct in our #manual_page that we ' \
                    'ask everybody to agree to. Just give it a 👍 if you agree. If you want me to ' \
                    'give you a Destiny 2 tag, click the corresponding platform tag on the ' \
                    'code of conduct after you give the thumbs up.' \
                    '\n\nWhelp, I hope someone gives you a less robotic welcome soon!\n\n'\
                    'Also find us on social media:\n'\
                    'YT channel membership: https://www.youtube.com/channel/UCKBCsmU53MBzCm_wNZY7hLA/join\n'\
                    'Twitter: https://twitter.com/productions_tdt\n'\
                    'Instagram: https://www.instagram.com/tdt_productions_\n'\
                    'Patreon: https://www.patreon.com/TDTPatreon'


async def send_welcome(member, channel=None, retry=None, msg=_welcome_text):
    """Sends welcome message to member"""

    try:
        if channel is None:
            channel = member.dm_channel
            if not channel:
                await member.create_dm()
                channel = member.dm_channel
        return await channel.send(msg.format(member=member))
    except discord.Forbidden as e:
        if retry is not None:
            msg = '{:} I am unable to DM you so I am posting my standard welcome DM here.\n' + msg
            await retry.send(msg.format(member=member))
            return await retry.send(msg.format(member=member))
        raise e


class Welcome(commands.Cog):
    """Cog to listen and send alerts"""
    # emoji: role
    _emoji_dict = emoji2role

    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
        self._manual_channel = None
        self._log_channel = None
        self._welcome_channel = None
        self._init = False

    async def _async_init(self):
        if self._init:
            return
        await self.clean_manual_page(None)
        self._init = True

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self._async_init()

    async def cog_check(self, ctx):
        """Don't allow everyone to access this cog"""
        return await admin_check(ctx)

    @property
    def manual_channel(self):
        if self._manual_channel is None:
            self._manual_channel = self.bot.find_channel(channels.manual_page)
        return self._manual_channel

    @property
    def log_channel(self):
        if self._log_channel is None:
            self._log_channel = self.bot.find_channel(channels.debugging)
        return self._log_channel

    @property
    def welcome_channel(self):
        if self._welcome_channel is None:
            self._welcome_channel = self.bot.find_channel(channels.welcome_wagon)
        return self._welcome_channel

    async def fetch_coc(self):
        return await self.manual_channel.fetch_message(_CoC_id)

    @commands.command()
    async def coc_reactions(self, ctx, member: discord.User = None):
        """<member> - Prints the reactions to the code of conduct by member"""
        if member is None:
            member = ctx.author
        msg = await self.fetch_coc()
        rxns = [rxn for rxn in msg.reactions
                if await rxn.users().find(lambda u: u == member)]
        await ctx.send(''.join(['{}'.format(rxn.emoji) for rxn in rxns]))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Alert admin type roles on new member joining"""
        logger.info('New member {0.name} joined'.format(member))
        _roles = [find_role(member.guild, i) for i in ["Admin", "Devoted"]]
        _roles = " ".join([i.mention for i in _roles if hasattr(i, 'mention')])
        if _log_in_discord:
            log_channel = self.log_channel
            if log_channel is not None:
                await log_channel.send('New member {0.name} joined.'.format(member))
        retry = False
        #try:
        #    await send_welcome(member)
        #except discord.Forbidden:
        #    retry = True
        manual = self.manual_channel
        msg = "Welcome to TDT {0.mention} <a:blobDance:738431916910444644>" \
              " Please look at the {1.mention}.".format(member, manual)
        await member.guild.system_channel.send(msg)
        msg = await self.fetch_coc()
        rxns = []
        for rxn in msg.reactions:
            async for user in rxn.users():
                if user == member:
                    rxns.append(rxn)
                    break
        # check for welcome back
        if "👍" in [str(rxn.emoji) for rxn in rxns]:
            old = msg
            msg = "... Or I guess I should say welcome back!"
            emoji_dict = {"👍": _recruit}
            emoji_dict.update(self._emoji_dict)
            _roles = [await self.bot.emoji2role(None, emoji_dict, emoji=rxn.emoji,
                                                member=member, guild=member.guild)
                      for rxn in rxns]
            _roles = ["`{}`".format(role) for role in _roles if role]
            if _roles:
                msg += "\nI've restored your " + ', '.join(_roles) + ' role'
                msg += 's.' if len(_roles) > 1 else '.'
            await member.guild.system_channel.send(msg, reference=old)
        #if retry:
        #    await send_welcome(member, retry=member.guild.system_channel)

    @commands.command()
    async def send_welcome(self, ctx, member: discord.User = None):
        """Send welcome message to an individual for testing"""
        if not member:
            member = ctx.author
        await send_welcome(member)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Parse reaction adds for agreeing to code of conduct and rank them up to
        Recruit"""
        # if bot
        if payload.user_id == self.bot.user.id:
            return
        # if not code of conduct message
        if payload.message_id != _CoC_id:
            # if reaction is in manual page and not protected
            try:
                if payload.channel_id == self.manual_channel.id:
                    msg = await self.manual_channel.fetch_message(payload.message_id)
                    await self.safely_remove_reactions(msg)
            # handle missing channel
            except AttributeError:
                pass
            return
        guild = [g for g in self.bot.guilds if g.id == payload.guild_id][0]
        recruit = find_role(guild, _recruit)
        args = payload, self._emoji_dict
        kwargs = dict(guild=guild, min_role=recruit)
        if str(payload.emoji) == "👍":
            out = "{0.display_name} agreed to the code of conduct.".format(payload.member)
            logger.info(out)
            if _log_in_discord:
                log_channel = find_channel(guild, "admin_log")
                # if they've agreed to CoC recently then return
                async for msg in log_channel.history(limit=200):
                    if msg.content == out:
                        return
                await log_channel.send(out)
            now = localize(datetime.datetime.utcnow())
            # if in joined in last 2 weeks
            if (now - localize(payload.member.joined_at)).seconds // 86400 < 14:
                if payload.member.top_role < recruit:
                    reason = "Agreed to code of conduct."
                    await payload.member.add_roles(recruit, reason=reason)
                # if they reacted before this with a platform role
                msg = await self.fetch_coc()
                for rxn in msg.reactions:
                    if getattr(rxn.emoji, 'id', rxn.emoji) in self._emoji_dict:
                        if payload.member in [u async for u in rxn.users()]:
                            await self.bot.emoji2role(*args, emoji=rxn.emoji, **kwargs)
            return
        if hasattr(payload.emoji, 'id'):
            await self.bot.emoji2role(*args, **kwargs)
        await self.clean_coc(None)

    @commands.command()
    async def clean_coc(self, ctx):
        """Clean up reactions to the CoC message"""
        msg = await self.fetch_coc()
        for rxn in msg.reactions:
            if getattr(rxn.emoji, 'id', rxn.emoji) not in list(self._emoji_dict) + ["👍"]:
                await rxn.clear()

    @commands.command()
    async def clean_manual_page(self, ctx):
        """Clean up reactions in the manual page"""
        channel = self.manual_channel
        history = [h async for h in channel.history(limit=200, before=_before)]
        for msg in history:
            await self.safely_remove_reactions(msg)

    async def safely_remove_reactions(self, msg, guild=None):
        """Remove reactions from a message"""
        if msg.id in _protected:
            return
        if msg.id == _CoC_id:
            return
        if msg.id == 945717800788447282:  # wolfpack roles
            return
        if guild is None:
            guild = msg.guild
        admin = find_role(guild, roles.admin)
        for rxn in msg.reactions:
            top_role = None
            user = await self.bot.get_or_fetch_user(self.bot.user.id, guild)
            async for user in rxn.users():
                if top_role is None:
                    try:
                        role = user.top_role
                    except AttributeError:
                        role = None
                    try:
                        top_role = max(role, top_role)
                    except TypeError:
                        top_role = role
            if top_role < admin:
                await rxn.clear()


if usingV2:
    async def setup(bot):
        cog = Welcome(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(Welcome(bot))
