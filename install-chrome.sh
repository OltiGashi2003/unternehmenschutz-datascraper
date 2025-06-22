#!/bin/bash
# Install Chrome for Render deployment

# Update package list
apt-get update

# Install dependencies
apt-get install -y wget gnupg2 software-properties-common

# Add Google Chrome repository
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list

# Update package list again
apt-get update

# Install Google Chrome
apt-get install -y google-chrome-stable

# Create symlink if needed
ln -sf /usr/bin/google-chrome-stable /usr/bin/google-chrome

echo "Chrome installation completed"
