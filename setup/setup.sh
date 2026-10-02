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
readonly venv_dir="$app_dir/.venv"
readonly token_file="$checkout_dir/config/token.txt"
readonly service_user=discordbot
# Resolve the directory containing this script so the unit can be installed
# correctly regardless of the caller's current working directory.
readonly script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return
    fi

    local installer
    installer=$(mktemp)
    trap 'rm -f "$installer"' RETURN
    apt-get update
    apt-get install --yes curl
    curl --fail --silent --show-error --location \
        https://astral.sh/uv/install.sh --output "$installer"
    UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh "$installer" >/dev/null
    rm -f "$installer"
    command -v uv
}

require_encrypted_storage() {
    local target=$1
    local source

    source=$(findmnt --target "$target" --noheadings --output SOURCE 2>/dev/null || true)
    if [[ -z "$source" ]] || ! lsblk --inverse --noheadings --output TYPE "$source" \
        | awk '$1 == "crypt" { found = 1 } END { exit !found }'; then
        echo "Refusing to configure the service: $target is not backed by encrypted storage." >&2
        echo "Install Ubuntu with LUKS encryption, or mount an encrypted /srv volume, then retry." >&2
        exit 1
    fi

    echo "Verified encrypted storage for $target ($source)."
}

# Check the storage again on reruns so a service cannot be configured after
# /srv has been replaced or remounted without encryption.
require_encrypted_storage "$app_dir"

# Refuse to configure a partial installation.
if [[ ! -d "$checkout_dir" ]]; then
    echo "Missing checkout: $checkout_dir. Run install.sh first." >&2
    exit 1
fi

# Keep setup rerunnable after a dependency change and support hosts where uv
# was not present when install.sh was run. uv selects the available Python;
# pyproject.toml supplies the project's compatibility constraint.
readonly uv_bin=$(ensure_uv)
if [[ ! -x "$venv_dir/bin/python" ]]; then
    runuser -u "$service_user" -- "$uv_bin" venv "$venv_dir"
fi
runuser -u "$service_user" -- "$uv_bin" pip install \
    --python "$venv_dir/bin/python" --editable "$checkout_dir"

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
