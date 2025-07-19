import logging
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application,CallbackQueryHandler,CommandHandler,ContextTypes,MessageHandler,filters,)
from cloudflare_api import *
from config import BOT_TOKEN, ADMIN_ID
from telegram import CallbackQuery, Message

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


RECORDS_PER_PAGE = 10
user_state = defaultdict(dict)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
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
        InlineKeyboardButton("ℹ️ راهنما", callback_data="show_help")
    ])

    welcome_text = (
        "👋 به ربات مدیریت DNS خوش آمدید!\n\n"
        " این ربات بهت کمک می‌کنه رکوردهای DNS دامنه‌هات رو از طریق Cloudflare به‌سادگی مدیریت کنی.\n\n"
        "✅ امکانات:\n"
        "• نمایش لیست دامنه‌ها و افزودن \n"
        "• ویرایش و افزودن رکورد (IP, TTL, Proxy)\n"
        "• حذف دامنه یا رکورد\n"
        "• بررسی وضعیت Zone\n\n\n"
        "🌐 دامنه‌های متصل:"
    )

    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        """
📘 راهنمای کامل استفاده از ربات DNS کلودفلر

ربات تلگرامی مدیریت DNS کلودفلر به شما امکان می‌دهد بدون نیاز به ورود به وب‌سایت Cloudflare، تمام عملیات موردنیاز را از طریق تلگرام انجام دهید.

📚 دکمه‌ها و عملکردشان

🧷 در منوی اصلی:
- ➕ افزودن دامنه: وارد کردن دامنه جدید (مثل example.com)
- 📃 نمایش دامنه‌ها: دیدن لیست دامنه‌های شما همراه با وضعیت فعال/غیرفعال
- ℹ️ راهنما: نمایش همین متن
- 🚪 خروج / قطع اتصال: حذف اطلاعات کاربر از ربات

🌐 در لیست دامنه‌ها:
- 🔍 مشاهده رکوردها: دیدن تمام رکوردهای DNS دامنه
- ➖ حذف دامنه: حذف دامنه از حساب کاربری (با تأیید)
- 🟢🟡 وضعیت دامنه: نمایش وضعیت active / pending

📄 در لیست رکوردها:
- 📝 ویرایش IP: تغییر IP رکورد (نوع A/AAAA)
- 🕒 تغییر TTL: انتخاب از بین 1 (خودکار)، 120، 300، 3600 ثانیه
- ☁️ تغییر پروکسی: روشن یا خاموش کردن حالت Cloudflare Proxy (ابر نارنجی یا سفید)
- ➕ افزودن رکورد جدید: امکان انتخاب نوع رکورد و وارد کردن اطلاعات
- 🗑 حذف رکورد: حذف رکورد با تأیید
- 🔙 بازگشت: برگشت به مرحله قبل

🚫 دکمه لغو (Cancel):
در تمام مراحل وارد کردن داده (مثل IP، نام دامنه، نام رکورد)، یک دکمه ❌ لغو نمایش داده می‌شود که با کلیک روی آن، فرآیند جاری متوقف شده و به منو بازمی‌گردید.

توسعه دهنده : rasim ghodrati @rasim_gh
"""
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

async def refresh_records(uid, query_or_msg, page=0):
    zone_id = user_state[uid]["zone_id"]
    zone_name = user_state[uid].get("zone_name", "")
    records = get_dns_records(zone_id)
    total_pages = (len(records) - 1) // RECORDS_PER_PAGE + 1

    text = f"📋 رکوردهای DNS دامنه: `{zone_name}`\n\n"
    start = page * RECORDS_PER_PAGE
    end = start + RECORDS_PER_PAGE
    user_state[uid]["page"] = page

    keyboard = []

    for rec in records[start:end]:
        if rec["type"] in ["A", "AAAA", "CNAME"]:
            name = rec["name"].replace(zone_name, "***")
            content = rec["content"]
            
            keyboard.append([
                InlineKeyboardButton(f"{name}", callback_data="noop"),
                InlineKeyboardButton(f"{content} | ⚙️", callback_data=f"record_settings_{rec['id']}")
            ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data="page_prev"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data="page_next"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("➕ افزودن رکورد", callback_data="add_record"),InlineKeyboardButton("🔙 بازگشت به دامنه‌ها", callback_data="back_to_domains")])
    
    try:
        msg = query_or_msg.callback_query.message if hasattr(query_or_msg, "callback_query") else query_or_msg.message
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"خطا در بروزرسانی رکوردها: {e}")


