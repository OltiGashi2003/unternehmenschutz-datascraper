#!/bin/bash

# Install Chrome dependencies for Railway
apt-get update
apt-get install -y wget gnupg
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
apt-get update
apt-get install -y google-chrome-stable

# Start the Flask app
exec gunicorn app_flask:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
