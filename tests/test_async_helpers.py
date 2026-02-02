import asyncio
import datetime
import types

import pytest

from TDTbot import async_helpers, param


class DummyChannel:
    def __init__(self):
        self.sent = []

    async def send(self, msg):
        self.sent.append(msg)
        return msg


@pytest.mark.asyncio
async def test_split_send_chunks_and_styles():
    channel = DummyChannel()
    message = "line1\nline2\nline3"
    # force small chunk to trigger split
    out = await async_helpers.split_send(channel, message, n=12, style="```")
    assert out == ["```line1```", "```line2```", "```line3```"]
    assert channel.sent == out


@pytest.mark.asyncio
async def test_sleep_handles_http_exception(monkeypatch):
    calls = {"asyncio": 0, "time": 0}

    class FakeHTTPException(Exception):
        pass

    monkeypatch.setattr(async_helpers, "discord", types.SimpleNamespace(HTTPException=FakeHTTPException))

    async def fake_sleep(dt):
        calls["asyncio"] += 1
        raise FakeHTTPException()

    def fake_time_sleep(dt):
        calls["time"] += 1

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(async_helpers.time, "sleep", fake_time_sleep)

    await async_helpers.sleep(0.01)
    assert calls["asyncio"] == 1
    assert calls["time"] == 1


@pytest.mark.asyncio
async def test_admin_check_by_role():
    admin_role = types.SimpleNamespace(id=param.roles.admin)
    author = types.SimpleNamespace(top_role=admin_role)
    ctx = types.SimpleNamespace(author=author, guild=None)
    assert await async_helpers.admin_check(ctx=ctx)


@pytest.mark.asyncio
async def test_admin_check_owner_fallback():
    author = types.SimpleNamespace(top_role=None)
    guild = types.SimpleNamespace(owner=author)
    ctx = types.SimpleNamespace(author=author, guild=guild)
    assert await async_helpers.admin_check(ctx=ctx)


@pytest.mark.asyncio
async def test_wait_until_sleeps_once(monkeypatch):
    sleeps = []

    async def fake_sleep(dt):
        sleeps.append(dt)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    target = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
    await async_helpers.wait_until(target)
    # One sleep for remaining seconds
    assert len(sleeps) == 1
    assert sleeps[0] >= 0


@pytest.mark.asyncio
async def test_parse_payload_returns_requested_fields():
    guild = types.SimpleNamespace(id=1)
    member = types.SimpleNamespace(id=123)
    channel = types.SimpleNamespace(id=456)
    message = types.SimpleNamespace(id=789)

    bot = types.SimpleNamespace(
        guilds=[guild],
        find_channel=lambda cid: channel if cid == channel.id else None,
        fetch_channel=lambda cid: None,
        fetch_guild=lambda gid: None,
    )

    async def fake_get_or_fetch_user(uid, guild_arg):
        return member

    bot.get_or_fetch_user = fake_get_or_fetch_user

    async def fake_fetch_message(mid):
        return message

    channel.fetch_message = fake_fetch_message

    payload = types.SimpleNamespace(
        guild_id=guild.id,
        user_id=member.id,
        channel_id=channel.id,
        message_id=message.id,
        member=None,
    )

    result = await async_helpers.parse_payload(payload, bot, "guild", "member", "channel", "message")

    assert result["guild"] is guild
    assert result["member"] is member
    assert result["channel"] is channel
    assert result["message"] is message
