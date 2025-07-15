#!/bin/bash

set -e

echo "🚀 Downloading Cloudflare DNS Bot..."

# مسیر نصب (پوشه مقصد)
INSTALL_DIR="/root/cloudflare_dns_bot"

# اگه از قبل وجود داره، پاکش کن
rm -rf $INSTALL_DIR

# کلون ریپو
git clone https://github.com/rasim-gh/cloudflare_dns_bot.git $INSTALL_DIR

# رفتن داخل پوشه
cd $INSTALL_DIR

# اجرای اسکریپت نصب
bash install.sh
