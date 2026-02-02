import datetime
import types

import pytest
import pytz

import TDTbot.bot as bot_module
from TDTbot import helpers, param


def test_bot_initializes_with_defaults(bot):
    # Case-insensitive is forced
    assert bot.case_insensitive is True

    # Command prefix comes from param.rc defaults
    prefixes = bot.command_prefix
    # discord.py stores prefixes internally; normalize to list for comparison
    if not isinstance(prefixes, (list, tuple)):
        prefixes = [prefixes]
    assert prefixes  # not empty

    # Reissue and startup are set
    assert bot.reissue is None
    assert bot.startup is not None


def test_find_channel_by_id_uses_guild_lookup(bot, monkeypatch):
    channel = types.SimpleNamespace(id=123, name="general")

    class FakeGuild:
        def __init__(self, chan):
            self.chan = chan
            self.id = 1
            self.channels = [chan]

        def get_channel(self, cid):
            return self.chan if cid == self.chan.id else None

    guild = FakeGuild(channel)
    bot._connection._guilds = {guild.id: guild}

    # Ensure bot-level get_channel returns None so guild path is exercised
    bot.get_channel = lambda cid: None

    found = bot.find_channel(123)
    assert found is channel


def test_find_channel_by_name_uses_helpers(bot, monkeypatch):
    channel = types.SimpleNamespace(id=321, name="random")

    class FakeGuild:
        def __init__(self, chan):
            self.chan = chan
            self.id = 2
            self.channels = [chan]

    guild = FakeGuild(channel)
    bot._connection._guilds = {guild.id: guild}

    def fake_find_channel(guild_obj, name):
        return channel if name == "random" else None

    monkeypatch.setattr(helpers, "find_channel", fake_find_channel)

    found = bot.find_channel("random")
    assert found is channel


@pytest.mark.asyncio
async def test_get_or_fetch_user_prefers_cached_member(bot, monkeypatch):
    member = types.SimpleNamespace(id=555, name="cached")

    class FakeGuild:
        def __init__(self, member_obj):
            self.member_obj = member_obj
            self.id = 9

        def get_member(self, uid):
            return self.member_obj if uid == self.member_obj.id else None

        async def fetch_member(self, uid):
            return None

    guild = FakeGuild(member)
    bot._connection._guilds = {guild.id: guild}

    # Ensure bot cache/fetch methods won't be used
    bot.get_user = lambda uid: None

    async def fake_fetch_user(uid):
        return None

    bot.fetch_user = fake_fetch_user

    result = await bot.get_or_fetch_user(member.id, guild=guild)
    assert result is member


@pytest.mark.asyncio
async def test_get_or_fetch_user_fetches_when_not_cached(bot, monkeypatch):
    member = types.SimpleNamespace(id=777, name="fetched")

    class FakeGuild:
        def __init__(self, member_obj):
            self.member_obj = member_obj
            self.id = 10

        def get_member(self, uid):
            return None

        async def fetch_member(self, uid):
            return self.member_obj if uid == self.member_obj.id else None

    guild = FakeGuild(member)
    bot._connection._guilds = {guild.id: guild}

    bot.get_user = lambda uid: None

    async def fake_fetch_user(uid):
        return None

    bot.fetch_user = fake_fetch_user

    result = await bot.get_or_fetch_user(member.id, guild=guild)
    assert result is member


@pytest.mark.asyncio
async def test_get_or_fetch_user_fallback(bot, monkeypatch):
    """
    When nothing is found and fallback=True, return the raw user_id.
    """

    class FakeGuild:
        def __init__(self):
            self.id = 11

        def get_member(self, uid):
            return None

        async def fetch_member(self, uid):
            return None

    guild = FakeGuild()
    bot._connection._guilds = {guild.id: guild}

    bot.get_user = lambda uid: None

    async def fake_fetch_user(uid):
        return None

    bot.fetch_user = fake_fetch_user

    user_id = 999999
    result = await bot.get_or_fetch_user(user_id, guild=guild, fallback=True)
    assert result == user_id


@pytest.mark.asyncio
async def test_emoji2role_adds_role_on_match(bot, monkeypatch):
    role = types.SimpleNamespace(id=1, name="role")

    class FakeMember:
        def __init__(self):
            self.id = 100
            self.roles = []
            self.added = []
            self.removed = []
            self.top_role = role

        async def add_roles(self, r):
            self.added.append(r)
            self.roles.append(r)

        async def remove_roles(self, r):
            self.removed.append(r)
            if r in self.roles:
                self.roles.remove(r)

    member = FakeMember()

    class FakeGuild:
        def __init__(self, r):
            self.id = 12
            self.roles = [r]

        def get_member(self, uid):
            return member if uid == member.id else None

    guild = FakeGuild(role)
    bot._connection._guilds = {guild.id: guild}

    payload = types.SimpleNamespace(message_id=None, guild_id=guild.id, emoji="🙂", member=member, user_id=member.id)

    result = await bot.emoji2role(payload, {"🙂": role.id})
    assert result is role
    assert role in member.added


