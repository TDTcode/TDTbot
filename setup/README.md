# Ubuntu setup

These scripts install TDTbot under `/srv/discord-bot` as the unprivileged
`discordbot` user and run it with systemd.

## Encryption requirement

All service-user data is required to be encrypted at rest. The service user's
home directory is `/srv/discord-bot`, so this includes `TDTbot/config`, the
Discord token, the service user's SSH key, logs, and any user data written by
the bot.

Use Ubuntu's installer option to encrypt the disk with LUKS, preferably with
encrypted LVM. If the host is already installed, an encrypted filesystem
mounted at `/srv` also satisfies the requirement. The installation scripts
verify that `/srv/discord-bot` is backed by a `crypt` device before creating
or configuring the service, and refuse to continue on an unencrypted host.

The disk must be unlocked before `tdtbot.service` starts. A boot-time
passphrase prompt is the simplest option. TPM2-backed automatic unlocking can
be used when unattended reboots are required, but its provisioning and
recovery policy are host-specific and are not handled by these scripts.

Do not put an encryption key or recovery passphrase inside the repository or
`/srv/discord-bot`; doing so would defeat at-rest protection. Encryption does
not protect data while the disk is unlocked and the service is running.

## Install

From an Ubuntu checkout of this repository, run the installer as root and
provide the repository URL to clone:

```sh
sudo ./setup/install.sh <repository-url>
```

The installer downloads `uv` if it is not already installed, uses it to create
the Python environment at `/srv/discord-bot/.venv`, and installs the
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
