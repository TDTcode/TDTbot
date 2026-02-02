import datetime
import types

import pytest
import pytz

from TDTbot import helpers, param


class DummyChannel:
    def __init__(self, cid, name):
        self.id = cid
        self.name = name


class DummyGuild:
    def __init__(self, channels=None, roles=None):
        self.channels = channels or []
        self.roles = roles or []


class DummyRole:
    def __init__(self, rid, name):
        self.id = rid
        self.name = name

    def __lt__(self, other):
        # allow comparison for min_role logic elsewhere (not needed here)
        return self.id < other.id


class DummyAttachment:
    def __init__(self, filename):
        self.filename = filename


class DummyMessage:
    def __init__(self, content, attachments=None):
        self.content = content
        self.attachments = attachments or []


def test_find_channel_by_id_and_name_and_alias():
    channel_by_id = DummyChannel(1, "general")
    channel_by_name = DummyChannel(2, "random")
    guild = DummyGuild(channels=[channel_by_id, channel_by_name])

    # int id
    assert helpers.find_channel(guild, 1) is channel_by_id
    # name match
    assert helpers.find_channel(guild, "random") is channel_by_name
    # leading # should be stripped
    assert helpers.find_channel(guild, "#random") is channel_by_name
    # discord style <#id>
    assert helpers.find_channel(guild, "<#2>") is channel_by_name

    # param alias lookup (debugging exists in param.channels)
    alias_channel = DummyChannel(param.channels.debugging, "debugging")
    guild.channels.append(alias_channel)
    assert helpers.find_channel(guild, "debugging") is alias_channel


def test_find_role_by_id_and_name():
    admin = DummyRole(10, "Admin")
    user = DummyRole(20, "User")
    guild = DummyGuild(roles=[admin, user])

    assert helpers.find_role(guild, 10) is admin
    assert helpers.find_role(guild, "user") is user
    assert helpers.find_role(guild, "missing") is None


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com", True),
        ("http://localhost:8080/path", True),
        ("ftp://1.2.3.4/file", True),
        ("notaurl", False),
        ("http:/missing-slash.com", False),
    ],
)
def test_valid_url(url, expected):
    assert helpers.valid_url(url) is expected


def test_parse_filetype_known_and_unknown():
    assert helpers.parse_filetype("image.jpg") == ["jpg", "image/jpeg"]
    # Matches by ending even with extra dots
    assert helpers.parse_filetype("archive.tar.gz") == []
    # Unknown returns empty list when force_list True
    assert helpers.parse_filetype("file.unknownext") == []


def test_parse_message_collects_urls_and_attachments():
    att1 = DummyAttachment("photo.jpeg")
    att2 = DummyAttachment("clip.mp4")
    msg = DummyMessage("check this https://example.com", attachments=[att1, att2])

    parsed = helpers.parse_message(msg)

    assert parsed["content"] == msg.content
    assert parsed["urls"] == ["https://example.com"]
    assert len(parsed["attachments"]) == 2
    assert parsed["attachments"][0][1:] == ["jpeg", "image/jpeg"]
    assert parsed["attachments"][1][1:] == ["mp4", "video/mp4"]
    # type should include url plus mime types, sorted & unique
    assert "url" in parsed["type"]
    assert "image/jpeg" in parsed["type"]
    assert "video/mp4" in parsed["type"]


def test_emotes_equal_handles_objects_and_strings():
    emoji_obj = types.SimpleNamespace(id="123", name="smile")
    assert helpers.emotes_equal(emoji_obj, "123")
    assert helpers.emotes_equal(emoji_obj, "smile")
    assert helpers.emotes_equal("🙂", "🙂")
    assert not helpers.emotes_equal("🙂", "🙃")


def test_int_time_and_seconds_to_datetime_roundtrip():
    t0 = pytz.utc.localize(datetime.datetime(2020, 1, 1))
    dt = pytz.utc.localize(datetime.datetime(2020, 1, 1, 0, 0, 10))
    secs = helpers.int_time(dt, t0)
    assert secs == 10
    back = helpers.seconds_to_datetime(secs, t0=t0, localize=False)
    assert back == dt


def test_localize_and_delocalize_behavior():
    naive = datetime.datetime(2021, 1, 1, 12, 0, 0)
    aware = pytz.timezone("US/Pacific").localize(naive)

    localized_naive = helpers.localize(naive)
    assert localized_naive.tzinfo is not None
    assert localized_naive.tzinfo.utcoffset(localized_naive) == datetime.timedelta(0)

    # aware is returned unchanged
    assert helpers.localize(aware) == aware

    # delocalize removes tzinfo and converts to UTC
    pacific = pytz.timezone("US/Pacific").localize(datetime.datetime(2021, 1, 1, 4, 0, 0))
    de = helpers.delocalize(pacific)
    assert de.tzinfo is None
    assert de.hour == 12  # 4am PST is 12pm UTC


def test_parse_timezone_handles_valid_and_abbrev_and_invalid():
    tz = helpers.parse_timezone("US/Pacific")
    assert tz.zone in {"US/Pacific", "America/Los_Angeles"}

    tz_abbr = helpers.parse_timezone("pst")
    assert tz_abbr.zone in {"US/Pacific", "America/Los_Angeles"}

    with pytest.raises(pytz.UnknownTimeZoneError):
        helpers.parse_timezone("not_a_real_tz")


def test_clean_string_strips_non_alnum():
    assert helpers.clean_string("Hello, World!") == "hello world"
    assert helpers.clean_string("  $foo_bar$  ") == "foo_bar"
