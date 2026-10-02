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

# python3-venv is needed to create the isolated environment. Installing these
# packages here makes the script usable on a minimal Ubuntu installation.
apt-get update
apt-get install --yes git python3 python3-venv

# Create the locked-down service account only when it does not already exist.
# --create-home also establishes /srv/discord-bot as its home directory.
if ! id "$service_user" >/dev/null 2>&1; then
    useradd --system --user-group --home-dir "$app_dir" --create-home \
        "$service_user"
fi

# Ensure the service account owns the application directory before cloning.
install -d -o "$service_user" -g "$service_user" "$app_dir"

# Do not overwrite an existing checkout. An existing non-Git directory is
# rejected so the installer cannot place files into an ambiguous deployment.
if [[ -e "$checkout_dir" ]]; then
    if [[ ! -d "$checkout_dir/.git" ]]; then
        echo "$checkout_dir exists but is not a Git checkout." >&2
        exit 1
    fi
else
    runuser -u "$service_user" -- git clone "$repo_url" "$checkout_dir"
fi

# Reuse an existing virtual environment; otherwise create one with the system
# Python. Dependencies are installed below even when the environment exists,
# making this step safe to rerun after dependency changes.
if [[ ! -x "$venv_dir/bin/python" ]]; then
    python3 -m venv "$venv_dir"
fi

# These are the runtime dependencies currently declared in environment.yaml.
# The venv keeps them separate from Ubuntu's system Python installation.
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install \
    pytz humanize numpy ephem gitpython pynacl 'tweepy[async]' 'discord.py[voice]'

# The service user must be able to read the checkout, virtual environment, and
# configuration files when systemd starts the bot.
chown -R "$service_user:$service_user" "$app_dir"
echo "Installed TDTbot in $checkout_dir. Create config/token.txt, then run setup/setup.sh."
