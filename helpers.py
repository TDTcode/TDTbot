from .param import rc as _rc
from . import param
import re
import datetime
import pytz


epoch = datetime.datetime(2000, 1, 1)
second = datetime.timedelta(seconds=1)
minute = datetime.timedelta(seconds=60)
hour = datetime.timedelta(seconds=3600)
day = datetime.timedelta(days=1)
week = datetime.timedelta(days=7)
month = datetime.timedelta(days=30)


def find_channel(guild, channel=None):
    """Find a channel in a guild based on its name"""
    if channel is None:
        channel = _rc('channel')
    if type(channel) not in [str, int]:
        return channel
    try:
        channel = int(channel)
        try:
            return [i for i in guild.channels if i.id == channel][0]
        except IndexError:
            return
    except ValueError:
        pass
    try:
        return [i for i in guild.channels
                if i.name.lower().strip() == channel.lower().strip()][0]
    except IndexError:
        pass
    if channel.startswith('#'):
        return find_channel(guild, channel.lstrip('#'))
    if channel.startswith('<#') and channel.endswith('>'):
        return find_channel(guild, channel[2:-1])
    if channel in param.channels:
        return find_channel(guild, param.channels[channel])
    return


def find_role(guild, name):
    """Find a role in a guild based on its name"""
    try:
        if isinstance(name, int):
            return [i for i in guild.roles if i.id == name][0]
        else:
            return [i for i in guild.roles if i.name.lower() == name.lower()][0]
    except IndexError:
        return


_regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
_filetypes = dict()


def valid_url(url):
    return re.match(_regex, url) is not None


def parse_filetype(filepath: str, force_list=True):
    _types = dict(jpg="image/jpeg",
                  jpeg="image/jpeg",
                  jpx="image/jpx",
                  png="image/png",
                  gif="image/gif",
                  webp="image/webp",
                  cr2="image/x-canon-cr2",
                  tif="image/tiff",
                  bmp="image/bmp",
                  jxr="image/vnd.ms-photo",
                  psd="image/vnd.adobe.photoshop",
                  ico="image/x-icon",
                  heic="image/heic",
                  mp4="video/mp4",
                  m4v="video/x-m4v",
                  mkv="video/x-matroska",
                  webm="video/webm",
                  mov="video/quicktime",
                  avi="video/x-msvideo",
                  wmv="video/x-ms-wmv",
                  mpg="video/mpeg",
                  mpeg="video/mpeg",
                  flv="video/x-flv",
                  mid="audio/midi",
                  mp3="audio/mpeg",
                  m4a="audio/m4a",
                  ogg="audio/ogg",
                  flac="audio/x-flac",
                  wav="audio/x-wav",
                  amr="audio/amr",
                  )
    ext = filepath.split('.')[-1]
    try:
        return [ext, _types[ext]]
    except KeyError:
        for ext in _types:
            if filepath.endswith(ext):
                return [ext, _types[ext]]
    if force_list:
        return []


def parse_message(message):
    out = dict()
    out['urls'] = [i for i in message.content.split(' ') if valid_url(i)]
    try:
        out['attachments'] = [[i] + parse_filetype(i.filename, force_list=True)
                              for i in message.attachments]
    except TypeError as e:
        print(str(message.attachments))
        print(str([parse_filetype(i.filename) for i in message.attachments]))
        raise e
    out['content'] = message.content
    _type = []
    if out['urls']:
        _type.append('url')
    _type += [i[-1] for i in out['attachments']]
    if not _type:
        _type = ['normal']
    _type = sorted(list(set(_type)))
    out['type'] = _type
    return out


def emotes_equal(a, b):
    alist = [a] + [getattr(a, attr, None) for attr in ['id', 'name']] + [str(a)]
    alist = [i for i in alist if i]
    blist = [b] + [getattr(b, attr, None) for attr in ['id', 'name']] + [str(b)]
    blist = [i for i in blist if i]
    for i in alist:
        for j in blist:
            try:
                if i == j:
                    return True
            except (ValueError, TypeError):
                pass
    return False


def int_time(in_time=None, t0=None):
    if in_time is None:
        in_time = datetime.datetime.utcnow()
    if t0 is None:
        t0 = epoch
    if isinstance(t0, str) and t0.lower() == 'unix':
        t0 = 0
    if isinstance(t0, int):
        t0 = datetime.datetime.utcfromtimestamp(t0)
    return int((localize(in_time) - localize(t0)).total_seconds())


def seconds_to_datetime(in_time, t0=None, localize=True):
    if t0 is None:
        t0 = epoch
    dt = t0 + datetime.timedelta(seconds=in_time)
    localize = pytz.utc if localize is True else localize
    if localize:
        dt = localize.localize(dt)
    return dt


def parse_timezone(tz, self_call=False, check_abbr=True):
    try:
        return pytz.timezone(tz)
    except pytz.exceptions.UnknownTimeZoneError:
        pass
    if check_abbr is True:
        check_abbr = {'hst': 'US/Hawaii',
                      'hdt': 'US/Hawaii',
                      'ht': 'US/Hawaii',
                      'ahst': 'US/Alaska',
                      'ahdt': 'US/Alaska',
                      'at': 'US/Alaska',
                      'pst': 'US/Pacific',
                      'pdt': 'US/Pacific',
                      'pt': 'US/Pacific',
                      'mst': 'US/Mountain',
                      'mdt': 'US/Mountain',
                      'mt': 'US/Mountain',
                      'cst': 'US/Central',
                      'cdt': 'US/Central',
                      'ct': 'US/Central',
                      'est': 'US/Eastern',
                      'edt': 'US/Eastern',
                      'et': 'US/Eastern',
                      'cet': 'Europe/Berlin',
                      'cest': 'Europe/Berlin',
                      'eet': 'Europe/Helsinki',
                      'eest': 'Europe/Helsinki',
                      'wet': 'Europe/Lisbon',
                      'west': 'Europe/Lisbon',
                      'bst': 'Europe/London',
                      'gmt': 'Europe/London',
                      }
    if check_abbr:
        if tz.lower() in check_abbr:
            return pytz.timezone(check_abbr[tz.lower()])
    if not self_call:
        if ' ' in tz:
            return parse_timezone(tz.replace(' ', '_'), self_call=True,
                                  check_abbr=check_abbr)
    return pytz.timezone(tz)


def localize(dt):
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        try:
            return dt.astimezone(pytz.utc)
        except ValueError:
            pass
    return dt


def delocalize(dt):
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt
    return dt.astimezone(pytz.utc).replace(tzinfo=None)


def clean_string(string):
    """Remove all non-alphanumeric characters except spaces and underscores"""
    return re.sub(r'[^\w\s]', '', string).strip().lower()
