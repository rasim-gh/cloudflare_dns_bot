#!/bin/bash

set -e

echo "🚀 نصب ربات Cloudflare DNS Telegram"

# گرفتن اطلاعات از کاربر
read -p "🤖 توکن ربات تلگرام: " bot_token
read -p "📧 ایمیل Cloudflare: " cf_email
read -p "🔑 API Key: " cf_api
read -p "👤 آیدی عددی ادمین: " admin_id

# کپی فایل config.py از template
cp config.py.template config.py

# جایگزینی مقادیر در config.py
sed -i "s|BOT_TOKEN = \"\"|BOT_TOKEN = \"$bot_token\"|" config.py
sed -i "s|CLOUDFLARE_EMAIL = \"\"|CLOUDFLARE_EMAIL = \"$cf_email\"|" config.py
sed -i "s|CLOUDFLARE_API_KEY = \"\"|CLOUDFLARE_API_KEY = \"$cf_api\"|" config.py
sed -i "s|ADMIN_ID = \"\"|ADMIN_ID = $admin_id|" config.py

echo "✅ فایل config.py ساخته شد."

# نصب ابزار لازم
apt update -y
apt install python3-venv git -y

# ساخت محیط مجازی و نصب پکیج‌ها
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# ساخت systemd سرویس
SERVICE_FILE="/etc/systemd/system/cloudflarebot.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Cloudflare DNS Telegram Bot
After=network.target

[Service]
ExecStart=$(pwd)/venv/bin/python $(pwd)/bot.py
WorkingDirectory=$(pwd)
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

# فعال‌سازی و اجرا
systemctl daemon-reload
systemctl enable cloudflarebot
systemctl restart cloudflarebot

echo "✅ نصب کامل شد!"
echo "📡 وضعیت: systemctl status cloudflarebot"
