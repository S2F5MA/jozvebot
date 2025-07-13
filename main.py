import telebot
from telebot import types
import os
import threading
from flask import Flask
import time
from dotenv import load_dotenv
load_dotenv()

# ===============================================================
# بخش ۱: تنظیمات اصلی و امنیتی 🔐
# ===============================================================

TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise ValueError("⚠️ توکن ربات (BOT_TOKEN) در متغیرهای محیطی یافت نشد.")

bot = telebot.TeleBot(TOKEN)
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", None)

# دیکشنری برای ذخیره حالت کاربران
user_states = {}

# ===============================================================
# بخش ۲: کد مربوط به بیدار نگه داشتن ربات (Keep-Alive) ⏰
# ===============================================================

app = Flask(__name__)

@app.route('/')
def keep_alive_page():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    if os.getenv("ENV") == "production":
        from gunicorn.app.base import BaseApplication
        class FlaskApplication(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()
            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key.lower(), value)
            def load(self):
                return self.application
        options = {
            "bind": f"0.0.0.0:{port}",
            "workers": 1,
        }
        FlaskApplication(app, options).run()
    else:
        app.run(host="0.0.0.0", port=port)

# ===============================================================
# بخش ۳: مدیریت گروه‌های مدیا
# ===============================================================

media_groups = {}
media_group_timers = {}

def process_media_group(group_id):
    messages_to_process = media_groups.pop(group_id, [])
    media_group_timers.pop(group_id, None)

    if not messages_to_process:
        return
    
    messages_to_process.sort(key=lambda m: m.message_id)
    chat_id = messages_to_process[0].chat.id
    bot.send_message(chat_id, f"یک گروه مدیا با {len(messages_to_process)} فایل دریافت شد. در حال پردازش...")
    
    for message in messages_to_process:
        handle_single_file(message)

@bot.message_handler(content_types=['photo', 'video'])
def handle_media(message):
    if message.media_group_id:
        group_id = message.media_group_id
        
        if group_id not in media_groups:
            media_groups[group_id] = []
        
        media_groups[group_id].append(message)
        
        if group_id in media_group_timers:
            media_group_timers[group_id].cancel()
        
        timer = threading.Timer(2.0, process_media_group, args=[group_id])
        media_group_timers[group_id] = timer
        timer.start()
    else:
        handle_single_file(message)

# ===============================================================
# بخش ۴: تمام هندلرهای ربات 🤖
# ===============================================================

@bot.message_handler(content_types=['document', 'video', 'photo', 'audio', 'voice'])
def handle_single_file(message):
    file_id, file_type = (None, None)
    if message.document:
        file_id, file_type = message.document.file_id, "📄 Document"
    elif message.video:
        file_id, file_type = message.video.file_id, "🎬 Video"
    elif message.photo:
        file_id, file_type = message.photo[-1].file_id, "🖼️ Photo"
    elif message.audio:
        file_id, file_type = message.audio.file_id, "🎵 Audio"
    elif message.voice:
        file_id, file_type = message.voice.file_id, "🎤 Voice"

    if file_id:
        bot.send_message(message.chat.id, f"{file_type}\n`{file_id}`", parse_mode='Markdown')

