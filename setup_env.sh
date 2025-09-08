#!/bin/bash
# --- setup_env.sh ---
# This script fetches application secrets from Google Secret Manager
# and creates the .env file needed by the Python application.

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Fetching secrets from Secret Manager..."

# Fetch the latest version of each secret.
DISCORD_TOKEN=$(gcloud secrets versions access latest --secret="DISCORD_TOKEN")
GOOGLE_API_KEY=$(gcloud secrets versions access latest --secret="GOOGLE_API_KEY")
GCP_PROJECT_ID=$(gcloud secrets versions access latest --secret="GCP_PROJECT_ID")

# Create the .env file, overwriting the old one with fresh secrets.
cat > .env << EOL
DISCORD_TOKEN=${DISCORD_TOKEN}
GOOGLE_API_KEY=${GOOGLE_API_KEY}
GCP_PROJECT_ID=${GCP_PROJECT_ID}
EOL

echo ".env file created successfully."

