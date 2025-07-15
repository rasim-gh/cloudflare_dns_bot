import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application,CallbackQueryHandler,CommandHandler,ContextTypes,MessageHandler,filters,)
from cloudflare_api import *
from config import BOT_TOKEN, ADMIN_ID  # type: ignore

logger = logging.getLogger(__name__)

user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return await (update.message or update.callback_query.message).reply_text(
            "❌ شما اجازه دسترسی ندارید."
        )

    zones = get_zones()
    keyboard = []

    for zone in zones:
        status_icon = "✅" if zone["status"] == "active" else "❌"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{zone['name']} {status_icon}", callback_data=f"zone_{zone['id']}"
                ),
                InlineKeyboardButton("🗑", callback_data=f"confirm_delete_zone_{zone['id']}"),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton("➕ افزودن دامنه جدید", callback_data="add_domain"),
            InlineKeyboardButton("ℹ️ راهنما", callback_data="show_help"),
        ]
    )

    welcome_text = (
        "👋 به ربات مدیریت DNS خوش آمدید!\n\n"
        "🔹 یکی از دامنه‌های فعال یا غیرفعال زیر را انتخاب کنید.\n"
        "🔹 امکان افزودن، حذف و مدیریت رکوردهای DNS برای هر دامنه فراهم است.\n\n"
        "🌐 دامنه‌های متصل:"
    )

    if update.callback_query:
        msg = update.callback_query.message
        if msg.text != welcome_text:
            await msg.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 راهنمای کامل کار با ربات مدیریت DNS:\n\n"
        "1️⃣ **نمایش دامنه‌ها:**\n"
        "لیست تمامی دامنه‌هایی که در حساب کلودفلر شما موجود است نمایش داده می‌شود.\n\n"
        "2️⃣ **افزودن دامنه جدید:**\n"
        "- دکمه '➕ افزودن دامنه جدید' را بزنید.\n"
        "- نام دامنه را به صورت کامل وارد کنید (مثال: example.com).\n"
        "- ربات دامنه را به حساب کلودفلر شما اضافه می‌کند و نیم‌سرورهای آن را نمایش می‌دهد.\n\n"
        "3️⃣ **مدیریت رکوردهای DNS:**\n"
        "- پس از انتخاب دامنه، لیست رکوردهای DNS نمایش داده می‌شود.\n"
        "- می‌توانید رکورد جدید اضافه کنید، رکوردها را ویرایش یا حذف کنید.\n"
        "- برای ویرایش آی‌پی، روی دکمه آی‌پی رکورد کلیک کنید و مقدار جدید را وارد نمایید.\n"
        "- وضعیت پروکسی را با کلیک روی آیکون 🔶 یا ⚪ تغییر دهید.\n\n"
        "4️⃣ **حذف دامنه یا رکورد:**\n"
        "- دکمه سطل زباله 🗑 کنار دامنه یا رکورد را بزنید.\n"
        "- پس از تایید، آن مورد حذف خواهد شد.\n\n"
        "🔙 برای بازگشت به صفحه دامنه‌ها از دکمه 'بازگشت به دامنه‌ها' استفاده کنید.\n\n"
        "⚠️ توجه: این ربات فقط توسط مدیر (شما) قابل استفاده است."
    )

    keyboard = [
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_domains")]
    ]

    if update.callback_query:
        await update.callback_query.message.edit_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )


# بقیه توابع مثل refresh_records، handle_callback، handle_message بدون تغییر ...