async def show_record_settings(uid, query: CallbackQuery, zone_id, record_id):
    record = get_record_details(zone_id, record_id)
    text = (
        f"⚙️ تنظیمات رکورد: `{record['name']}`\n\n"
        f"Type: `{record['type']}`\n"
        f"IP Address: `{record['content']}`\n"
        f"TTL: `{record['ttl']}`\n"
        f"Proxied: {'✅' if record.get('proxied') else '❌'}"
    )
    keyboard = [
        [
            InlineKeyboardButton("🖊 تغییر IP", callback_data=f"editip_{record_id}"),
            InlineKeyboardButton("🕒 تغییر TTL", callback_data=f"edittll_{record_id}"),
            InlineKeyboardButton("🔁 پروکسی", callback_data=f"toggle_proxy_{record_id}"),
        ],
        [
            InlineKeyboardButton("🗑 حذف", callback_data=f"confirm_delete_{record_id}"),
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_records"),
        ],
    ]
    try:
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"خطا در نمایش تنظیمات رکورد: {e}")
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")]
        ]) 
        await query.message.reply_text("📝 لطفاً نام دامنه را وارد کنید و منتظر باشید \n (مثال: example.com):", reply_markup=keyboard)
        user_state[uid]["mode"] = "adding_domain"
    
    elif data == "cancel_action":
        await query.message.edit_text("❌ عملیات لغو شد.")
        user_state.pop(uid, None)

        
    elif data == "page_next":
        current = user_state[uid].get("page", 0)
        await refresh_records(uid, update, page=current + 1)

    elif data == "page_prev":
        current = user_state[uid].get("page", 0)
        await refresh_records(uid, update, page=current - 1)

    elif data.startswith("record_settings_"):
        record_id = data.split("_")[2]
        zone_id = user_state[uid]["zone_id"]
        record = get_record_details(zone_id, record_id)
        user_state[uid]["record_id"] = record_id

        text = f"⚙️ تنظیمات رکورد: `{record['name']}`\n\nType: `{record['type']}`\nIP Address: `{record['content']}`\nTTL: `{record['ttl']}`\n Proxied: {'✅' if record.get('proxied') else '❌'}"
        keyboard = [
            [
                InlineKeyboardButton("🖊 تغییر IP", callback_data=f"editip_{record_id}"),
                InlineKeyboardButton("🕒 TTL", callback_data=f"edittll_{record_id}"),
                InlineKeyboardButton("🔁 پروکسی", callback_data=f"toggle_proxy_{record_id}"),
            ],
            [
                InlineKeyboardButton("🗑 حذف", callback_data=f"confirm_delete_{record_id}"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_records"),
            ],

        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_type_"):
        rtype = data.split("_")[2]
        user_state[uid]["record_data"]["type"] = rtype
        user_state[uid]["record_step"] = 1
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")]
        ])
        await query.message.reply_text("📌 مرحله ۲ از ۵: نام رکورد را وارد کنید (مثال: sub.example.com)", reply_markup=keyboard)
        
    elif data.startswith("select_ttl_"):
        ttl_value = int(data.split("_")[2])
        user_state[uid]["record_data"]["ttl"] = ttl_value
        user_state[uid]["record_step"] = 4
        keyboard = [
            [InlineKeyboardButton("✅ بله", callback_data="select_proxied_true"),
            InlineKeyboardButton("❌ خیر", callback_data="select_proxied_false")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")]
        ]
        await query.message.reply_text("📌 مرحله ۵ از ۵: آیا پروکسی فعال باشد؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_proxied_"):
        proxied = data.endswith("true")
        user_state[uid]["record_data"]["proxied"] = proxied
        zone_id = user_state[uid]["zone_id"]
        r = user_state[uid]["record_data"]
        success = create_dns_record(zone_id, r["type"], r["name"], r["content"], r["ttl"], r["proxied"])
        user_state[uid] = {"zone_id": zone_id, "zone_name": get_zone_info_by_id(zone_id)["name"]}
        await query.message.reply_text("✅ رکورد اضافه شد." if success else "❌ افزودن رکورد ناموفق بود.")
        await refresh_records(uid, update)

    elif data == "back_to_records":
        await refresh_records(uid, update, page=user_state[uid].get("page", 0))

    elif data.startswith("editip_"):
        record_id = data.split("_")[1]
        user_state[uid]["mode"] = "editing_ip"
        user_state[uid]["record_id"] = record_id
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")]
        ])
        await query.message.reply_text("📝 لطفاً IP جدید را وارد کنید:", reply_markup=keyboard)

    elif data.startswith("toggle_proxy_"):
        record_id = data.split("_")[2]
        zone_id = user_state[uid]["zone_id"]
        success = toggle_proxied_status(zone_id, record_id)
        if success:
            await show_record_settings(uid, query, zone_id, record_id)
        else:
            await query.answer("خطا در تغییر وضعیت پروکسی", show_alert=True)

    elif data.startswith("edittll_"):
        record_id = data.split("_")[1]
        user_state[uid]["mode"] = "editing_ttl"
        user_state[uid]["record_id"] = record_id
        keyboard = [
            [
                InlineKeyboardButton("🔁 1 (خودکار)", callback_data=f"update_ttl_{record_id}_1"),
                InlineKeyboardButton("⏱ 120 ثانیه", callback_data=f"update_ttl_{record_id}_120")
            ],
            [
                InlineKeyboardButton("⏱ 300 ثانیه", callback_data=f"update_ttl_{record_id}_300"),
                InlineKeyboardButton("🕒 3600 ثانیه", callback_data=f"update_ttl_{record_id}_3600")
            ],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")]
        ]
        await query.message.edit_text("⏱ مقدار جدید TTL را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("update_ttl_"):
        parts = data.split("_")
        record_id = parts[2]
        ttl = int(parts[3])
        zone_id = user_state[uid]["zone_id"]
        record = get_record_details(zone_id, record_id)
        success = update_dns_record(zone_id, record_id, record["name"], record["type"], record["content"], ttl, record.get("proxied", False))
        user_state[uid]["mode"] = None
        if success:
            await show_record_settings(uid, query, zone_id, record_id)
        else:
            await query.answer("خطا در به‌روزرسانی TTL", show_alert=True)
            
    elif data.startswith("confirm_delete_"):
        record_id = data.split("_")[2]
        keyboard = [
            [
            InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"delete_record_{record_id}"),
            InlineKeyboardButton("❌ لغو", callback_data="back_to_records")
            ],
           ]
        await query.message.reply_text("❗ آیا مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delete_record_"):
        record_id = data.split("_")[2]
        zone_id = user_state[uid]["zone_id"]
        delete_dns_record(zone_id, record_id)
        await refresh_records(uid, update, page=user_state[uid].get("page", 0))

    elif data == "add_record":
        user_state[uid] = {
        "mode": "adding_record_step",
        "record_step": 0,
        "record_data": {},
        "zone_id": user_state[uid]["zone_id"]
        }
        keyboard = [
            [
                InlineKeyboardButton("🔵 A", callback_data="select_type_A"),
                InlineKeyboardButton("🟢 AAAA", callback_data="select_type_AAAA"),
                InlineKeyboardButton("🔁 CNAME", callback_data="select_type_CNAME")
            ],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")],
        ]
        await query.message.reply_text("📌 مرحله ۱ از ۵: نوع رکورد را انتخاب کنید:",reply_markup=InlineKeyboardMarkup(keyboard))


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
        return
        
    if state.get("mode") == "adding_record_step":
        step = state.get("record_step", 0)
        record_data = state.get("record_data", {})
        text = update.message.text.strip()

        if step == 1:
            record_data["name"] = text
            user_state[uid]["record_step"] = 2
            keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")]
            ])
            await update.message.reply_text("📌 مرحله ۳ از ۵: مقدار رکورد را وارد کنید (مثلاً IP یا آدرس)", reply_markup=keyboard)

        elif step == 2:
            record_data["content"] = text
            user_state[uid]["record_step"] = 3
            keyboard = [
                [
                    InlineKeyboardButton("🔁 1 (خودکار)", callback_data="select_ttl_1"),
                    InlineKeyboardButton("⏱ 120 ثانیه", callback_data="select_ttl_120")
                ],
                [
                    InlineKeyboardButton("⏱ 300 ثانیه", callback_data="select_ttl_300"),
                    InlineKeyboardButton("🕒 3600 ثانیه", callback_data="select_ttl_3600")
                ],
                [InlineKeyboardButton("❌ لغو", callback_data="cancel_action")]
            ]
            await update.message.reply_text("📌 مرحله ۴ از ۵: مقدار TTL را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if state.get("mode") == "editing_ip":
        new_ip = update.message.text.strip()
        zone_id = state["zone_id"]
        record_id = state["record_id"]
        record = get_record_details(zone_id, record_id)
        update_dns_record(zone_id, record_id, record["name"], record["type"], new_ip, record["ttl"], record.get("proxied", False))
        user_state[uid]["mode"] = None
        await show_record_settings(uid, update, zone_id, record_id)
        return


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
