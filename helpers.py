from .param import rc as _rc
import re


def find_channel(guild, name=None):
    """Find a channel in a guild based on its name"""
    if name is None:
        name = _rc('channel')
    try:
        return [i for i in guild.channels
                if i.name.lower().strip() == name.lower().strip()][0]
    except IndexError:
        return


def find_role(guild, name):
    """Find a role in a guild based on its name"""
    try:
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


def parse_filetype(filepath: str):
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


def parse_message(message):
    out = dict()
    out['urls'] = [i for i in message.content.split(' ') if valid_url(i)]
    out['attachments'] = [[i] + parse_filetype(i.filename) for i in message.attachments]
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