async def refresh_records(uid, query_or_msg):
    # کد همانطور که قبلا بود
    zone_id = user_state[uid]["zone_id"]
    zone_name = user_state[uid].get("zone_name", "")
    records = get_dns_records(zone_id)

    text = f"📋 لیست رکوردهای DNS برای دامنه: `{zone_name}`\n\n"
    keyboard = []

    for rec in records:
        if rec["type"] in ["A", "AAAA", "CNAME"]:
            proxied_icon = "🔶" if rec.get("proxied") else "⚪"
            keyboard.append(
                [
                    InlineKeyboardButton(rec["name"], callback_data="noop"),
                    InlineKeyboardButton(rec["content"], callback_data=f"editip_{rec['id']}"),
                    InlineKeyboardButton(proxied_icon, callback_data=f"toggle_proxy_{rec['id']}"),
                    InlineKeyboardButton("🗑", callback_data=f"confirm_delete_{rec['id']}"),
                ]
            )

    keyboard.append([InlineKeyboardButton("➕ افزودن رکورد جدید", callback_data="add_record")])
    keyboard.append(
        [
            InlineKeyboardButton("🔙 بازگشت به دامنه‌ها", callback_data="back_to_domains"),
        ]
    )

    try:
        if hasattr(query_or_msg, "callback_query") and query_or_msg.callback_query:
            await query_or_msg.callback_query.message.edit_text(
                text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query_or_msg.message.reply_text(
                text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"خطا در بروزرسانی رکوردها: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data == "show_help":
        await show_help(update, context)
        return

    if data.startswith("zone_"):
        zone_id = data.split("_")[1]
        zone_info = get_zone_info_by_id(zone_id)
        user_state[uid] = {"zone_id": zone_id, "zone_name": zone_info["name"]}
        await refresh_records(uid, update)

    elif data == "back_to_domains":
        await start(update, context)

    elif data.startswith("confirm_delete_zone_"):
        zone_id = data.split("_")[-1]
        zone = get_zone_info_by_id(zone_id)
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"delete_zone_{zone_id}")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_delete")],
        ]
        await query.message.reply_text(
            f"❗ آیا مطمئنید که می‌خواهید دامنه زیر حذف شود؟\n`{zone['name']}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data.startswith("delete_zone_"):
        zone_id = data.split("_")[-1]
        success = delete_zone(zone_id)
        await query.message.reply_text("✅ دامنه حذف شد." if success else "❌ حذف انجام نشد.")
        await start(update, context)

    elif data == "cancel_delete":
        await query.message.reply_text("❎ حذف لغو شد.")

    elif data == "add_domain":
        user_state[uid] = {"mode": "adding_domain"}
        await query.message.reply_text("📝 لطفاً نام دامنه را وارد کنید (مثال: example.com):")

    elif data == "add_record":
        user_state[uid]["mode"] = "adding_record_step"
        user_state[uid]["record_step"] = 0
        user_state[uid]["record_data"] = {}
        user_state[uid]["zone_id"] = user_state[uid].get("zone_id")
        await query.message.reply_text("📌 مرحله ۱/۵: نوع رکورد را وارد کنید (مثال: A, AAAA, CNAME):")

    elif data.startswith("editip_"):
        record_id = data.split("_")[1]
        user_state[uid]["mode"] = "editing_ip"
        user_state[uid]["record_id"] = record_id
        record = get_record_details(user_state[uid]["zone_id"], record_id)
        await query.message.reply_text(
            f"📝 آی‌پی جدید برای رکورد `{record['name']}` را وارد کنید:", parse_mode="Markdown"
        )

    elif data.startswith("confirm_delete_"):
        record_id = data.split("_")[2]
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"delete_record_{record_id}")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_delete")],
        ]
        await query.message.reply_text(
            "❗ آیا مطمئنید که می‌خواهید این رکورد حذف شود؟", reply_markup=InlineKeyboardMarkup(keyboard)
        )

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

    else:
        await query.message.reply_text("⚠️ دستور ناشناخته.")

    logger.info(f"[CALLBACK] داده دریافت شده: {data}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_state.get(uid, {})

    if state.get("mode") == "adding_domain":
        domain = update.message.text.strip()
        success = add_domain_to_cloudflare(domain)
        if success:
            zone_info = get_zone_info(domain)
            ns = "\n".join(zone_info.get("name_servers", []))
            await update.message.reply_text(
                f"✅ دامنه `{domain}` با موفقیت اضافه شد.\nوضعیت: `{zone_info['status']}`\n\n🛰 نیم‌سرورها:\n`{ns}`",
                parse_mode="Markdown",
            )
            user_state[uid] = {"zone_id": zone_info["id"], "zone_name": zone_info["name"]}
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
            "📌 مرحله ۲/۵: نام رکورد را وارد کنید (مثال: sub.example.com):",
            "📌 مرحله ۳/۵: مقدار (IP یا آدرس) را وارد کنید:",
            "📌 مرحله ۴/۵: مقدار TTL را وارد کنید (مثال: 120 یا 1 برای خودکار):",
            "📌 مرحله ۵/۵: آیا پروکسی فعال باشد؟ (true/false):",
        ]

        if step < len(steps):
            if steps[step] == "ttl":
                try:
                    record_data["ttl"] = int(text)
                except ValueError:
                    await update.message.reply_text("❌ TTL باید عدد باشد.")
                    return
            else:
                record_data[steps[step]] = text

            user_state[uid]["record_step"] += 1
            if step + 1 < len(steps):
                await update.message.reply_text(prompts[step])
            else:
                zone_id = state["zone_id"]
                proxied = record_data.get("proxied", "").lower() in ["true", "1", "yes"]
                success = create_dns_record(
                    zone_id,
                    record_data["type"],
                    record_data["name"],
                    record_data["content"],
                    record_data["ttl"],
                    proxied,
                )
                await update.message.reply_text("✅ رکورد اضافه شد." if success else "❌ افزودن رکورد ناموفق بود.")
                zone_info = get_zone_info_by_id(zone_id)
                user_state[uid] = {"zone_id": zone_id, "zone_name": zone_info["name"]}
                dummy = type("Dummy", (), {"message": update.message})
                await refresh_records(uid, dummy)

    elif state.get("mode") == "editing_ip":
        new_ip = update.message.text.strip()
        zone_id = state["zone_id"]
        record_id = state["record_id"]
        record = get_record_details(zone_id, record_id)
        success = update_dns_record(
            zone_id,
            record_id,
            record["name"],
            record["type"],
            new_ip,
            record["ttl"],
            record.get("proxied", False),
        )
        await update.message.reply_text("✅ آی‌پی بروز شد." if success else "❌ بروز رسانی انجام نشد.")
        zone_info = get_zone_info_by_id(zone_id)
        user_state[uid] = {"zone_id": zone_id, "zone_name": zone_info["name"]}
        dummy = type("Dummy", (), {"message": update.message})
        await refresh_records(uid, dummy)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
