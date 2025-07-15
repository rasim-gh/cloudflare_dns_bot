import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from cloudflare_api import *
from config import BOT_TOKEN, ADMIN_ID

#logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await (update.message or update.callback_query.message).reply_text("❌ شما اجازه دسترسی ندارید.")

    zones = get_zones()
    keyboard = []

    for zone in zones:
        status_icon = "✅" if zone["status"] == "active" else "❌"
        keyboard.append([
            InlineKeyboardButton(f"{zone['name']} {status_icon}", callback_data=f"zone_{zone['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"confirm_delete_zone_{zone['id']}")
        ])

    keyboard.append([
        InlineKeyboardButton("➕ افزودن دامنه جدید", callback_data="add_domain"),
        InlineKeyboardButton("🔁 بروزرسانی", callback_data="refresh_domains")
    ])

    welcome_text = (
        "👋 به ربات مدیریت DNS خوش آمدی!\n\n"
        "🔹 از لیست زیر یکی از دامنه‌های فعال یا غیرفعال را انتخاب کن.\n"
        "🔹 امکان افزودن، حذف، و مدیریت رکوردها برای هر دامنه فراهمه.\n\n"
        "🌐 لیست دامنه‌های متصل:"
    )

    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def refresh_records(uid, query_or_dummy):
    zone_id = user_state[uid]["zone_id"]
    zone_name = user_state[uid].get("zone_name", "")
    records = get_dns_records(zone_id)

    text = f"📋 لیست رکوردهای دامنه: `{zone_name}`\n\n"
    keyboard = []

    for rec in records:
        if rec["type"] in ["A", "AAAA", "CNAME"]:
            proxied_icon = "🔶" if rec.get("proxied") else "⚪"
            keyboard.append([
                InlineKeyboardButton(rec["name"], callback_data="noop"),
                InlineKeyboardButton(rec["content"], callback_data=f"editip_{rec['id']}"),
                InlineKeyboardButton(proxied_icon, callback_data=f"toggle_proxy_{rec['id']}"),
                InlineKeyboardButton("🗑", callback_data=f"confirm_delete_{rec['id']}")
            ])

    keyboard.append([InlineKeyboardButton("➕ افزودن رکورد جدید", callback_data="add_record")])
    keyboard.append([
        InlineKeyboardButton("🔁 بروزرسانی رکوردها", callback_data="refresh_records"),
        InlineKeyboardButton("🔙 بازگشت به دامنه‌ها", callback_data="back_to_domains")
    ])

    try:
        if hasattr(query_or_dummy, "callback_query") and query_or_dummy.callback_query:
            await query_or_dummy.callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query_or_dummy.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"❌ Error in refresh_records: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data.startswith("zone_"):
        zone_id = data.split("_")[1]
        zone_info = get_zone_info_by_id(zone_id)
        user_state[uid] = {"zone_id": zone_id, "zone_name": zone_info["name"]}
        await refresh_records(uid, update)

    elif data == "refresh_domains" or data == "back_to_domains":
        await start(update, context)

    elif data.startswith("confirm_delete_zone_"):
        zone_id = data.split("_")[-1]
        zone = get_zone_info_by_id(zone_id)
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"delete_zone_{zone_id}")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_delete")]
        ]
        await query.message.reply_text(f"❗ آیا مطمئنی می‌خوای دامنه زیر حذف شه؟\n\n`{zone['name']}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("delete_zone_"):
        zone_id = data.split("_")[-1]
        success = delete_zone(zone_id)
        await query.message.reply_text("✅ دامنه حذف شد." if success else "❌ حذف انجام نشد.")
        await start(update, context)

    elif data == "cancel_delete":
        await query.message.reply_text("❎ حذف لغو شد.")

    elif data == "add_domain":
        user_state[uid] = {"mode": "adding_domain"}
        await query.message.reply_text("📝 لطفاً نام دامنه را وارد کن (مثال: example.com):")

    elif data == "add_record":
        user_state[uid]["mode"] = "adding_record_step"
        user_state[uid]["record_step"] = 0
        user_state[uid]["record_data"] = {}
        user_state[uid]["zone_id"] = user_state[uid].get("zone_id")  # حفظ zone_id
        await query.message.reply_text("📌 مرحله ۱/۵: نوع رکورد را وارد کن (مثال: A, AAAA, CNAME):")

    elif data.startswith("editip_"):
        record_id = data.split("_")[1]
        user_state[uid]["mode"] = "editing_ip"
        user_state[uid]["record_id"] = record_id
        record = get_record_details(user_state[uid]["zone_id"], record_id)
        await query.message.reply_text(f"📝 آی‌پی جدید برای رکورد `{record['name']}` وارد کن:", parse_mode="Markdown")

    elif data.startswith("confirm_delete_"):
        record_id = data.split("_")[2]
        user_state[uid]["record_to_delete"] = record_id
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"delete_record_{record_id}")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_delete")]
        ]
        await query.message.reply_text("❗ آیا مطمئنی می‌خوای این رکورد حذف بشه؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delete_record_"):
        record_id = data.split("_")[2]
        zone_id = user_state[uid]["zone_id"]
        success = delete_dns_record(zone_id, record_id)
        await query.message.reply_text("✅ رکورد حذف شد." if success else "❌ حذف انجام نشد.")
        await refresh_records(uid, update)

    elif data.startswith("toggle_proxy_"):
        record_id = data.split("_")[2]
        zone_id = user_state[uid]["zone_id"]
        success = toggle_proxied_status(zone_id, record_id)
        await query.message.reply_text("🔄 وضعیت پروکسی تغییر کرد." if success else "❌ خطا در تغییر وضعیت.")
        await refresh_records(uid, update)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_state.get(uid, {})

    if state.get("mode") == "adding_domain":
        domain = update.message.text.strip()
        success = add_domain_to_cloudflare(domain)
        if success:
            zone_info = get_zone_info(domain)
            ns = "\n".join(zone_info.get("name_servers", []))
            await update.message.reply_text(f"✅ دامنه `{domain}` با موفقیت اضافه شد.\nوضعیت: `{zone_info['status']}`\n\n🛰 نیم‌سرورها:\n`{ns}`", parse_mode="Markdown")
            user_state[uid] = {
                "zone_id": zone_info["id"],
                "zone_name": zone_info["name"]
            }
        else:
            await update.message.reply_text("❌ خطا در افزودن دامنه.")
            user_state.pop(uid, None)
        await start(update, context)

    elif state.get("mode") == "adding_record_step":
        step = state["record_step"]
        record_data = state["record_data"]
        text = update.message.text.strip()

        steps = ["type", "name", "content", "ttl", "proxied"]
        prompts = [
            "📌 مرحله ۲/۵: نام رکورد (مثال: sub.example.com):",
            "📌 مرحله ۳/۵: مقدار (IP یا آدرس):",
            "📌 مرحله ۴/۵: مقدار TTL (مثال: 120 یا 1 برای خودکار):",
            "📌 مرحله ۵/۵: پروکسی فعال باشد؟ (true/false):"
        ]

        if step < len(steps):
            record_data[steps[step]] = text if steps[step] != "ttl" else int(text)
            user_state[uid]["record_step"] += 1
            if step + 1 < len(steps):
                await update.message.reply_text(prompts[step])
            else:
                zone_id = state["zone_id"]
                proxied = record_data["proxied"].lower() in ["true", "1", "yes"]
                success = create_dns_record(zone_id, record_data["type"], record_data["name"], record_data["content"], record_data["ttl"], proxied)
                await update.message.reply_text("✅ رکورد افزوده شد." if success else "❌ افزودن رکورد ناموفق بود.")
                zone_info = get_zone_info_by_id(zone_id)
                user_state[uid] = {
                    "zone_id": zone_id,
                    "zone_name": zone_info["name"]
                }
                dummy = type("Dummy", (), {"message": update.message})
                await refresh_records(uid, dummy)

    elif state.get("mode") == "editing_ip":
        new_ip = update.message.text.strip()
        zone_id = state["zone_id"]
        record_id = state["record_id"]
        record = get_record_details(zone_id, record_id)
        success = update_dns_record(zone_id, record_id, record["name"], record["type"], new_ip, record["ttl"], record.get("proxied", False))
        await update.message.reply_text("✅ آی‌پی بروز شد." if success else "❌ بروز نشد.")
        zone_info = get_zone_info_by_id(zone_id)
        user_state[uid] = {
            "zone_id": zone_id,
            "zone_name": zone_info["name"]
        }
        dummy = type("Dummy", (), {"message": update.message})
        await refresh_records(uid, dummy)

if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()