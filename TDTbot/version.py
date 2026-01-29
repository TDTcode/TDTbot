import discord  # type: ignore

discord_version = [int(i) for i in discord.__version__.split('.')]
usingV2 = discord_version[0] >= 2
