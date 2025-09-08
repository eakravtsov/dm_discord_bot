#!/bin/bash
# --- setup_and_run.sh ---
# This script is executed by Cloud Build on the GCE VM.
# It runs as root (via sudo) to manage files and services, but performs
# user-specific actions as the 'discordbot' user.

# Exit immediately if a command exits with a non-zero status.
set -e

APP_DIR="/opt/apps/discord-bot"
APP_USER="discordbot"

echo "--- Starting deployment in $APP_DIR ---"

cd $APP_DIR

# --- 1. Pull Latest Code ---
echo "Pulling latest code as user '$APP_USER'..."
# Run git commands as the application user to maintain correct file ownership.
sudo -u $APP_USER git fetch --all
sudo -u $APP_USER git reset --hard origin/computeEngineVersion # Or your primary branch

# --- 2. Set Up Environment ---
echo "Fetching secrets and creating .env file..."
# This script needs to run with permissions to access the gcloud SDK.
# We'll run it as root and then set the ownership correctly.
./setup_env.sh
chown $APP_USER:$APP_USER .env
echo ".env file is ready."

# --- 3. Install/Update Dependencies ---
echo "Updating Python dependencies as user '$APP_USER'..."
# Run pip install as the application user within the virtual environment.
sudo -u $APP_USER /opt/apps/discord-bot/venv/bin/pip install -r requirements.txt
echo "Dependencies are up-to-date."

# --- 4. Restart the Service ---
echo "Restarting the discord-bot systemd service..."
systemctl restart discord-bot.service

echo "--- Deployment successful! ---"

