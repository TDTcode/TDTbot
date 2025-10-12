# TDTbot
A Discord bot for The Dream Team clan

### Dependancies
1) Python >= 3.5.3
2) discordpy https://discordpy.readthedocs.io/en/latest/intro.html#installing
3) gitpython https://gitpython.readthedocs.io/en/stable/intro.html
4) pytz (installable with `conda` or `pip`)
5) humanize (installable with `conda` or `pip`)

### Install
In the `config` subdirectory create a file `token.txt` with your bot's token in it. See https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token for help on bot tokens.

### Usage
- Run: `python3 -m TDTbot <optional flags>`
- Help/see options: `python3 -m TDTbot -h`

### Configuration
The default config file is `config/tdt.json`, defaults can be found near the top of `param.py`.

### Emoji Role Assignment
The bot can assign roles based on reactions to a message. To set this up add a `self.bot.enroll_emoji_role` call in `cogs/main.py` in the `__init__` function of `MainCommands`.

### Trick or Treat
A spooky game that runs on Halloween.

Intructions for initiation:
- Create a channel named "the_neighborhood" (or change the `_channel` variable in `cogs/trick_or_treat.py`)
- Create a message in `#manual_page` and copy the channel ID to `messages.trick_or_treat` in `param.py`
- Make sure `_game_on` is set to `"auto"` or `True` in `cogs/trick_or_treat.py`
- Create a role named "SPOOKY" (or change the `_role` variable in `cogs/trick_or_treat.py`)