@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_states[message.from_user.id] = 'HOME'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 ترم 1"), types.KeyboardButton("📗 ترم 2"))
    bot.send_message(message.chat.id, """سلام 👋
قبل اینکه شروع کنی، اینو بگم: برای هر درس، ما دو نوع فایل داریم: "جزوه اصلی" و "فایل ضمیمه". فایل ضمیمه شامل نکات و مطالبی است که در طول کلاس مطرح شده‌اند و در جزوه اصلی موجود نیستند.
حالا لطفاً ترم مورد نظرت رو انتخاب کن:""", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📘 ترم 1")
def show_term1_subjects(message):
    user_states[message.from_user.id] = 'TERM_1'
    bot.send_message(message.chat.id, "⚠️ منابع ترم ۱ هنوز آماده نشده‌اند. لطفاً بعداً بررسی کنید.")
    send_welcome(message)

@bot.message_handler(func=lambda msg: msg.text == "📗 ترم 2")
def show_term2_subjects(message):
    user_states[message.from_user.id] = 'TERM_2'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["🦷 سلامت دهان و جامعه", "⚛️ فیزیک پزشکی", "💀 علوم تشریح 2", "🧬 ژنتیک", "⚗️ بیوشیمی", "📜 فرهنگ و تمدن اسلام", "💓 فیزیولوژی 1", "🕌 اندیشه اسلامی 1", "🔙 بازگشت به خانه"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم درس؟ 🤔", reply_markup=markup)


# ---- سلامت دهان و جامعه ----
@bot.message_handler(func=lambda msg: msg.text == "🦷 سلامت دهان و جامعه" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_oral_health_professor_menu(message):
    user_states[message.from_user.id] = 'ORAL_HEALTH_PROFESSOR'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👨‍🏫 استاد بخشنده"), types.KeyboardButton ("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "لطفاً انتخاب کن:", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 استاد بخشنده" and user_states.get(msg.from_user.id) == 'ORAL_HEALTH_PROFESSOR')
def show_professor_files_menu(message):
    user_states[message.from_user.id] = 'ORAL_HEALTH_FILES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton("📊 پاور"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم فایل رو می‌خوای؟", reply_markup=markup)



@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'ORAL_HEALTH_FILES')
def handle_reference(message):
    bot.send_document(message.chat.id, "BQACAgQAAxkBAAIC6WhywHEWz-jjoycdtxUJd1lkWImtAAJqKgAC5xNAUuqduCpdbgpDNgQ")
    user_states[message.from_user.id] = 'WAITING_FOR_REFERENCE_FILE'


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'ORAL_HEALTH_FILES')
def handle_power_files(message):
    power_file_ids = [
        "BQACAgQAAxkBAAICnWhyvGXqxdKBi5wcl4OYp6Kp5AABbQACahgAAu7giVHRNigLwirKXzYE",
        "BQACAgQAAxkBAAICnGhyvGXpb0gusp8aGdpeC7PJJKEuAAJoGAAC7uCJUWBmMNVfHnRfNgQ",
        "BQACAgQAAxkBAAICnmhyvGV9b742-2Z8xmLZM93a4F_5AAIMGQAC4HfQUTCEMHQhD1DmNgQ",
        "BQACAgQAAxkBAAICn2hyvGXo_OL4M7nLF8nHKW3R4dDIAAKnGAACi8jRU-rG_3UsdNGoNgQ",
        "BQACAgQAAxkBAAICoGhyvGX4EV1guL5Nh_ygnyBtiGamAAKpGAACi8jRUyE183QHVLhtNgQ",
        "BQACAgQAAxkBAAICoWhyvGU2QMGYieCBNsM8EZUTUmBpAAIILAACByp4UAyFu7tnreHwNgQ",
        "BQACAgQAAxkBAAIComhyvGVbGaIAAXEg6S6jV99zbyWp9QACBywAAgcqeFByAw4JEsX67jYE",
        "BQACAgQAAxkBAAICo2hyvGWhEUYIGcCPaTsap0R9k1QuAAJ-GAACbGn4UG-eHNGSKBlDNgQ",
        "BQACAgQAAxkBAAICpGhyvGUJF4RCPA68oHYCYoZNDJxRAAJ9GAACbGn4UNsq1X8KrKrqNgQ",
        "BQACAgQAAxkBAAICpWhyvGX2wz2G9ZLbgVt8X5AaWP1PAAJBGQACSuNIUeivzx1VzcsiNgQ"
    ]
    
    bot.send_message(message.chat.id, "📊 اینم پاورهای مربوط به استاد بخشنده:")
    
    for file_id in power_file_ids:
        try:
            bot.send_document(message.chat.id, file_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❗ خطا در ارسال فایل: {e}")

# --- هندلرهای درس علوم تشریح 2 ---
@bot.message_handler(func=lambda msg: msg.text == "💀 علوم تشریح 2" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_anatomy_menu(message):
    user_states[message.from_user.id] = 'ANATOMY'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧠 نظری"), types.KeyboardButton("🦴 عملی"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم بخش؟ 🤔", reply_markup=markup)

# --- زیرمنوهای بخش نظری ---
@bot.message_handler(func=lambda msg: msg.text == "🧠 نظری" and user_states.get(msg.from_user.id) == 'ANATOMY')
def show_anatomy_theory_section(message):
    user_states[message.from_user.id] = 'ANATOMY_THEORY'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🦴 آناتومی (استاد نوروزیان )"), types.KeyboardButton("🔬 بافت‌شناسی (استاد منصوری )"), types.KeyboardButton("👶 جنین‌شناسی (استاد کرمیان )"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم مبحث؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🦴 آناتومی (استاد نوروزیان )" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY')
def show_anatomy_section_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_SECTION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton("🎬 ویدیو"), types.KeyboardButton("📊 پاور"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'ANATOMY_SECTION')
def handle_anatomy_power_files(message):
    power_file_ids = [
        "BQACAgQAAxkBAAIDG2hzABd1anatomy1",  # 🟡 جایگزین کن با File ID واقعی
        "BQACAgQAAxkBAAIDHWHzABd2anatomy2",  # 🟡 جایگزین کن با File ID واقعی
        "BQACAgQAAxkBAAIDHmHzABd3anatomy3",  # 🟡 جایگزین کن با File ID واقعی
    ]

    bot.send_message(message.chat.id, "📊 اینم پاورهای مربوط به استاد نوروزیان:")

    for file_id in power_file_ids:
        try:
            bot.send_document(message.chat.id, file_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❗ خطا در ارسال فایل: {e}")

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'ANATOMY_SECTION')
def show_anatomy_resources_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton("📄 جزوات جامع"), types.KeyboardButton("📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'ANATOMY_RESOURCES')
def send_anatomy_reference(message):
    reference_file_ids = [
        "BQACAgQAAxkBAAIDNWHzANRefAnatomy1",  # 🟡 جایگزین کن با File ID واقعی
        "BQACAgQAAxkBAAIDNmHzANRefAnatomy2",  # 🟡 جایگزین کن با File ID واقعی
    ]

    bot.send_message(message.chat.id, "📘 اینم رفرنس‌های آناتومی استاد نوروزیان:")

    for file_id in reference_file_ids:
        try:
            bot.send_document(message.chat.id, file_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❗ خطا در ارسال فایل: {e}")

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوات جامع" and user_states.get(msg.from_user.id) == 'ANATOMY_RESOURCES')
def show_anatomy_theory_comprehensive_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_THEORY_COMPREHENSIVE'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📎 فایل ضمیمه"),
        types.KeyboardButton("📄 جزوه 403"),
        types.KeyboardButton("📄 جزوه 402"),
        types.KeyboardButton("🔙 بازگشت به منوی قبلی")
    )
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📎 فایل ضمیمه" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_COMPREHENSIVE')
def send_anatomy_attachment_file(message):
    file_ids = [
        "BQACAgQAAxkBAAIDOWHzAttachFile1",  # 🟡 جایگزین کن با فایل آیدی واقعی
    ]
    bot.send_message(message.chat.id, "📎 فایل ضمیمه اینجاست:")

    for file_id in file_ids:
        try:
            bot.send_document(message.chat.id, file_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❗ خطا در ارسال فایل: {e}")

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه 403" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_COMPREHENSIVE')
def send_anatomy_note_402(message):
    file_ids = [
        "BQACAgQAAxkBAAIDPmHzNote402File1",  # 🟡 جایگزین کن با فایل آیدی واقعی
    ]
    bot.send_message(message.chat.id, "📄 اینم جزوه 403:")

    for file_id in file_ids:
        try:
            bot.send_document(message.chat.id, file_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❗ خطا در ارسال فایل: {e}")

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه 402" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_COMPREHENSIVE')
def send_anatomy_note_401(message):
    file_ids = [
        "BQACAgQAAxkBAAIDQGHzyNote401File1",  # 🟡 جایگزین کن با فایل آیدی واقعی
    ]
    bot.send_message(message.chat.id, "📄 اینم جزوه 402:")

    for file_id in file_ids:
        try:
            bot.send_document(message.chat.id, file_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❗ خطا در ارسال فایل: {e}")

@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'ANATOMY_RESOURCES')
def show_anatomy_theory_sessions_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_THEORY_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = [
        "1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم",
        "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم",
        "1️⃣1️⃣ جلسه یازدهم", "1️⃣2️⃣ جلسه دوازدهم", "1️⃣3️⃣ جلسه سیزدهم", "1️⃣4️⃣ جلسه چهاردهم", "1️⃣5️⃣ جلسه پانزدهم",
        "🔙 بازگشت به منوی قبلی"
    ]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

def send_anatomy_session_file(message, session_num, file_ids):
    bot.send_message(message.chat.id, f"📄 جلسه {session_num}:")
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id)

# جلسات 1 تا 15
@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session1(message): send_anatomy_session_file(message, "اول", ["<FILE_ID_1>"])

@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session2(message): send_anatomy_session_file(message, "دوم", ["<FILE_ID_2>"])

@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session3(message): send_anatomy_session_file(message, "سوم", ["<FILE_ID_3>"])

@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session4(message): send_anatomy_session_file(message, "چهارم", ["<FILE_ID_4>"])

@bot.message_handler(func=lambda msg: msg.text == "5️⃣ جلسه پنجم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session5(message): send_anatomy_session_file(message, "پنجم", ["<FILE_ID_5>"])

@bot.message_handler(func=lambda msg: msg.text == "6️⃣ جلسه ششم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session6(message): send_anatomy_session_file(message, "ششم", ["<FILE_ID_6>"])

@bot.message_handler(func=lambda msg: msg.text == "7️⃣ جلسه هفتم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session7(message): send_anatomy_session_file(message, "هفتم", ["<FILE_ID_7>"])

@bot.message_handler(func=lambda msg: msg.text == "8️⃣ جلسه هشتم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session8(message): send_anatomy_session_file(message, "هشتم", ["<FILE_ID_8>"])

@bot.message_handler(func=lambda msg: msg.text == "9️⃣ جلسه نهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session9(message): send_anatomy_session_file(message, "نهم", ["<FILE_ID_9>"])

@bot.message_handler(func=lambda msg: msg.text == "🔟 جلسه دهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session10(message): send_anatomy_session_file(message, "دهم", ["<FILE_ID_10>"])

@bot.message_handler(func=lambda msg: msg.text == "1️⃣1️⃣ جلسه یازدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session11(message): send_anatomy_session_file(message, "یازدهم", ["<FILE_ID_11>"])

@bot.message_handler(func=lambda msg: msg.text == "1️⃣2️⃣ جلسه دوازدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session12(message): send_anatomy_session_file(message, "دوازدهم", ["<FILE_ID_12>"])

@bot.message_handler(func=lambda msg: msg.text == "1️⃣3️⃣ جلسه سیزدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session13(message): send_anatomy_session_file(message, "سیزدهم", ["<FILE_ID_13>"])

@bot.message_handler(func=lambda msg: msg.text == "1️⃣4️⃣ جلسه چهاردهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session14(message): send_anatomy_session_file(message, "چهاردهم", ["<FILE_ID_14>"])

@bot.message_handler(func=lambda msg: msg.text == "1️⃣5️⃣ جلسه پانزدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session15(message): send_anatomy_session_file(message, "پانزدهم", ["<FILE_ID_15>"])


@bot.message_handler(func=lambda msg: msg.text == "🔬 بافت‌شناسی (استاد منصوری )" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY')
def show_histology_section_menu(message):
    user_states[message.from_user.id] = 'HISTOLOGY_SECTION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📊 پاور"), types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'HISTOLOGY_SECTION')
def send_histology_powerpoints(message):
    # فایل آیدی‌های پاورپوینت‌ها
    power_file_ids = [
        "<FILE_ID_1>",
        "<FILE_ID_2>",
        "<FILE_ID_3>",
        # ... در صورت نیاز فایل‌های بیشتر اضافه کن
    ]
    bot.send_message(message.chat.id, "📊 پاورپوینت‌های استاد منصوری:")

    for file_id in power_file_ids:
        bot.send_document(message.chat.id, file_id)

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'HISTOLOGY_SECTION')
def show_histology_resources_menu(message):
    user_states[message.from_user.id] = 'HISTOLOGY_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton("📑 خلاصه فصول تدریس شده"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'HISTOLOGY_RESOURCES')
def send_histology_references(message):
    reference_file_ids = [
        "<REF_FILE_ID_1>",
        "<REF_FILE_ID_2>",
        # فایل‌های بیشتر در صورت نیاز
    ]
    bot.send_message(message.chat.id, "📘 رفرنس‌های بافت‌شناسی:")

    for file_id in reference_file_ids:
        bot.send_document(message.chat.id, file_id)

@bot.message_handler(func=lambda msg: msg.text == "📑 خلاصه فصول تدریس شده" and user_states.get(msg.from_user.id) == 'HISTOLOGY_RESOURCES')
def send_histology_chapter_summaries(message):
    summary_file_ids = [
        "<SUMMARY_FILE_ID_1>",
        "<SUMMARY_FILE_ID_2>",
        "<SUMMARY_FILE_ID_3>",
        # ادامه بده اگر بیشتر داری
    ]
    bot.send_message(message.chat.id, "📑 خلاصه فصول تدریس‌شده استاد منصوری:")

    for file_id in summary_file_ids:
        bot.send_document(message.chat.id, file_id)

@bot.message_handler(func=lambda msg: msg.text == "👶 جنین‌شناسی (استاد کرمیان )" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY')
def show_embryology_section_menu(message):
    user_states[message.from_user.id] = 'EMBRYOLOGY_SECTION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📄 جزوه استاد"), types.KeyboardButton("📘 رفرنس"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه استاد" and user_states.get(msg.from_user.id) == 'EMBRYOLOGY_SECTION')
def send_embryology_prof_notes(message):
    prof_notes_file_ids = [
        "<EMBRYO_PROF_NOTE_ID_1>",
        "<EMBRYO_PROF_NOTE_ID_2>",
        # می‌تونی فایل‌های بیشتری اضافه کنی
    ]
    bot.send_message(message.chat.id, "📄 جزوات استاد کرمیان:")

    for file_id in prof_notes_file_ids:
        bot.send_document(message.chat.id, file_id)

@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'EMBRYOLOGY_SECTION')
def send_embryology_references(message):
    reference_file_ids = [
        "<EMBRYO_REF_FILE_ID_1>",
        "<EMBRYO_REF_FILE_ID_2>",
        # ادامه بده در صورت نیاز
    ]
    bot.send_message(message.chat.id, "📘 رفرنس‌های پیشنهادی برای جنین‌شناسی:")

    for file_id in reference_file_ids:
        bot.send_document(message.chat.id, file_id)

# --- زیرمنوهای بخش عملی ---
@bot.message_handler(func=lambda msg: msg.text == "🦴 عملی" and user_states.get(msg.from_user.id) == 'ANATOMY')
def show_anatomy_practical_section(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🦴 آناتومی ( استاد سلطانی )"), types.KeyboardButton("🔬 بافت‌شناسی (استاد  )"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم مبحث؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🦴 آناتومی ( استاد سلطانی )" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL')
def show_anatomy_practical_subsection(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_SUB'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton("🎬 ویدیو"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🎬 ویدیو" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_SUB')
def show_anatomy_practical_video_sessions(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_VIDEO_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in [
    "1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم",
    "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم",
    "1️⃣1️⃣ جلسه یازدهم"])
def send_anatomy_practical_video(message):
    video_file_ids = {
        "1️⃣ جلسه اول": "<VIDEO_FILE_ID_1>",
        "2️⃣ جلسه دوم": "<VIDEO_FILE_ID_2>",
        "3️⃣ جلسه سوم": "<VIDEO_FILE_ID_3>",
        "4️⃣ جلسه چهارم": "<VIDEO_FILE_ID_4>",
        "5️⃣ جلسه پنجم": "<VIDEO_FILE_ID_5>",
        "6️⃣ جلسه ششم": "<VIDEO_FILE_ID_6>",
        "7️⃣ جلسه هفتم": "<VIDEO_FILE_ID_7>",
        "8️⃣ جلسه هشتم": "<VIDEO_FILE_ID_8>",
        "9️⃣ جلسه نهم": "<VIDEO_FILE_ID_9>",
        "🔟 جلسه دهم": "<VIDEO_FILE_ID_10>",
        "1️⃣1️⃣ جلسه یازدهم": "<VIDEO_FILE_ID_11>",
    }
    selected = message.text
    file_id = video_file_ids.get(selected)
    if file_id:
        bot.send_video(message.chat.id, file_id)
    else:
        bot.send_message(message.chat.id, "❗ فایل ویدیویی این جلسه موجود نیست.")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_SUB')
def show_anatomy_practical_resources_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 جزوات جامع"), types.KeyboardButton("📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📚 جزوات جامع" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_RESOURCES')
def show_anatomy_practical_comprehensive_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_COMPREHENSIVE'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🎓 جزوه 401"), types.KeyboardButton("🎓 جزوه 403"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم جزوه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["🎓 جزوه 401", "🎓 جزوه 403"] and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_COMPREHENSIVE')
def send_anatomy_practical_comprehensive_file(message):
    file_ids = {
        "🎓 جزوه 401": "<FILE_ID_401>",
        "🎓 جزوه 403": "<FILE_ID_403>"
    }
    file_id = file_ids.get(message.text)
    if file_id:
        bot.send_document(message.chat.id, file_id)
    else:
        bot.send_message(message.chat.id, "❗ فایل مورد نظر یافت نشد.")
    
@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_RESOURCES')
def show_anatomy_practical_sessions_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in [
    "1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم",
    "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم",
    "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم",
    "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم"
] and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_SESSIONS')
def send_anatomy_practical_session_file(message):
    file_ids = {
        "1️⃣ جلسه اول": "<FILE_ID_SESSION_1>",
        "2️⃣ جلسه دوم": "<FILE_ID_SESSION_2>",
        "3️⃣ جلسه سوم": "<FILE_ID_SESSION_3>",
        "4️⃣ جلسه چهارم": "<FILE_ID_SESSION_4>",
        "5️⃣ جلسه پنجم": "<FILE_ID_SESSION_5>",
        "6️⃣ جلسه ششم": "<FILE_ID_SESSION_6>",
        "7️⃣ جلسه هفتم": "<FILE_ID_SESSION_7>",
        "8️⃣ جلسه هشتم": "<FILE_ID_SESSION_8>",
        "9️⃣ جلسه نهم": "<FILE_ID_SESSION_9>",
        "🔟 جلسه دهم": "<FILE_ID_SESSION_10>",
        "1️⃣1️⃣ جلسه یازدهم": "<FILE_ID_SESSION_11>"
    }
    file_id = file_ids.get(message.text)
    if file_id:
        bot.send_document(message.chat.id, file_id)
    else:
        bot.send_message(message.chat.id, "❗ فایل این جلسه هنوز بارگذاری نشده.")

@bot.message_handler(func=lambda msg: msg.text == "🔬 بافت‌شناسی (استاد  )" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL')
def show_histology_practical_subsection(message):
    user_states[message.from_user.id] = 'HISTOLOGY_PRACTICAL_SUB'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton("🎬 ویدیو"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🎬 ویدیو" and user_states.get(msg.from_user.id) == 'HISTOLOGY_PRACTICAL_SUB')
def send_histology_practical_video(message):
    user_states[message.from_user.id] = 'HISTOLOGY_PRACTICAL_VIDEO'
    file_id = "<FILE_ID_Video_Histology_Practical>"  # ← اینجا آی‌دی ویدیو رو قرار بده
    bot.send_video(message.chat.id, file_id, caption="🎥 ویدیوی بافت‌شناسی عملی (استاد)")

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'HISTOLOGY_PRACTICAL_SUB')
def show_histology_practical_resources_menu(message):
    user_states[message.from_user.id] = 'HISTO_PRACTICAL_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("📄 جزوه کلی"), types.KeyboardButton("📄 جزوه جلسه اول"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه کلی" and user_states.get(msg.from_user.id) == 'HISTO_PRACTICAL_RESOURCES')
def send_histology_practical_general_notes(message):
    # لیست چند فایل جزوه کلی
    file_ids = [
        "<FILE_ID_1>",  # ← این‌ها رو با file_id واقعی جایگزین کن
        "<FILE_ID_2>",
        "<FILE_ID_3>"
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📄 جزوه کلی بافت‌شناسی عملی")

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه جلسه اول" and user_states.get(msg.from_user.id) == 'HISTO_PRACTICAL_RESOURCES')
def send_histology_practical_first_session_notes(message):
    # لیست چند فایل جزوه جلسه اول
    file_ids = [
        "<FILE_ID_4>",
        "<FILE_ID_5>"
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📄 جزوه جلسه اول بافت‌شناسی عملی")

# --- هندلرهای درس ژنتیک ---
@bot.message_handler(func=lambda msg: msg.text == "🧬 ژنتیک" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_genetics_menu(message):
    user_states[message.from_user.id] = 'GENETICS_MENU'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["👩‍🏫 استاد صیاد", "👨‍🏫 استاد یاسایی", "👨‍🏫 استاد عمرانی", "👨‍🏫 استاد قادریان", "🔙 بازگشت به دروس"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم استاد؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "👩‍🏫 استاد صیاد" and user_states.get(msg.from_user.id) == 'GENETICS_MENU')
def show_sayyad_menu(message):
    user_states[message.from_user.id] = 'GENETICS_SAYYAD'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه", "🔙 بازگشت به منوی ژنتیک")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD')
def send_genetics_sayyad_comprehensive_notes(message):
    file_ids = [
        "<FILE_ID_1>",  # ← این‌ها رو با file_idهای واقعی جایگزین کن
        "<FILE_ID_2>"
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📚 جزوه جامع استاد صیاد - ژنتیک")


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD')
def show_sayyad_sessions_menu(message):
    user_states[message.from_user.id] = 'GENETICS_SAYYAD_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD_SESSIONS')
def send_sayyad_session1(message):
    file_ids = ["<FILE_ID_1>", "<FILE_ID_2>"]  # ← جایگزین با file_idهای واقعی
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه اول - استاد صیاد")

@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD_SESSIONS')
def send_sayyad_session2(message):
    file_ids = ["<FILE_ID_3>", "<FILE_ID_4>"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه دوم - استاد صیاد")

@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD_SESSIONS')
def send_sayyad_session3(message):
    file_ids = ["<FILE_ID_5>", "<FILE_ID_6>"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه سوم - استاد صیاد")

@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 استاد یاسایی" and user_states.get(msg.from_user.id) == 'GENETICS_MENU')
def show_yasaei_menu(message):
    user_states[message.from_user.id] = 'GENETICS_YASAEI'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه", "🔙 بازگشت به منوی ژنتیک")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI')
def send_yasaei_full_note(message):
    file_ids = ["<FILE_ID_1>", "<FILE_ID_2>"]  # ← اینجا فایل‌آیدی‌ها رو بذار
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📚 جزوه جامع - استاد یاسایی")

@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI')
def show_yasaei_sessions_menu(message):
    user_states[message.from_user.id] = 'GENETICS_YASAEI_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_1(message):
    file_ids = ["<FILE_ID_1>"]  # فایل‌آیدی‌های جلسه اول
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه اول - استاد یاسایی")

@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_2(message):
    file_ids = ["<FILE_ID_2>"]  # فایل‌آیدی‌های جلسه دوم
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه دوم - استاد یاسایی")

@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_3(message):
    file_ids = ["<FILE_ID_3>"]  # فایل‌آیدی‌های جلسه سوم
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه سوم - استاد یاسایی")

@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_4(message):
    file_ids = ["<FILE_ID_4>"]  # فایل‌آیدی‌های جلسه چهارم
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه چهارم - استاد یاسایی")

@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 استاد عمرانی" and user_states.get(msg.from_user.id) == 'GENETICS_MENU')
def show_omrani_menu(message):
    user_states[message.from_user.id] = 'GENETICS_OMRANI'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("❓ نمونه‌سوالات", "🔙 بازگشت به منوی ژنتیک")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "❓ نمونه‌سوالات" and user_states.get(msg.from_user.id) == 'GENETICS_OMRANI')
def send_omrani_questions(message):
    file_ids = ["<FILE_ID_1>", "<FILE_ID_2>", "<FILE_ID_3>"]  # جایگزین با فایل‌آیدی‌های واقعی
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="❓ نمونه‌سوالات - استاد عمرانی")

@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 استاد قادریان" and user_states.get(msg.from_user.id) == 'GENETICS_MENU')
def show_ghaderian_menu(message):
    user_states[message.from_user.id] = 'GENETICS_GHADERIAN'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 پاور", "📚 منابع مطالعاتی", "🔙 بازگشت به منوی ژنتیک")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN')
def send_ghaderian_powerpoints(message):
    file_ids = ["<FILE_ID_1>", "<FILE_ID_2>", "<FILE_ID_3>"]  # اینجا فایل‌آیدی‌های پاورپوینت‌ها رو بزار
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📊 پاور - استاد قادریان")

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN')
def show_ghaderian_resources_menu(message):
    user_states[message.from_user.id] = 'GENETICS_GHADERIAN_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📘 رفرنس", "📑 خلاصه رفرنس", "🔙 بازگشت به منوی قبلی")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN_RESOURCES')
def send_ghaderian_references(message):
    file_ids = ["<REF_FILE_ID_1>", "<REF_FILE_ID_2>"]  # جایگزین فایل‌آیدی‌های رفرنس
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📘 رفرنس - استاد قادریان")

@bot.message_handler(func=lambda msg: msg.text == "📑 خلاصه رفرنس" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN_RESOURCES')
def send_ghaderian_reference_summaries(message):
    file_ids = ["<SUMMARY_FILE_ID_1>", "<SUMMARY_FILE_ID_2>"]  # جایگزین فایل‌آیدی‌های خلاصه رفرنس
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📑 خلاصه رفرنس - استاد قادریان")

# --- هندلرهای درس بیوشیمی ---
@bot.message_handler(func=lambda msg: msg.text == "⚗️ بیوشیمی" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_biochemistry_menu(message):
    user_states[message.from_user.id] = 'BIOCHEMISTRY'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("⚗️ بیوشیمی نظری 2"), types.KeyboardButton("🧫 بیوشیمی عملی"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم بخش؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "⚗️ بیوشیمی نظری 2" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY')
def show_biochemistry_theory_menu(message):
    user_states[message.from_user.id] = 'BIOCHEMISTRY_THEORY'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📊 پاور"), types.KeyboardButton("📄 جزوه استاد"), types.KeyboardButton("🔙 بازگشت به منوی بیوشیمی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY_THEORY')
def send_biochemistry_powerpoints(message):
    file_ids = ["<POWERPOINT_FILE_ID_1>", "<POWERPOINT_FILE_ID_2>"]  # فایل‌آیدی‌های پاورپوینت
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📊 پاور بیوشیمی نظری 2")

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه استاد" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY_THEORY')
def send_biochemistry_lecturer_notes(message):
    file_ids = ["<LECTURE_NOTE_FILE_ID_1>", "<LECTURE_NOTE_FILE_ID_2>"]  # فایل‌آیدی‌های جزوه استاد
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📄 جزوه استاد بیوشیمی نظری 2")

@bot.message_handler(func=lambda msg: msg.text == "🧫 بیوشیمی عملی" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY')
def show_biochemistry_practical_menu(message):
    user_states[message.from_user.id] = 'BIOCHEMISTRY_PRACTICAL'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("📄 جزوه استاد"), types.KeyboardButton("🔙 بازگشت به منوی بیوشیمی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه استاد" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY_PRACTICAL')
def send_biochemistry_practical_lecturer_notes(message):
    file_ids = ["<BIOCHEMISTRY_PRACTICAL_LECTURE_NOTE_FILE_ID_1>", "<BIOCHEMISTRY_PRACTICAL_LECTURE_NOTE_FILE_ID_2>"]  # فایل‌آیدی‌های جزوه استاد بیوشیمی عملی
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📄 جزوه استاد بیوشیمی عملی")

# --- هندلرهای درس فیزیک پزشکی ---
@bot.message_handler(func=lambda msg: msg.text == "⚛️ فیزیک پزشکی" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_physics_menu(message):
    user_states[message.from_user.id] = 'PHYSICS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton("📊 پاور"), types.KeyboardButton("🎤 ویس"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'PHYSICS')
def send_physics_powers(message):
    file_ids = [
        "<PHYSICS_POWERPOINT_FILE_ID_1>",
        "<PHYSICS_POWERPOINT_FILE_ID_2>",
        # فایل‌آیدی‌های بیشتر پاورپوینت‌ها
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📊 پاور فیزیک پزشکی")

@bot.message_handler(func=lambda msg: msg.text == "🎤 ویس" and user_states.get(msg.from_user.id) == 'PHYSICS')
def send_physics_voice_notes(message):
    file_ids = [
        "<PHYSICS_VOICE_FILE_ID_1>",
        "<PHYSICS_VOICE_FILE_ID_2>",
        # فایل‌آیدی‌های بیشتر ویس‌ها
    ]
    for file_id in file_ids:
        bot.send_voice(message.chat.id, file_id, caption="🎤 ویس فیزیک پزشکی")

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSICS')
def show_physics_resources_menu(message):
    user_states[message.from_user.id] = 'PHYSICS_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("❓ نمونه سوال"), types.KeyboardButton("📄 جزوات جامع"), types.KeyboardButton("📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی فیزیک پزشکی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "❓ نمونه سوال" and user_states.get(msg.from_user.id) == 'PHYSICS_RESOURCES')
def send_physics_sample_questions(message):
    file_ids = [
        "<PHYSICS_SAMPLE_QUESTION_FILE_ID_1>",
        "<PHYSICS_SAMPLE_QUESTION_FILE_ID_2>",
        # فایل‌آیدی‌های بیشتر نمونه سوالات
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="❓ نمونه سوال فیزیک پزشکی")

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوات جامع" and user_states.get(msg.from_user.id) == 'PHYSICS_RESOURCES')
def show_physics_comprehensive_menu(message):
    user_states[message.from_user.id] = 'PHYSICS_COMPREHENSIVE'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🎓 جزوه ورودی 401"), types.KeyboardButton("📎 فایل ضمیمه"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🎓 جزوه ورودی 401" and user_states.get(msg.from_user.id) == 'PHYSICS_COMPREHENSIVE')
def send_physics_401_notes(message):
    file_ids = [
        "<PHYSICS_401_NOTE_FILE_ID_1>",
        "<PHYSICS_401_NOTE_FILE_ID_2>",
        # فایل‌آیدی‌های بیشتر جزوه 401
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="🎓 جزوه ورودی 401 فیزیک پزشکی")

@bot.message_handler(func=lambda msg: msg.text == "📎 فایل ضمیمه" and user_states.get(msg.from_user.id) == 'PHYSICS_COMPREHENSIVE')
def send_physics_attached_files(message):
    file_ids = [
        "<PHYSICS_ATTACHED_FILE_ID_1>",
        "<PHYSICS_ATTACHED_FILE_ID_2>",
        # فایل‌آیدی‌های بیشتر فایل ضمیمه
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📎 فایل ضمیمه فیزیک پزشکی")

@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSICS_RESOURCES')
def show_physics_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSICS_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "1️⃣2️⃣ جلسه دوازدهم", "1️⃣3️⃣ جلسه سیزدهم", "🔙 بازگشت به منابع فیزیک پزشکی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in [
    "1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم",
    "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم",
    "1️⃣1️⃣ جلسه یازدهم", "1️⃣2️⃣ جلسه دوازدهم", "1️⃣3️⃣ جلسه سیزدهم"
] and user_states.get(msg.from_user.id) == 'PHYSICS_SESSIONS')
def send_physics_session_files(message):
    session_files = {
        "1️⃣ جلسه اول": ["FILE_ID_1_1", "FILE_ID_1_2"],  # اگر چند فایل دارید
        "2️⃣ جلسه دوم": ["FILE_ID_2"],
        "3️⃣ جلسه سوم": ["FILE_ID_3"],
        "4️⃣ جلسه چهارم": ["FILE_ID_4"],
        "5️⃣ جلسه پنجم": ["FILE_ID_5"],
        "6️⃣ جلسه ششم": ["FILE_ID_6"],
        "7️⃣ جلسه هفتم": ["FILE_ID_7"],
        "8️⃣ جلسه هشتم": ["FILE_ID_8"],
        "9️⃣ جلسه نهم": ["FILE_ID_9"],
        "🔟 جلسه دهم": ["FILE_ID_10"],
        "1️⃣1️⃣ جلسه یازدهم": ["FILE_ID_11"],
        "1️⃣2️⃣ جلسه دوازدهم": ["FILE_ID_12"],
        "1️⃣3️⃣ جلسه سیزدهم": ["FILE_ID_13"],
    }
    files = session_files.get(message.text)
    if files:
        for file_id in files:
            bot.send_document(message.chat.id, file_id)
    else:
        bot.send_message(message.chat.id, "فایلی برای این جلسه وجود ندارد.")

# --- هندلرهای درس فیزیولوژی 1 ---
@bot.message_handler(func=lambda msg: msg.text == "💓 فیزیولوژی 1" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_physiology_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_MENU'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["🔬 سلول (استاد گشادرو)", "❤️ قلب (استاد زردوز)", "🍔 گوارش (استاد قاسمی)", "🩸 گردش خون (استاد حسین‌مردی)", "🔙 بازگشت به دروس"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم بخش؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🔬 سلول (استاد گشادرو)" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_MENU')
def show_physiology_cell_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CELL'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 پاور", "📚 منابع مطالعاتی", "🔙 بازگشت به منوی فیزیولوژی")
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CELL')
def send_physiology_cell_powerpoint(message):
    for file_id in physiology_cell_powers:
        bot.send_document(message.chat.id, file_id)

physiology_cell_powers = [
    "FILE_ID_POW_1",
    "FILE_ID_POW_2",
    "FILE_ID_POW_3",
]

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CELL')
def show_physiology_cell_resources(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CELL_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📄 جزوه استاد", "🔙 بازگشت به منوی سلول")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

# فایل ایدی‌های جزوه استاد برای بخش سلول (استاد گشادرو)
physiology_cell_teacher_notes = [
    "FILE_ID_JOZVE_1",
    "FILE_ID_JOZVE_2",
    "FILE_ID_JOZVE_3",
]

@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه استاد" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CELL_RESOURCES')
def send_physiology_cell_teacher_notes(message):
    for file_id in physiology_cell_teacher_notes:
        bot.send_document(message.chat.id, file_id)


@bot.message_handler(func=lambda msg: msg.text == "❤️ قلب (استاد زردوز)" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_MENU')
def show_physiology_heart_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_HEART'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 پاور", "📚 منابع مطالعاتی", "🔙 بازگشت به منوی فیزیولوژی")
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

# فایل ایدی‌های پاور برای بخش قلب (استاد زردوز)
physiology_heart_powerpoints = [
    "FILE_ID_POWERPOINT_1",
    "FILE_ID_POWERPOINT_2",
    "FILE_ID_POWERPOINT_3",
]

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART')
def send_physiology_heart_powerpoints(message):
    for file_id in physiology_heart_powerpoints:
        bot.send_document(message.chat.id, file_id)

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART')
def show_physiology_heart_resources(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_HEART_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه", "🔙 بازگشت به منوی قلب")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

# فایل ایدی جزوه جامع قلب
physiology_heart_comprehensive_note_file_id = "FILE_ID_JOZVE_JAME_HEART"

@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART_RESOURCES')
def send_physiology_heart_comprehensive_note(message):
    bot.send_document(message.chat.id, physiology_heart_comprehensive_note_file_id)

    
@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART_RESOURCES')
def show_zardouz_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_HEART_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

# فایل ایدی جزوات جلسات قلب (استاد زردوز)
physiology_heart_session_files = {
    "1️⃣ جلسه اول": "FILE_ID_SESSION_1_HEART",
    "2️⃣ جلسه دوم": "FILE_ID_SESSION_2_HEART",
    "3️⃣ جلسه سوم": "FILE_ID_SESSION_3_HEART",
}

@bot.message_handler(func=lambda msg: msg.text in physiology_heart_session_files and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART_SESSIONS')
def send_physiology_heart_session_file(message):
    file_id = physiology_heart_session_files.get(message.text)
    if file_id:
        bot.send_document(message.chat.id, file_id)
    else:
        bot.send_message(message.chat.id, "متأسفانه این جلسه فایل ندارد.")

@bot.message_handler(func=lambda msg: msg.text == "🍔 گوارش (استاد قاسمی)" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_MENU')
def show_physiology_digestion_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_DIGESTION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 پاور", "📚 منابع مطالعاتی", "🔙 بازگشت به منوی فیزیولوژی")
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION')
def send_physiology_digestion_power_files(message):
    file_ids = [
        "<PHYSIOLOGY_DIGESTION_POWER_FILE_ID_1>",
        "<PHYSIOLOGY_DIGESTION_POWER_FILE_ID_2>",
        "<PHYSIOLOGY_DIGESTION_POWER_FILE_ID_3>",
        # فایل آیدی‌های بیشتر پاور گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📊 پاور گوارش (استاد قاسمی)")

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION')
def show_physiology_digestion_resources(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_DIGESTION_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه", "🔙 بازگشت به منوی گوارش")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_RESOURCES')
def send_physiology_digestion_comprehensive_files(message):
    file_ids = [
        "<PHYSIOLOGY_DIGESTION_COMPREHENSIVE_FILE_ID_1>",
        "<PHYSIOLOGY_DIGESTION_COMPREHENSIVE_FILE_ID_2>",
        "<PHYSIOLOGY_DIGESTION_COMPREHENSIVE_FILE_ID_3>",
        # فایل آیدی‌های بیشتر جزوه جامع گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📚 جزوه جامع گوارش (استاد قاسمی)")

@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_RESOURCES')
def show_ghasemi_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_DIGESTION_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session1_files(message):
    file_ids = [
        "<PHYSIOLOGY_DIGESTION_SESSION1_FILE_ID_1>",
        "<PHYSIOLOGY_DIGESTION_SESSION1_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه اول گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جزوه جلسه اول گوارش (استاد قاسمی)")

@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session2_files(message):
    file_ids = [
        "<PHYSIOLOGY_DIGESTION_SESSION2_FILE_ID_1>",
        "<PHYSIOLOGY_DIGESTION_SESSION2_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه دوم گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جزوه جلسه دوم گوارش (استاد قاسمی)")

@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session3_files(message):
    file_ids = [
        "<PHYSIOLOGY_DIGESTION_SESSION3_FILE_ID_1>",
        "<PHYSIOLOGY_DIGESTION_SESSION3_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه سوم گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جزوه جلسه سوم گوارش (استاد قاسمی)")

@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session4_files(message):
    file_ids = [
        "<PHYSIOLOGY_DIGESTION_SESSION4_FILE_ID_1>",
        "<PHYSIOLOGY_DIGESTION_SESSION4_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه چهارم گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جزوه جلسه چهارم گوارش (استاد قاسمی)")

@bot.message_handler(func=lambda msg: msg.text == "🩸 گردش خون (استاد حسین‌مردی)" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_MENU')
def show_physiology_circulation_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CIRCULATION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 پاور", "📚 منابع مطالعاتی", "🔙 بازگشت به منوی فیزیولوژی")
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION')
def send_circulation_powerpoint_files(message):
    file_ids = [
        "<PHYSIOLOGY_CIRCULATION_POWERPOINT_FILE_ID_1>",
        "<PHYSIOLOGY_CIRCULATION_POWERPOINT_FILE_ID_2>",
        # فایل آیدی‌های بیشتر پاور گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📊 پاور گردش خون (استاد حسین‌مردی)")

@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION')
def show_physiology_circulation_resources(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CIRCULATION_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه", "🔙 بازگشت به منوی گردش خون")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_RESOURCES')
def send_circulation_comprehensive_notes(message):
    file_ids = [
        "<PHYSIOLOGY_CIRCULATION_COMPREHENSIVE_NOTE_FILE_ID_1>",
        "<PHYSIOLOGY_CIRCULATION_COMPREHENSIVE_NOTE_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جزوه جامع گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📚 جزوه جامع گردش خون (استاد حسین‌مردی)")

@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_RESOURCES')
def show_hosseinmardi_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CIRCULATION_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_1(message):
    file_ids = [
        "<PHYSIOLOGY_CIRCULATION_SESSION_1_FILE_ID_1>",
        "<PHYSIOLOGY_CIRCULATION_SESSION_1_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه اول گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه اول گردش خون (استاد حسین‌مردی)")

@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_2(message):
    file_ids = [
        "<PHYSIOLOGY_CIRCULATION_SESSION_2_FILE_ID_1>",
        "<PHYSIOLOGY_CIRCULATION_SESSION_2_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه دوم گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه دوم گردش خون (استاد حسین‌مردی)")

@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_3(message):
    file_ids = [
        "<PHYSIOLOGY_CIRCULATION_SESSION_3_FILE_ID_1>",
        "<PHYSIOLOGY_CIRCULATION_SESSION_3_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه سوم گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه سوم گردش خون (استاد حسین‌مردی)")

@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_4(message):
    file_ids = [
        "<PHYSIOLOGY_CIRCULATION_SESSION_4_FILE_ID_1>",
        "<PHYSIOLOGY_CIRCULATION_SESSION_4_FILE_ID_2>",
        # فایل آیدی‌های بیشتر جلسه چهارم گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id, caption="📝 جلسه چهارم گردش خون (استاد حسین‌مردی)")

# --- هندلرهای درس اندیشه اسلامی 1 ---
@bot.message_handler(func=lambda msg: msg.text == "🕌 اندیشه اسلامی 1" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_islamic_thought_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_MENU'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧕 بانوان"), types.KeyboardButton("🧔 آقایان"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم گروه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🧕 بانوان" and user_states.get(msg.from_user.id) == 'ISLAMIC_THOUGHT_MENU')
def show_islamic_thought_women_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_WOMEN'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton("📚 جزوه جامع"), types.KeyboardButton("📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی اندیشه"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'ISLAMIC_THOUGHT_WOMEN')
def show_islamic_thought_women_sessions_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_WOMEN_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🧔 آقایان" and user_states.get(msg.from_user.id) == 'ISLAMIC_THOUGHT_MENU')
def show_islamic_thought_men_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_MEN'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("❓ نمونه سوالات"), types.KeyboardButton("🔙 بازگشت به منوی اندیشه"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

# --- هندلرهای درس فرهنگ و تمدن اسلام ---
@bot.message_handler(func=lambda msg: msg.text == "📜 فرهنگ و تمدن اسلام" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_islamic_culture_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_CULTURE_MENU'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("❓ نمونه سوالات"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

# --- هندلرهای بازگشت (نسخه اصلاح شده و کامل) ---
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به دروس" and user_states.get(msg.from_user.id) in ['ORAL_HEALTH_PROFESSOR', 'PHYSICS', 'ANATOMY', 'BIOCHEMISTRY', 'GENETICS_MENU', 'PHYSIOLOGY_MENU', 'ISLAMIC_THOUGHT_MENU', 'ISLAMIC_CULTURE_MENU'])
def back_to_term2_subjects(message):
    show_term2_subjects(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به خانه")
def back_home(message):
    send_welcome(message)

# بازگشت‌های سلامت دهان و جامعه
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) in ['ORAL_HEALTH_FILES'])
def back_to_oral_health_professor_menu(message):
    show_oral_health_professor_menu(message)

# بازگشت‌های بیوشیمی
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی بیوشیمی" and user_states.get(msg.from_user.id) in ['BIOCHEMISTRY_THEORY', 'BIOCHEMISTRY_PRACTICAL'])
def back_to_biochemistry_menu(message):
    show_biochemistry_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) in ['ANATOMY_THEORY', 'ANATOMY_PRACTICAL'])
def back_to_anatomy_main_menu(message):
    show_anatomy_menu(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) in ['ANATOMY_SECTION', 'HISTOLOGY_SECTION', 'EMBRYOLOGY_SECTION'])
def back_to_anatomy_theory_menu(message):
    show_anatomy_theory_section(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'ANATOMY_RESOURCES')
def back_to_anatomy_section_menu(message):
    show_anatomy_section_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) in ['ANATOMY_THEORY_COMPREHENSIVE', 'ANATOMY_THEORY_SESSIONS'])
def back_to_anatomy_resources_menu(message):
    show_anatomy_resources_menu(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'HISTOLOGY_RESOURCES')
def back_to_histology_section_menu(message):
    show_histology_section_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) in ['ANATOMY_PRACTICAL_SUB', 'HISTOLOGY_PRACTICAL_SUB'])
def back_to_anatomy_practical_menu(message):
    show_anatomy_practical_section(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) in ['ANATOMY_PRACTICAL_RESOURCES', 'ANATOMY_PRACTICAL_VIDEO_SESSIONS'])
def back_to_anatomy_practical_subsection(message):
    show_anatomy_practical_subsection(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) in ['ANATOMY_PRACTICAL_SESSIONS', 'ANATOMY_PRACTICAL_COMPREHENSIVE'])
def back_to_anatomy_practical_resources(message):
    show_anatomy_practical_resources_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'HISTO_PRACTICAL_RESOURCES')
def back_to_histology_practical_subsection(message):
    show_histology_practical_subsection(message)

# بازگشت‌های ژنتیک
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی ژنتیک" and user_states.get(msg.from_user.id) in ['GENETICS_SAYYAD', 'GENETICS_YASAEI', 'GENETICS_OMRANI', 'GENETICS_GHADERIAN'])
def back_to_genetics_menu(message):
    show_genetics_menu(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD_SESSIONS')
def back_to_sayyad_menu(message):
    show_sayyad_menu(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def back_to_yasaei_menu(message):
    show_yasaei_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN_RESOURCES')
def back_to_ghaderian_menu(message):
    show_ghaderian_menu(message)

# بازگشت‌های فیزیک پزشکی
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی فیزیک پزشکی" and user_states.get(msg.from_user.id) == 'PHYSICS_RESOURCES')
def back_to_physics_menu(message):
    show_physics_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منابع فیزیک پزشکی" and user_states.get(msg.from_user.id) == 'PHYSICS_SESSIONS')
def back_to_physics_resources(message):
    show_physics_resources_menu(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'PHYSICS_COMPREHENSIVE')
def back_to_physics_resources_from_comprehensive(message):
    show_physics_resources_menu(message)

# بازگشت‌های فیزیولوژی
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی فیزیولوژی" and user_states.get(msg.from_user.id) in ['PHYSIOLOGY_CELL', 'PHYSIOLOGY_HEART', 'PHYSIOLOGY_DIGESTION', 'PHYSIOLOGY_CIRCULATION'])
def back_to_physiology_menu(message):
    show_physiology_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی سلول" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CELL_RESOURCES')
def back_to_physiology_cell_menu(message):
    show_physiology_cell_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قلب" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART_RESOURCES')
def back_to_physiology_heart_menu(message):
    show_physiology_heart_menu(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART_SESSIONS')
def back_to_physiology_heart_resources(message):
    show_physiology_heart_resources(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def back_to_physiology_digestion_resources(message):
    show_physiology_digestion_resources(message)
    
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def back_to_physiology_circulation_resources(message):
    show_physiology_circulation_resources(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی گوارش" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_RESOURCES')
def back_to_physiology_digestion_menu(message):
    show_physiology_digestion_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی گردش خون" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_RESOURCES')
def back_to_physiology_circulation_menu(message):
    show_physiology_circulation_menu(message)

# بازگشت‌های اندیشه اسلامی
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی اندیشه" and user_states.get(msg.from_user.id) in ['ISLAMIC_THOUGHT_WOMEN', 'ISLAMIC_THOUGHT_MEN'])
def back_to_islamic_thought_menu(message):
    show_islamic_thought_menu(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی قبلی" and user_states.get(msg.from_user.id) == 'ISLAMIC_THOUGHT_WOMEN_SESSIONS')
def back_to_islamic_thought_women_menu(message):
    show_islamic_thought_women_menu(message)

# --- هندلر عمومی برای پیام‌های نامعتبر ---
@bot.message_handler(content_types=['text'])
def handle_unknown_text(message):
    bot.send_message(message.chat.id, "⚠️ دستور نامعتبر! لطفاً از دکمه‌های منو استفاده کنید. بازگشت به منوی اصلی...")
    send_welcome(message)

# ===============================================================
# بخش ۵: اجرای نهایی ربات 🚀
# ===============================================================

if __name__ == "__main__":
    print(" Starting keep-alive server...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    bot.remove_webhook()
    print(" Bot server started. Running polling...")
    
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Error in polling: {e}")
            if ADMIN_CHAT_ID:
                try:
                    bot.send_message(ADMIN_CHAT_ID, f"⚠️ خطا در اجرای ربات: {e}")
                except Exception as e_send:
                    print(f"Could not send error message to admin: {e_send}")
            time.sleep(15)