#!/bin/bash
set -e

echo "🚀 Downloading Cloudflare DNS Bot..."

INSTALL_DIR="/root/cloudflare_dns_bot"
rm -rf $INSTALL_DIR
git clone https://github.com/rasim-gh/cloudflare_dns_bot.git $INSTALL_DIR
cd $INSTALL_DIR
bash install.sh
