import asyncio
import discord  # type: ignore # noqa: F401
from discord.ext import commands  # type: ignore
import datetime
import logging
import pytz
import random
import re
import traceback
from typing import Union

from .. import param
from ..helpers import parse_timezone, minute, day, localize, delocalize
from ..async_helpers import admin_check, wait_until, split_send
from ..version import usingV2


logger = logging.getLogger('discord.' + __name__)
_stale_emoji = '🔕'
_prototype = "**<Prototype Event Name>**\n"\
             "What: <a bots example event>\n"\
             "Who: <@TDTbot>\n"\
             "When: <Sunday at 4:20pm PT>\n"\
             "React with <insert emoji> to reserve your spot.\n"\
             "(all times will be counted in Pacific Timezone)\n"\
             "(don't include the <> characters in your post)"


async def is_stale(message, user):
    rxns = [rxn for rxn in message.reactions if rxn.emoji == _stale_emoji]
    if rxns:
        if user in rxns[0].users:
            return True
    return False


class _Event(dict):
    """A class to contain event info (dict subclass)."""
    def __init__(self, message, cog, log_channel=None, from_hist=False):
        super().__init__()
        self.cog = cog
        self.children = []
        if message.author == cog.bot.user:
            return
        self._error = None
        self._comments = []
        # start parsing message for event info
        lines = [i.strip() for i in message.content.split('\n')]
        nlines = len(lines)
        if nlines < 4:
            return
        out = dict()
        keys = ['who', 'what', 'when']  # check for and get these
        for line in lines:
            for key in keys:
                if line.lower().strip().startswith(key + ':'):
                    tmp = [i.strip() for i in line.split(':')]
                    value = ":".join(tmp[1:])
                    out[key] = value
        for key in keys:
            if key not in out:
                logger.warning('Missing key "{:}"'.format(key))
                print(out)
                print(lines)
                return
        out['name'] = lines[0] if len(lines) > 4 else out['what']
        # text saying how to enroll in event
        out['enroll'] = '\n'.join(lines[4:])
        day = None
        # check for unix timestamp
        unix_timestamp = re.match(r'<t:(\d+:[tTdDfFR])>', out['when'])
        if unix_timestamp:
            dt = unix_timestamp.group(1)
            dt = datetime.datetime.fromtimestamp(int(dt[:10]), tz=pytz.utc)
            day = dt.strftime('%A')
        # parse day of week
        if day is None:
            days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                            'saturday', 'sunday']
            for d in days_of_week:
                if d in out['when'].lower():
                    day = d
                    break
        try:
            if not day:
                logger.warning("Can't parse day")
                if not from_hist:
                    self._error = "Event not registered. Unable to parse day of week"
                raise ValueError
            # We only get this far if we have a valid event, so set attributes now
            self.cog = cog
            self._pending_alerts = False
            self.from_hist = from_hist
            if log_channel is None:
                log_channel = getattr(self.cog, 'channel', param.rc('event_channel'))
            self.log_channel = self.cog.bot.find_channel(log_channel)
            tz = pytz.timezone(param.rc('timezone'))
            self.tz = tz
            out['id'] = message.id
            self._message_channel = message.channel
            # Attributes finished, now deal with timezone crap
            now = datetime.datetime.now().astimezone(tz).replace(tzinfo=None)
            today = now.date()  # today in server timezone
            if not unix_timestamp:
                i = 0
                # parse day of week into datetime and assume it's the next day with given name
                while (today + datetime.timedelta(days=i)).weekday() != days_of_week.index(day):
                    i += 1
                day = today + datetime.timedelta(days=i)
                # parse time text
                time_text = out['when'].lower().strip()
                search = r'([0-9]{1,2})([:. -])?([0-9]{2})?[ ]?([ap][.]?m[.]?)?[ ]?(\w+)?'
                time = re.findall(search, time_text)
                if not time:
                    logger.warning("Can't parse time")
                    if not from_hist:
                        self._error = "Event not registered. Unable to parse time"
                    raise ValueError
                logger.debug('Time: {}'.format(time))
                time = time[0]
                hour = int(time[0])
                minute = int(time[2] if time[2] else 0)
                am_pm = time[3].strip().replace('.', '')
                # parse timezone, default to server timezone (US/Pacific)
                timezone = tz
                tz_parsed = False
                if time[4]:
                    try:
                        timezone = parse_timezone(time[4])
                    except pytz.exceptions.UnknownTimeZoneError:
                        logger.info('timezone parse "{}" fail.'.format(time[4]))
                        logger.info(traceback.format_exc())
                    else:
                        tz_parsed = True
                        # self._comments.append('Timezone "{}" parsed as: "{}"'.format(time[4], timezone.zone))
                # if am/pm not provided
                if not am_pm:
                    if 'night' in out['when'].lower() and hour < 12:
                        am_pm = 'pm'
                    elif hour < 8 and 'morning' not in out['when'].lower():
                        am_pm = 'pm'
                    elif hour < 12:
                        am_pm = 'am'
                if am_pm == 'pm' and hour < 12:
                    hour += 12
                t = datetime.time(hour, minute)
                # make sure datetime is specified with parsed timezone
                dt = timezone.localize(datetime.datetime.combine(day, t))
                if tz_parsed:
                    abrv = timezone.localize(datetime.datetime.now(), is_dst=None).tzname().lower()
                    if time[4] != abrv and len(time[4]) in [3, 4]:
                        msg = 'I think you meant "{}" instead of "{}".'
                        self._comments.append(msg.format(abrv.upper(), time[4].upper()))
            # convert it to UTC and strip timezone info (required by external libs)
            out['datetime'] = dt.astimezone(pytz.utc)
            # put the contents of out into self
            self.update(out)
            return
        except Exception as e:
            logger.info("Error parsing event!")
            logger.info(e)
            logger.info(traceback.format_exc())
            logger.info("=" * 30)
            logger.info(message.content)
            logger.info("=" * 30)
            if not from_hist:
                self._error = "Event not registered. Unable to parse event.\n" \
                              "Sorry, I'm not much smarter than Electro."
            return

    async def send_error(self, channel=None):
        if channel is None:
            channel = getattr(self.cog, 'channel', param.rc('event_channel'))
        if self._error:
            msg = await channel.send(self._error)
            self.children.append(msg)

    async def message(self):
        """Fetch and return the message associated with this event"""
        # we fetch this every usage to update the reactions
        return await self._message_channel.fetch_message(self['id'])

    @property
    def dt_str(self):
        """Datetime string for this event"""
        # assign UTC timezone to datetime object
        dt = localize(self['datetime'])
        # convert to server timezone
        return dt.astimezone(self.tz).strftime('%X %A %x %Z')

    def unix_timestamp(self, mode='R'):
        """Unix timestamp for this event"""
        dt = localize(self['datetime'])
        return '<t:{:d}:{:}>'.format(int(dt.timestamp()), mode)

    @property
    def name(self):
        """Name of event"""
        return self['name']

    @property
    def log_message(self):
        """Return the string we want to send to the log when registering this event"""
        return 'Event "{}" registered for {}'.format(self.name, self.unix_timestamp('F'))

    @property
    def id(self):
        """Message id"""
        return self['id']

    async def record_log(self, log_channel=None):
        """Record the log message in the log channel if it's not there already"""
        after = self['datetime'] - datetime.timedelta(days=6, hours=23)
        log = self.log_message
        if log_channel is None:
            log_channel = self.log_channel
        # check log if the log_message is already there
        async for msg in log_channel.history(limit=200, after=delocalize(after)):
            if msg.content == log:
                return
        # if we are registering this event from history
        if self.from_hist:
            msg = await self.message()
            if not msg:
                return
            # if this message was edited more than 10 min after creation
            if not (msg.edited_at is None or msg.created_at is None):
                if msg.edited_at > msg.created_at + 10 * minute:
                    t = localize(msg.created_at + 1 * day)
                    # and the event post/message is more than a day older then reboot
                    print(localize(self.cog.bot.restart_time()))
                    print(localize(t))
                    if localize(self.cog.bot.restart_time()) > localize(t):
                        # exit and don't post log
                        return
        else:
            if self._comments:
                await split_send(self.log_channel, self._comments)
        msg = await self.log_channel.send(log)
        self.children.append(msg)

    async def make_stale(self):
        msg = await self.message()
        await msg.add_reaction(_stale_emoji)

    async def _is_stale_q(self, msg=None):
        if msg is None:
            msg = await self.message()
        return is_stale(msg, self.bot.user)

    def future_or_active(self, hours=6):
        """Is this event in the past or near future?"""
        return (localize(datetime.datetime.utcnow()) - localize(self['datetime']) <=
                datetime.timedelta(hours=hours))

    def past(self):
        """Is this event in the past?"""
        if localize(self['datetime']) < localize(datetime.datetime.utcnow()):
            return True
        return False

    async def attendees(self):
        """Return set of enrolled attendees"""
        msg = await self.message()
        out = []
        for rxn in msg.reactions:
            out.extend([u async for u in rxn.users()])
        return set(out)

    async def content(self):
        """Return message content"""
        msg = await self.message()
        return msg.content

    async def search(self, phrases):
        """Does this event contain one of the given phases"""
        print('search')
        print(phrases)
        content = (await self.content()).lower()
        print(content)
        for i in phrases:
            if i.lower() in content:
                print(i, content)
                return True
        return False

    async def alert(self, dt_min=None, channel=None, eta=None, wait=True, prefix=None):
        """Schedule/send event alerts mentioning all attendees.
        option dt_min is time before event in minutes.
        """
        if channel is None:
            channel = getattr(self.cog, 'channel', param.rc('event_channel'))
        channel = self.cog.bot.find_channel(channel)
        dt = localize(self['datetime']) - datetime.timedelta(minutes=dt_min)
        if dt < localize(datetime.datetime.utcnow()):
            dt_min = (localize(self['datetime']) - localize(datetime.datetime.utcnow())).seconds // 60
        if prefix is None:
            prefix = 'Your event "{0.name}"'.format(self)
        if eta is None:
            if dt_min is None:
                eta = "is approaching."
            elif dt_min == 0:
                eta = "is starting now."
            elif dt_min % 60 == 0:
                if dt_min == 60:
                    eta = "is starting in an hour."
                else:
                    eta = "is starting in {:d} hours.".format(dt_min // 60)
            elif dt_min > 60:
                if dt_min > 120:
                    eta = "is starting in {:d} hours and {:d} minutes."
                else:
                    eta = "is starting in {:d} hour and {:} minutes."
                eta = eta.format(dt_min // 60, dt_min % 60)
                if dt_min % 60 == 1:
                    eta = eta[:-2] + '.'
            else:
                if dt_min == 1:
                    eta = "is starting in one minute."
                else:
                    eta = "is starting in {:d} minutes.".format(dt_min)
        if eta == 'UNIX':
            eta = 'is starting {} ({})'.format(self.unix_timestamp(), self.unix_timestamp('F'))
        if wait:
            await wait_until(dt)
        msg = ' '.join([prefix, eta] + [i.mention for i in await self.attendees()])
        msg = await channel.send(msg)
        self.children.append(msg)
        if dt == 0:  # todo: fix this
            await self.make_stale()
        if dt_min == 0 and self.past():
            await self.make_stale()
            await self._clear(wait=None)

    def set_alerts(self, dts=None, channel=None):
        """Set multiple alerts for list of dt (in minutes)"""
        if self._pending_alerts:
            return
        if dts is None:
            dts = param.rc('event_reminders')[:]
        if self.from_hist:
            delta = localize(self['datetime']) - localize(datetime.datetime.utcnow())
            tmp = [dt for dt in dts if datetime.timedelta(minutes=dt) <= delta]
            if dts != tmp:
                logger.info('dts changed for event {0.name}'.format(self))
                logger.info('dts: ' + str(dts))
                logger.info('new: ' + str(tmp))
            dts = tmp
        for dt in dts:
            self.cog.bot.loop.create_task(self.alert(dt, channel=channel))
        self._pending_alerts = True

    async def log_and_alert(self, dts=None, event_chanel=None, log_channel=None):
        """Record log_message and set alerts"""
        await self.record_log(log_channel=log_channel)
        self.set_alerts(dts=dts, channel=event_chanel)

    async def _clear(self, wait=0):
        if wait != 0:
            if wait is None:
                wait = datetime.timedelta(days=1)
            if isinstance(wait, float):
                wait = datetime.timedelta(hours=wait)
            if isinstance(wait, datetime.timedelta):
                wait = localize(self['datetime']) + wait
            await wait_until(wait)
        for msg in self.children:
            await msg.delete()
        self.children = []
        msg = await self.message()
        await msg.delete()
        keys = self.keys()[:]
        for i in keys:
            del self[i]


class Events(commands.Cog):
    """Cog to handle events"""
    def __init__(self, bot, channel=None, log_channel=None):
        self.bot = bot
        if channel is None:
            channel = param.rc('event_channel')
        self._channel = channel
        if log_channel is None:
            log_channel = param.rc('log_channel')
        self._log_channel = log_channel
        self._events = []
        self._hist_checked = False

    @property
    def channel(self):
        """Return channel and fetch it if needed"""
        if hasattr(self._channel, 'id'):
            return self._channel
        channel = self.bot.find_channel(self._channel)
        if channel:
            self._channel = channel
            return channel

    @property
    def log_channel(self):
        """Return log channel and fetch it if needed"""
        if hasattr(self._log_channel, 'id'):
            return self._log_channel
        channel = self.bot.find_channel(self._log_channel)
        if channel:
            self._log_channel = channel
            return channel

    @property
    def event_list(self):
        """Return a list of active events still to happen"""
        return [e for e in self._events if e.future_or_active()]

    def cleanse_old(self):
        """Remove past events"""
        old = [e for e in self._events if not e.future_or_active()]
        for e in old:
            self._events.remove(e)

    def is_event_channel(self, channel):
        """Is the given channel the event channel"""
        if channel == self.channel:
            return True
        if channel == self.channel.id:
            return True
        if isinstance(self._channel, int):
            return channel.id == self.channel.id
        if hasattr(self.channel, "lower"):
            try:
                int(self.channel)
                return self.channel.id == channel.id
            except ValueError:
                return channel.name == self.channel
        return channel == self.channel

    async def enroll_event_if_valid(self, event):
        # if this is a valid event
        if event:
            if event not in self._events:
                self._events.append(event)
                await event.log_and_alert(event_chanel=self.channel)
        else:
            await event.send_error()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Parse messages for new event post"""
        # ignore all messages from our bot
        if message.author == self.bot.user:
            return
        # if we have not already parsed the history, do so
        if not self._hist_checked:
            await self.check_history()
        # ignore commands when checking for events
        try:
            if message.content.startswith(self.bot.command_prefix):
                return
        except TypeError:
            for prefix in self.bot.command_prefix:
                if message.content.startswith(prefix):
                    return
        # if message in event channel, then try to parse it
        if self.is_event_channel(message.channel):
            # if event is stale ignore it
            if await is_stale(message, self.bot.user):
                return
            await self.enroll_event_if_valid(_Event(message, self))

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        """Parse message edits that might be events"""
        # if message not in event channel, ignore it
        if not self.is_event_channel(payload.channel_id):
            return
        msg_id = payload.message_id
        n = len(self._events)
        # remove old versions of this event (before this edit we are now parsing)
        events = [i for i in range(n) if msg_id == self._events[i]['id']]
        for i in events:
            self.event_list.pop(i)
        # get message object
        message = await self.channel.fetch_message(msg_id)
        dt = datetime.timedelta(minutes=5)
        not_recent = (localize(datetime.datetime.now()) - localize(message.created_at)) > dt
        await self.enroll_event_if_valid(_Event(message, self, from_hist=not_recent))

    async def check_history(self, channel=None):
        """Check event channel history for any events we missed before we were
        initiated"""
        if channel is None:
            channel = self.channel
        # only check the last week
        after = datetime.datetime.utcnow() - datetime.timedelta(days=6, hours=23)
        try:
            async for i in channel.history(after=after, limit=200):
                if i.author != self.bot.user:
                    await self.enroll_event_if_valid(_Event(i, self, from_hist=True))
            logger.debug('History parsed.')
            self._hist_checked = True
        except AttributeError as e:
            logger.error('FAILURE in check_history:\n' + str(e))

    @commands.group()
    async def events(self, ctx):
        """<"attendees"> Lists events and optionally attendees."""
        if ctx.invoked_subcommand is None:
            msg = '{0}) {1.log_message}'
            msg = '\n'.join([msg.format(i + 1, e) for i, e in enumerate(self.event_list)])
            if msg:
                await ctx.send(msg)
            else:
                await ctx.send('No events.')

    @commands.command()
    async def unix_times(self, ctx):
        """List Unix times of events."""
        msg = ['{0}) {1.name} {2} {3}'.format(i, e, e.unix_timestamp('F'), e.unix_timestamp())
               for i, e in enumerate(self.event_list)]
        await split_send(ctx, msg)

    @events.command()
    async def attendees(self, ctx):
        """Prints event attendees. Subcommand of events; usage 'TDT$events attendees'"""
        msg = []
        fmt = '{0}) {1.name}: {2}'
        for i, e in enumerate(self.event_list):
            users = [j.display_name for j in await e.attendees()]
            msg.append(fmt.format(i + 1, e, ', '.join(users)))
        msg = '\n'.join(msg)
        if msg:
            await ctx.send(msg)
        else:
            await ctx.send('No events.')

    @events.command()
    async def dt(self, ctx):
        """Prints time until events. Subcommand of events; usage 'TDT$events dt'"""
        try:
            msg = []
            now = datetime.datetime.utcnow()
            fmt = '{0}) {1.name}: {2}'
            for i, e in enumerate(sorted(self.event_list, key=lambda x: x['datetime'])):
                dt = localize(e['datetime']) - localize(now)
                msg.append(fmt.format(i + 1, e, dt))
            msg = '\n'.join(msg)
            if msg:
                await ctx.send(msg)
            else:
                await ctx.send('No events.')
        except Exception as e:
            logger.error(e)
            logger.error(''.join(traceback.format_tb(e.__traceback__)))
            raise e

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        await self.check_history()

    @commands.command()
    async def read_events(self, ctx):
        """Read and parse the events channel for events. This shouldn't need to be
        called."""
        await self.check_history()

    @commands.command()
    @commands.check(admin_check)
    async def clear_events(self, ctx, limit: int = 200):
        """<limit=200 (optional)> Clear the events channel.
        "limit" sets the max number of messages deleted.
        If this command is used as a reply then it will clear messages before that message
        """
        before = None
        active = []
        ref = ctx.message.reference
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
            before = msg.created_at
            for i in self._events:
                if not i.past():
                    active.append(i['id'])
                    active.extend([j.id for j in i.children])

        def purge_check(message):
            if before:
                if message.author == self.bot.user and message.content == _prototype:
                    return False
            if message.id in active:
                return False
            return True

        await self.channel.purge(limit=limit, before=before, check=purge_check)
        if before is None:
            msg = _prototype
            msg = await self.channel.send('```' + msg + '```')
            emoji = 'rebel_skuratnum_200x200'
            try:
                rxn = [e for e in self.channel.guild.emojis if e.name == emoji][0]
                if rxn:
                    await msg.add_reaction(rxn)
            except IndexError:
                pass
            return
        if ctx.channel == self.channel:
            await asyncio.sleep(5)
            await ctx.message.delete()

    @commands.command()
    @commands.check(admin_check)
    async def scrub_events(self, ctx, limit: int = 200):
        """<limit=200 (optional)> Clear the events channel of non-event messages.
        "limit" sets the max number of messages deleted.
        """
        n = 0
        clocks = '🕛🕧🕐🕜🕑🕝🕒🕞🕓🕟🕔🕠🕕🕡🕖🕢🕗🕣🕘🕤🕙🕥🕚🕦'
        while not self._hist_checked:
            if n == 0:
                msg = await ctx.send('Waiting for event history to be checked.')
            elif n <= len(clocks):
                await msg.add_reaction(clocks[n - 1])
            await asyncio.sleep(5)
            n += 1
        event_ids = [e.id for e in self._events]

        def check(message):
            if message.id in event_ids:
                return False
            if message.author != self.bot.user:
                return False
            return True

        await self.channel.purge(limit=limit, check=check)
        if n > 0:
            await ctx.send('Done.')

    @commands.command()
    async def traitor(self, ctx, multi: bool = False):
        """Assign and DM a traitor'"""
        t_msg = 'Traitor: You are the Traitor! Turn on your HUD, try to get the Power ' \
                'Ammo, and ready your Knives and Grenades!'
        d_msg = 'Detective: You are the Detective! Turn off your HUD. ' \
                'Equip a Kvostov and Erianas to protect the innocents.'
        i_msg = 'Innocent: There is a traitor amongst you... Keep your HUD and Ghost ' \
                'off and be sure to mute if you die.'
        roles = {t_msg: 1, d_msg: 1, i_msg: None}
        phrases = ['TTT', 'terrorist', 'traitor']
        await self.assign_rolls(ctx, roles, phrases, multi=multi)

    @commands.command()
    async def infected(self, ctx, multi: bool = False):
        """Assign and DM an infected'"""
        a_msg = 'You are the Prime Infected: get out your Stay Away and sword and start '\
                'infecting. You loose your Stay Away after one kill.'
        b_msg = 'Survivor: You’re a survivor... stay alert, they\'re coming...'
        roles = {a_msg: 1, b_msg: None}
        phrases = ['Infection', 'infected']
        await self.assign_rolls(ctx, roles, phrases, multi=multi)

    async def assign_rolls(self, ctx, roles, phrases, multi=False):
        """Assign and DM event rolls'"""
        event_name = phrases[0]
        events = [i for i in self.event_list if await i.search(phrases)]
        if len(events) > 1 and not multi:
            raise ValueError('Multiple {:} events registered.'.format(event_name))
        elif not len(events):
            raise ValueError('No {:} events registered.'.format(event_name))

        sent = []
        suf = ''
        for i, e in enumerate(events):
            if len(events) > 1:
                suf = ' ({:})'.format(i)
            attendees = await e.attendees()
            assignments = {}
            for role, num in roles.items():
                if num is None:
                    continue
                if num > 0:
                    assignments[role] = random.sample(attendees, num)
                    for a in assignments[role]:
                        attendees.remove(a)
            for role, num in roles.items():
                if num is None:
                    assignments[role] = list(attendees)[:]
                    for a in assignments[role]:
                        attendees.remove(a)
            for role, people in assignments.items():
                for person in people:
                    channel = person.dm_channel
                    if not channel:
                        await person.create_dm()
                        channel = person.dm_channel
                    await channel.send(role + suf)
                    sent.append(person.display_name)

        if sent:
            msg = '{:} event rolls sent to {:}.'.format(event_name, ', '.join(sent))
            logger.info(msg)
            await ctx.send(msg)
        else:
            raise RuntimeError('No event roll messages sent.')

    @commands.command()
    @commands.check(admin_check)
    async def make_event_stale(self, ctx, event: Union[int, str]):
        """<event id/name> Make an event stale"""
        try:
            event = int(event)
        except ValueError:
            pass
        if isinstance(event, int):
            events = [i for i in self._events if i['id'] == event]
        elif event == 'all':
            events = self._events
        else:
            events = [i for i in self._events if i.search(event)]
        out = []
        for i in events:
            await i.make_stale()
            out.append('Event {:} made stale.'.format(i['name']))
        if not out:
            out = ['No events matching "{}" found.'.format(event)]
        await split_send(ctx, out)


if usingV2:
    async def setup(bot):
        cog = Events(bot)
        await bot.add_cog(cog)
else:
    def setup(bot):
        bot.add_cog(Events(bot))