@pytest.mark.asyncio
async def test_emoji2role_delete_removes_role(bot, monkeypatch):
    role = types.SimpleNamespace(id=2, name="deleteme")
    other_role = types.SimpleNamespace(id=3, name="other")

    class FakeMember:
        def __init__(self):
            self.id = 200
            self.roles = [role, other_role]
            self.added = []
            self.removed = []
            self.top_role = role

        async def add_roles(self, r):
            self.added.append(r)
            self.roles.append(r)

        async def remove_roles(self, r):
            self.removed.append(r)
            if r in self.roles:
                self.roles.remove(r)

    member = FakeMember()

    class FakeGuild:
        def __init__(self, r1, r2):
            self.id = 13
            self.roles = [r1, r2]

        def get_member(self, uid):
            return member if uid == member.id else None

    guild = FakeGuild(role, other_role)
    bot._connection._guilds = {guild.id: guild}

    payload = types.SimpleNamespace(message_id=None, guild_id=guild.id, emoji="🙂", member=member, user_id=member.id)

    result = await bot.emoji2role(payload, {"🙂": role.id}, delete=True, remove=[other_role.id])

    assert result is role
    assert role in member.removed
    assert other_role in member.removed
    assert role not in member.roles


@pytest.mark.asyncio
async def test_bot_check_respects_ignore_list(bot):
    ctx = types.SimpleNamespace(channel=types.SimpleNamespace(name="devoted_chat"))
    assert await bot.bot_check(ctx) is False

    ctx2 = types.SimpleNamespace(channel=types.SimpleNamespace(name="not_ignored"))
    assert await bot.bot_check(ctx2) is True


def test_enroll_emoji_role_validates_inputs(bot):
    with pytest.raises(ValueError):
        bot.enroll_emoji_role()
    with pytest.raises(ValueError):
        bot.enroll_emoji_role(123)

    bot.enroll_emoji_role({"🙂": 1}, some_kw=True)
    assert bot._emoji_role_data[-1][0][0] == {"🙂": 1}
    assert bot._emoji_role_data[-1][1]["some_kw"] is True


def test_tdt_returns_guild_and_raises(bot):
    guild = types.SimpleNamespace(id=param.guilds.tdt)
    bot._connection._guilds = {guild.id: guild}
    assert bot.tdt() is guild

    bot._connection._guilds = {}
    with pytest.raises(RuntimeError):
        bot.tdt()


def test_restart_time_prefers_reissue_message(bot):
    bot.startup = pytz.utc.localize(datetime.datetime(2020, 1, 1, 0, 0, 0))
    reissue_msg = types.SimpleNamespace(created_at=datetime.datetime(2021, 1, 1, 12, 0, 0))
    bot.reissue = types.SimpleNamespace(message=reissue_msg)

    result = bot.restart_time()
    assert result == pytz.utc.localize(reissue_msg.created_at)


@pytest.mark.asyncio
async def test_emoji2role_respects_min_role(bot):
    class Role:
        def __init__(self, rid):
            self.id = rid
            self.name = str(rid)

        def __lt__(self, other):
            return self.id < other.id

    low = Role(1)
    high = Role(2)

    class Member:
        def __init__(self):
            self.id = 10
            self.roles = []
            self.added = []
            self.removed = []
            self.top_role = low

        async def add_roles(self, r):
            self.added.append(r)
            self.roles.append(r)

        async def remove_roles(self, r):
            self.removed.append(r)

    member = Member()

    class FakeGuild:
        def __init__(self):
            self.id = 14
            self.roles = [low, high]

        def get_member(self, uid):
            return member if uid == member.id else None

    guild = FakeGuild()
    bot._connection._guilds = {guild.id: guild}

    payload = types.SimpleNamespace(message_id=None, guild_id=guild.id, emoji="🙂", member=member, user_id=member.id)

    result = await bot.emoji2role(payload, {"🙂": high.id}, min_role=high.id)
    assert result is None
    assert member.added == []
    assert member.roles == []


@pytest.mark.asyncio
async def test_emoji2role_multiple_matches_returns_none(bot):
    role = types.SimpleNamespace(id=5, name="role")

    class Member:
        def __init__(self):
            self.id = 20
            self.roles = [role]
            self.added = []
            self.removed = []
            self.top_role = role

        async def add_roles(self, r):
            self.added.append(r)

        async def remove_roles(self, r):
            self.removed.append(r)

    member = Member()

    class FakeGuild:
        def __init__(self):
            self.id = 15
            self.roles = [role]

        def get_member(self, uid):
            return member if uid == member.id else None

    guild = FakeGuild()
    bot._connection._guilds = {guild.id: guild}

    class HashableEmoji:
        def __init__(self, name):
            self.name = name

        def __hash__(self):
            return hash(self.name)

    second_key = HashableEmoji("🙂")
    payload = types.SimpleNamespace(message_id=None, guild_id=guild.id, emoji="🙂", member=member, user_id=member.id)

    result = await bot.emoji2role(payload, {"🙂": role.id, second_key: role.id})
    assert result is None
    assert member.added == []


@pytest.mark.asyncio
async def test_get_user_configs_uses_fetch_user(bot, monkeypatch):
    files = ["/tmp/111.json", "/tmp/222.json"]
    monkeypatch.setattr(bot_module, "get_all_user_config_files", lambda: files)

    captured = []

    async def fake_fetch_user(uid):
        captured.append(uid)
        return types.SimpleNamespace(id=uid)

    bot.fetch_user = fake_fetch_user

    class FakeUserConfig:
        def __init__(self, user):
            self.user = user

    monkeypatch.setattr(bot_module, "UserConfig", FakeUserConfig)

    configs = await bot.get_user_configs()
    assert [uc.user.id for uc in configs] == [111, 222]
    assert captured == [111, 222]
