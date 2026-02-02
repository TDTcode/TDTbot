import asyncio
import types

import pytest

import TDTbot.bot as bot_module
from TDTbot.bot import MainBot


@pytest.fixture
def bot(monkeypatch):
    """
    Create a MainBot instance with discord/network calls mocked out.
    Shared across tests to avoid repetition.
    """
    # Force v2 behavior so __init__ doesn't try to load extensions immediately
    monkeypatch.setattr(bot_module, "usingV2", True)

    # Stub out load_extension to avoid touching the filesystem/network
    monkeypatch.setattr(bot_module.commands.Bot, "load_extension", lambda self, name: None)

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
