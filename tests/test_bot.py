import asyncio
import types

import pytest
import TDTbot.bot as bot_module
from TDTbot import helpers
from TDTbot.bot import MainBot


@pytest.fixture
def bot(monkeypatch):
    """
    Create a MainBot instance with discord/network calls mocked out.
    """
    # Force v2 behavior so __init__ doesn't try to load extensions immediately
    monkeypatch.setattr(bot_module, "usingV2", True)

    # Stub out load_extension to avoid touching the filesystem/network
    monkeypatch.setattr(
        bot_module.commands.Bot, "load_extension", lambda self, name: None
    )

    # Build the bot with a fresh event loop to avoid reusing a closed loop
    loop = asyncio.new_event_loop()
    b = MainBot(loop=loop)
    if not hasattr(b, "_connection"):
        b._connection = types.SimpleNamespace()
    b._connection._guilds = {}
    b._connection.user = types.SimpleNamespace(id=0)

    yield b

    # Clean up the loop after each test
    loop.call_soon_threadsafe(loop.stop)
    loop.close()


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

    payload = types.SimpleNamespace(
        message_id=None, guild_id=guild.id, emoji="🙂", member=member, user_id=member.id
    )

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

    payload = types.SimpleNamespace(
        message_id=None, guild_id=guild.id, emoji="🙂", member=member, user_id=member.id
    )

    result = await bot.emoji2role(
        payload, {"🙂": role.id}, delete=True, remove=[other_role.id]
    )

    assert result is role
    assert role in member.removed
    assert other_role in member.removed
    assert role not in member.roles
