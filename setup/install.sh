#!/usr/bin/env bash
# Install TDTbot and its Python dependencies under /srv/discord-bot.
#
# This script prepares the application files but deliberately does not start
# systemd. Add config/token.txt and run setup/setup.sh after installation.
set -euo pipefail

# The script changes system users, installs apt packages, and writes under
# /srv, so it must be run by root (normally with sudo).
if [[ ${EUID} -ne 0 ]]; then
    echo "Run this script with sudo or as root." >&2
    exit 1
fi

# Keep the repository URL explicit so an accidental invocation cannot clone
# an unintended default repository.
if [[ $# -ne 1 ]]; then
    echo "Usage: sudo $0 <repository-url>" >&2
    exit 2
fi

# These paths are shared with setup/setup.sh and setup/tdtbot.service.
# The checkout is in a directory named TDTbot so `python -m TDTbot` resolves
# from the application directory used by systemd.
readonly repo_url=$1
readonly app_dir=/srv/discord-bot
readonly checkout_dir="$app_dir/TDTbot"
readonly venv_dir="$app_dir/.venv"
readonly service_user=discordbot
readonly ssh_dir="$app_dir/.ssh"
ssh_key="$ssh_dir/id_ed25519"

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return
    fi

    local installer
    installer=$(mktemp)
    trap 'rm -f "$installer"' RETURN
    curl --fail --silent --show-error --location \
        https://astral.sh/uv/install.sh --output "$installer"
    UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh "$installer" >/dev/null
    rm -f "$installer"
    command -v uv
}

# These packages make the script usable on a minimal Ubuntu installation.
apt-get update
apt-get install --yes curl git openssh-client python3

# Install uv system-wide only when it is not already available. uv can fetch
# the requested Python version when the distribution does not provide it.
readonly uv_bin=$(ensure_uv)

# Create the locked-down service account only when it does not already exist.
# --create-home also establishes /srv/discord-bot as its home directory.
if ! id "$service_user" >/dev/null 2>&1; then
    useradd --system --user-group --home-dir "$app_dir" --create-home \
        "$service_user"
fi

# Ensure the service account owns the application directory before cloning.
install -d -o "$service_user" -g "$service_user" "$app_dir"

# Give the service account its own GitHub SSH identity. The clone is held
# until the operator has uploaded the public key to GitHub, otherwise a fresh
# installation fails with an unhelpful repository-access error.
install -d -m 700 -o "$service_user" -g "$service_user" "$ssh_dir"

# Reuse an existing RSA identity when one is already present. Otherwise reuse
# an existing Ed25519 identity, or create a new Ed25519 key as the default.
if [[ -f "$ssh_dir/id_rsa" ]]; then
    ssh_key="$ssh_dir/id_rsa"
fi
if [[ ! -f "$ssh_key" ]]; then
    runuser -u "$service_user" -- ssh-keygen -q -t ed25519 -N '' \
        -C "${service_user}@$(hostname --fqdn 2>/dev/null || hostname)" \
        -f "$ssh_key"
fi
if [[ ! -f "$ssh_key.pub" ]]; then
    runuser -u "$service_user" -- ssh-keygen -y -f "$ssh_key" \
        > "$ssh_key.pub"
    chown "$service_user:$service_user" "$ssh_key.pub"
    chmod 644 "$ssh_key.pub"
fi
chown "$service_user:$service_user" "$ssh_key"
chmod 600 "$ssh_key"

# Do not overwrite an existing checkout. An existing non-Git directory is
# rejected so the installer cannot place files into an ambiguous deployment.
if [[ -e "$checkout_dir" ]]; then
    if [[ ! -d "$checkout_dir/.git" ]]; then
        echo "$checkout_dir exists but is not a Git checkout." >&2
        exit 1
    fi
else
    echo
    echo "Add this SSH key to GitHub before continuing:"
    echo "  https://github.com/settings/keys"
    echo
    cat "$ssh_key.pub"
    echo
    read -r -p "Have you uploaded this key to GitHub? [y/N] " github_key_ready
    if [[ ! "$github_key_ready" =~ ^[Yy]$ ]]; then
        echo "The GitHub SSH key must be uploaded before cloning." >&2
        exit 1
    fi

    # Accept the common HTTPS form while still cloning over SSH, so the service
    # account key is actually used. Other URLs are passed through unchanged.
    repo_url_for_clone=$repo_url
    if [[ "$repo_url" =~ ^https://github\.com/(.+)$ ]]; then
        repo_url_for_clone="git@github.com:${BASH_REMATCH[1]}"
    fi

    runuser -u "$service_user" -- env \
        GIT_SSH_COMMAND="ssh -i $ssh_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
        git clone "$repo_url_for_clone" "$checkout_dir"
fi

# Reuse an existing virtual environment; otherwise let uv select an available
# Python interpreter. The project's requires-python constraint is enforced
# when its dependencies are installed below.
if [[ ! -x "$venv_dir/bin/python" ]]; then
    runuser -u "$service_user" -- "$uv_bin" venv "$venv_dir"
fi

# Install the repository's declared runtime dependencies into the isolated
# environment. uv resolves pyproject.toml and downloads packages as needed.
runuser -u "$service_user" -- "$uv_bin" pip install \
    --python "$venv_dir/bin/python" --editable "$checkout_dir"

# The service user must be able to read the checkout, virtual environment, and
# configuration files when systemd starts the bot.
chown -R "$service_user:$service_user" "$app_dir"
echo "Installed TDTbot in $checkout_dir. Create config/token.txt, then run setup/setup.sh."
