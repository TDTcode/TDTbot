#!/usr/bin/env bash
# Install and start the TDTbot systemd service after install.sh has completed.
#
# The token is checked before the unit is enabled so a missing credential does
# not result in a repeatedly failing service.
set -euo pipefail

# This script writes to /etc/systemd/system and changes ownership/mode of the
# bot token, so it must be run by root (normally with sudo).
if [[ ${EUID} -ne 0 ]]; then
    echo "Run this script with sudo or as root." >&2
    exit 1
fi

# These paths must match setup/install.sh and setup/tdtbot.service.
readonly app_dir=/srv/discord-bot
readonly checkout_dir="$app_dir/TDTbot"
readonly token_file="$checkout_dir/config/token.txt"
readonly service_user=discordbot
# Resolve the directory containing this script so the unit can be installed
# correctly regardless of the caller's current working directory.
readonly script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Refuse to configure a partial installation.
if [[ ! -d "$checkout_dir" ]]; then
    echo "Missing checkout: $checkout_dir. Run install.sh first." >&2
    exit 1
fi

# An empty token file would make the bot fail to authenticate. The token is
# intentionally not created by this script because it must come from the bot
# owner.
if [[ ! -s "$token_file" ]]; then
    echo "Missing or empty token file: $token_file" >&2
    exit 1
fi

# Limit access to the Discord token to the service account, then install the
# version-controlled unit file into systemd's local unit directory.
chown "$service_user:$service_user" "$token_file"
chmod 600 "$token_file"
install -m 0644 "$script_dir/tdtbot.service" \
    /etc/systemd/system/tdtbot.service
# Reload systemd's unit cache and enable/start the service immediately.
systemctl daemon-reload
systemctl enable --now tdtbot.service
systemctl --no-pager status tdtbot.service
