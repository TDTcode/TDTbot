# Ubuntu setup

These scripts install TDTbot under `/srv/discord-bot` as the unprivileged
`discordbot` user and run it with systemd.

## Install

From an Ubuntu checkout of this repository, run the installer as root and
provide the repository URL to clone:

```sh
sudo ./setup/install.sh <repository-url>
```

The installer downloads `uv` if it is not already installed, uses it to create
the Python 3.11 environment at `/srv/discord-bot/.venv`, and installs the
dependencies declared in `pyproject.toml`.

It reuses an existing RSA key at `/srv/discord-bot/.ssh/id_rsa` when present;
otherwise it reuses an Ed25519 key or creates one at
`/srv/discord-bot/.ssh/id_ed25519`. The installer prints the selected public
key and waits for you to add it at <https://github.com/settings/keys> before
cloning the repository. An HTTPS GitHub URL is automatically converted to its
SSH equivalent for the clone.

Create the bot token file before enabling the service:

```sh
sudo install -d -o discordbot -g discordbot /srv/discord-bot/TDTbot/config
sudoedit /srv/discord-bot/TDTbot/config/token.txt
sudo ./setup/setup.sh
```

`setup.sh` installs the systemd unit, applies token-file permissions, and
starts the service. The unit includes these restrictions:

```ini
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/discord-bot
RestrictAddressFamilies=AF_INET AF_INET6
```

## Service management

```sh
sudo systemctl status tdtbot.service
sudo systemctl restart tdtbot.service
sudo journalctl -u tdtbot.service -f
```

To stop the bot from starting at boot:

```sh
sudo systemctl disable --now tdtbot.service
```
