#!/bin/bash

INSTALL_DIR="/root/cloudflare_dns_bot"
SERVICE_NAME="cloudflarebot"

show_menu() {
  clear
  echo "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓"
  echo "┃   ⚙️ Cloudflare DNS Bot Installer  |  telegram Channel : @Utah_net"
  echo "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
  echo ""
  echo "1) 🛠  Install the bot"
  echo "2) ⚙️  Configure the bot"
  echo "3) ❌ Uninstall the bot"
  echo "0) 🚪 Exit"
  echo ""
  read -p "Your choice: " choice
}

install_bot() {
  echo "📦 Installing the bot..."
  rm -rf "$INSTALL_DIR"
  git clone https://github.com/rasim-gh/cloudflare_dns_bot.git "$INSTALL_DIR"
  cd "$INSTALL_DIR" || exit
  bash install.sh
  echo "✅ Installation completed successfully."
  read -p "⏎ Press Enter to return to the menu..." _
}

configure_bot() {
  CONFIG_FILE="$INSTALL_DIR/config.py"
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "⚠️ Config file not found. Please install the bot first."
  else
    echo "📝 Opening the config file..."
    sleep 1
    nano "$CONFIG_FILE"
    echo "🔄 Restarting the bot service..."
    systemctl restart "$SERVICE_NAME"
    echo "✅ Configuration saved and bot restarted."
  fi
  read -p "⏎ Press Enter to return to the menu..." _
}

uninstall_bot() {
  echo "❌ Uninstalling the bot completely..."
  systemctl stop "$SERVICE_NAME"
  systemctl disable "$SERVICE_NAME"
  rm -f /etc/systemd/system/"$SERVICE_NAME".service
  systemctl daemon-reload
  rm -rf "$INSTALL_DIR"
  echo "✅ Bot and all files have been removed."
  read -p "⏎ Press Enter to return to the menu..." _
}

while true; do
  show_menu
  case $choice in
    1) install_bot ;;
    2) configure_bot ;;
    3) uninstall_bot ;;
    0) echo "👋 Exiting. Goodbye!"; exit 0 ;;
    *) echo "❌ Invalid option. Please choose a valid one."; sleep 2 ;;
  esac
done
