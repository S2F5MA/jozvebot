import telebot
from telebot import types
import os
import threading
from flask import Flask
import time
import json
import re
import atexit
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

# ===============================================================
# بخش ۲: مدیریت حالت کاربران به صورت پایدار 🧠
# ===============================================================

STATE_FILE = "user_states.json"

# بارگذاری حالت‌ها از فایل (اگر وجود داشته باشد)
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, 'r') as f:
        user_states = json.load(f)
else:
    user_states = {}

# تابع ذخیره‌سازی در فایل


def save_user_states():
    with open(STATE_FILE, 'w') as f:
        json.dump(user_states, f)


# ذخیره هنگام خروج از برنامه
atexit.register(save_user_states)

# ذخیره دوره‌ای هر 30 ثانیه


def auto_save_loop():
    while True:
        time.sleep(30)
        save_user_states()


threading.Thread(target=auto_save_loop, daemon=True).start()

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
    bot.send_message(
        chat_id, f"یک گروه مدیا با {len(messages_to_process)} فایل دریافت شد. در حال پردازش...")

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
# بخش 4 : مدیریت فایل آیدی ها
# ===============================================================


# دیکشنری برای نگهداری فایل‌ها
user_files = {}


@bot.message_handler(commands=['get_ids'])
def handle_single_file(message):
    chat_id = message.chat.id
    user_files[chat_id] = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ پایان دریافت فایل‌ها")
    bot.send_message(
        chat_id, "📥 حالا فایل‌هاتو بفرست. وقتی تموم شد روی «پایان دریافت فایل‌ها» بزن.", reply_markup=markup)


@bot.message_handler(content_types=['document', 'video', 'audio', 'voice', 'photo'])
def save_file_id(message):
    chat_id = message.chat.id
    if chat_id not in user_files:
        return  # اگر هنوز دستور get_ids نداده بودن، هیچی ذخیره نکن

    file_id = None

    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.voice:
        file_id = message.voice.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id

    if file_id:
        user_files[chat_id].append(file_id)


@bot.message_handler(func=lambda m: m.text == "✅ پایان دریافت فایل‌ها")
def send_file_ids(message):
    chat_id = message.chat.id
    files = user_files.get(chat_id, [])

    if files:
        formatted = ",\n".join(f'"{fid}"' for fid in files)
        bot.send_message(chat_id, f"📎 فایل آیدی‌ها (برای کد):\n\n{formatted}")
    else:
        bot.send_message(chat_id, "⚠️ هیچ فایلی دریافت نشد.")

    user_files[chat_id] = []
    bot.send_message(chat_id, "✅ عملیات تمام شد.",
                     reply_markup=types.ReplyKeyboardRemove())


# ===============================================================
# بخش 5 : تنظیمات منوها
# ===============================================================

@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_states[message.from_user.id] = 'HOME'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 ترم 1"),
               types.KeyboardButton("📗 ترم 2"))
    bot.send_message(message.chat.id, """سلام 👋
قبل اینکه شروع کنی، اینو بگم: برای هر درس، ما دو نوع فایل داریم: "جزوه اصلی" و "فایل ضمیمه". فایل ضمیمه شامل نکات و مطالبی است که در طول کلاس مطرح شده‌اند و در جزوه اصلی موجود نیستند.
حالا لطفاً ترم مورد نظرت رو انتخاب کن:""", reply_markup=markup)


# ---------------------------------------------------------------
# ===============================================================
# TERM 1
# ===============================================================
# ---------------------------------------------------------------

@bot.message_handler(func=lambda msg: msg.text == "📘 ترم 1")
def show_term1_subjects(message):
    user_states[message.from_user.id] = 'TERM_1'
    bot.send_message(
        message.chat.id, "⚠️ منابع ترم ۱ هنوز آماده نشده‌اند. لطفاً بعداً بررسی کنید.")
    send_welcome(message)


# ---------------------------------------------------------------
# ===============================================================
# TERM 2
# ===============================================================
# ---------------------------------------------------------------


@bot.message_handler(func=lambda msg: msg.text == "📗 ترم 2")
def show_term2_subjects(message):
    user_states[message.from_user.id] = 'TERM_2'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["🦷 سلامت دهان و جامعه", "⚛️ فیزیک پزشکی", "💀 علوم تشریح 2", "🧬 ژنتیک", "⚗️ بیوشیمی",
               "📜 فرهنگ و تمدن اسلام", "💓 فیزیولوژی 1", "🕌 اندیشه اسلامی 1", "🔙 بازگشت به خانه"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم درس؟ 🤔", reply_markup=markup)


# ---- سلامت دهان و جامعه ----
@bot.message_handler(func=lambda msg: msg.text == "🦷 سلامت دهان و جامعه" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_oral_health_professor_menu(message):
    user_states[message.from_user.id] = 'ORAL_HEALTH_PROFESSOR'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👩‍🏫 استاد بخشنده"),
               types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم استاد؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "👩‍🏫 استاد بخشنده" and user_states.get(msg.from_user.id) == 'ORAL_HEALTH_PROFESSOR')
def show_professor_files_menu(message):
    user_states[message.from_user.id] = 'ORAL_HEALTH_FILES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton(
        "📊 پاور"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'ORAL_HEALTH_FILES')
def handle_reference(message):
    bot.send_document(
        message.chat.id, "BQACAgQAAxkBAAIC6WhywHEWz-jjoycdtxUJd1lkWImtAAJqKgAC5xNAUuqduCpdbgpDNgQ")
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
    markup.add(types.KeyboardButton("🧠 نظری"), types.KeyboardButton(
        "🦴 عملی"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم بخش؟ 🤔", reply_markup=markup)

# --- زیرمنوهای بخش نظری ---


@bot.message_handler(func=lambda msg: msg.text == "🧠 نظری" and user_states.get(msg.from_user.id) == 'ANATOMY')
def show_anatomy_theory_section(message):
    user_states[message.from_user.id] = 'ANATOMY_THEORY'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🦴 آناتومی (استاد نوروزیان)"), types.KeyboardButton("🔬 بافت‌شناسی (استاد منصوری)"),
               types.KeyboardButton("👶 جنین‌شناسی (استاد کرمیان)"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم مبحث؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🦴 آناتومی (استاد نوروزیان )" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY')
def show_anatomy_section_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_SECTION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton(
        "🎬 ویدیو"), types.KeyboardButton("📊 پاور"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'ANATOMY_SECTION')
def handle_anatomy_power_files(message):
    power_file_ids = [
        # 🟡 جایگزین کن با File ID واقعی
        "BQACAgQAAxkBAAIEimhzMn7yhRe17WG_DRFaZ9zvNv7-AALdFwACdnxIUVLTgFGvhsdANgQ",
        # 🟡 جایگزین کن با File ID واقعی
        "BQACAgQAAxkBAAIEi2hzMn5vehOykLH42mBh11kUDus6AALeFwACdnxIURAcXc1UpRxsNgQ",
        # 🟡 جایگزین کن با File ID واقعی
        "BQACAgQAAxkBAAIEjGhzMn7NDA7cR9e1F6Qqp_e2_C7hAALfFwACdnxIUU-lApLdrHeoNgQ",
        "BQACAgQAAxkBAAIEjWhzMn7eL37pm491MQaAjFJATNM5AALgFwACdnxIUev4Oj7xThKRNgQ",
        "BQACAgQAAxkBAAIEjmhzMn6ViJPVNmK5VVHzW4q0ozAgAALhFwACdnxIUUwaySeazzu0NgQ",
        "BQACAgQAAxkBAAIEkGhzMn4hFaQfGlK8RqU8KHyIuXnDAALjFwACdnxIUS_og3F9oC7nNgQ",
        "BQACAgQAAxkBAAIEj2hzMn6zhMEMxWvG2mQEldt58pDqAALiFwACdnxIUdeFx6hW-UDgNgQ",
        "BQACAgQAAxkBAAIEkWhzMn6GvS3A3mczTZBukyYGoDIYAALkFwACdnxIUU9kZVwKf5V-NgQ",
        "BQACAgQAAxkBAAIEkmhzMn71hR1JT-p9aN8S4vDIVrlUAALlFwACdnxIUUaDl2JAHTwcNgQ",
        "BQACAgQAAxkBAAIEk2hzMn5S3n78-yy1Y1yELsKIxnVhAALmFwACdnxIUUEaBkDu-POUNgQ",
        "BQACAgQAAxkBAAIElGhzMn5_wFBmDKNb_u5jBArVB62cAALnFwACdnxIUV4Sw3JkBCPSNgQ",
        "BQACAgQAAxkBAAIElWhzMn4VJiXs1qzuw3TezV2rrEcqAALoFwACdnxIUVP-NUakaOZnNgQ",
        "BQACAgQAAxkBAAIElmhzMn50KjxGWaT4fOGsH8rpb_pUAALpFwACdnxIUceSFOH5AkoONgQ",
        "BQACAgQAAxkBAAIEl2hzMn6k7gJ3chet3ZMnqH2BfKrcAALrFwACdnxIUWc-TgSjd1ZGNgQ",
        "BQACAgQAAxkBAAIEmGhzMn7v6b70ZGhgCDgooNG5whbVAALsFwACdnxIUVcmgrQ0o55nNgQ",
        "BQACAgQAAxkBAAIEmWhzMn7gxf4WPri2exlStbsRqk4hAALtFwACdnxIUdFdIzSpMlAKNgQ",
        "BQACAgQAAxkBAAIEmmhzMn6K3JKfR39R5vihYoN1_IeSAALuFwACdnxIUVD-kNOvn7DhNgQ",
        "BQACAgQAAxkBAAIEm2hzMn5uqktrdVWfxg4M9w6YpqCWAALvFwACdnxIUbWVxdR4AAF6VTYE",
        "BQACAgQAAxkBAAIEnGhzMn4tg9ehSAspLXYoNDERCx4yAALwFwACdnxIUd-WGnGFpvzgNgQ",
        "BQACAgQAAxkBAAIEnWhzMn5rphhHtyQYsWnvUMVAsxvlAALxFwACdnxIUfhIobuvWYvRNgQ",
        "BQACAgQAAxkBAAIEnmhzMn6TNQ7l1uF6MLLnC_v0yixdAALyFwACdnxIUSedIIV-nKMSNgQ",
        "BQACAgQAAxkBAAIEn2hzMn4Ha_thudOf9WKiblOZR6akAALzFwACdnxIUfy2VPOnMEKQNgQ",
        "BQACAgQAAxkBAAIEoGhzMn78NiHbq_LFePj2-xwk7WOcAAL0FwACdnxIUa68Epbj6NC8NgQ",
        "BQACAgQAAxkBAAIEoWhzMn5cbXopi5-0cEDxNJiNgGmiAAL1FwACdnxIUUx1aWoKRQbNNgQ",
        "BQACAgQAAxkBAAIEomhzMn4IbCuKeY0QI1CqhzI4mAruAAL2FwACdnxIUZBGv-BFt15tNgQ",
        "BQACAgQAAxkBAAIEo2hzMn5J9nvfmb1YojJoc-S5pNijAAL3FwACdnxIUcgJDWVsCP-UNgQ",
        "BQACAgQAAxkBAAIEpGhzMn50antMnT9ozQvQv6ZtHpG6AAL4FwACdnxIUYwwmefKSqgBNgQ",
        "BQACAgQAAxkBAAIEpWhzMn6VNuj-m9vEuJuT7jtO3vcsAAL5FwACdnxIUbzzZrOH0AazNgQ",
        "BQACAgQAAxkBAAIEpWhzMn6VNuj-m9vEuJuT7jtO3vcsAAL5FwACdnxIUbzzZrOH0AazNgQ",
        "BQACAgQAAxkBAAIEpmhzMn57zLV2_HrqL3fyFYApS6RDAAL6FwACdnxIUf14L6nh3_ObNgQ",
        "BQACAgQAAxkBAAIEp2hzMn7uC87Q1GjMXAyMo2kGnBYqAAL7FwACdnxIUVw9dWQCyY_PNgQ",
        "BQACAgQAAxkBAAIEqGhzMn7EGOP3CrO96gTWM8-J3EaiAAL8FwACdnxIUb9SFyShWAWANgQ",
        "BQACAgQAAxkBAAIEqWhzMn5TbbE2kv3RME3jLVZboeS6AAL9FwACdnxIUY3rHczTPH8lNgQ",
        "BQACAgQAAxkBAAIEqmhzMn7YszpTNTPY8l_D7BDWQMYfAAL_FwACdnxIUV0T4cPuCPj_NgQ",
    ]

    bot.send_message(
        message.chat.id, "📊 اینم پاورهای مربوط به استاد نوروزیان:")

    for file_id in power_file_ids:
        try:
            bot.send_document(message.chat.id, file_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❗ خطا در ارسال فایل: {e}")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'ANATOMY_SECTION')
def show_anatomy_resources_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton("📄 جزوات جامع"), types.KeyboardButton(
        "📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'ANATOMY_RESOURCES')
def send_anatomy_reference(message):
    reference_file_ids = [
        # 🟡 جایگزین کن با File ID واقعی
        "BQACAgQAAxkBAAIEzGhzNSPPXJq3N3oVOe1V3dvLs_YsAAJFAAMukklRv5SF32MikPk2BA",
        # 🟡 جایگزین کن با File ID واقعی
        "BQACAgUAAxkBAAIEzWhzNSMObxLiliPrlhZkyciKM2_LAALKAANEzChWqkwpykgsRaQ2BA",
        "BQACAgQAAxkBAAIEzmhzNSMxQziQgzMjftrU2hURdIciAAJPBgACeHEhUwrOIM7sq_88NgQ"
    ]

    bot.send_message(
        message.chat.id, "📘 اینم رفرنس‌های آناتومی استاد نوروزیان:")

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
        # 🟡 جایگزین کن با فایل آیدی واقعی
        "BQACAgQAAxkBAAIE0mhzNYIrIBYM8984rJa9jSNwiQABBwACnxgAAhyNOVJeV2ukNpkzxDYE",
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
        # 🟡 جایگزین کن با فایل آیدی واقعی
        "BQACAgQAAxkBAAIE1GhzNaFUY22WPQuoNX1Lm6Z6MZBqAAIxGQACfVY4Uq11bteFeECYNgQ",
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
        # 🟡 جایگزین کن با فایل آیدی واقعی
        "BQACAgQAAxkBAAIE1mhzNcOEiSgLcHUozRhq_GJqjSdmAAIzEAACRW85UC2ZZQABXzvKoDYE",
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
def session1(message): send_anatomy_session_file(message, "اول", [
    "BQACAgQAAxkBAAIE2GhzNrhA9AKdPJWZ8XJEuJSC4JB_AAJ9GAACHI05Uuqx1bZc4DnFNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session2(message): send_anatomy_session_file(message, "دوم", [
    "BQACAgQAAxkBAAIE2mhzNts2mIvlkvGOar-PJr_ipo-fAAKbGAACHI05UjnRxl1QfnatNgQ", "BQACAgQAAxkBAAIE22hzNtvQ_rmTxzpVC6aYNpalfI2bAAKcGAACHI05UmNYAzrRVQ1uNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session3(message): send_anatomy_session_file(message, "سوم", [
    "BQACAgQAAxkBAAIE3WhzNwl67_dkBEUX1EUHaE8jlYN9AAJ_GAACHI05Uiti1UwHx0Z2NgQ"])


@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session4(message): send_anatomy_session_file(message, "چهارم", [
    "BQACAgQAAxkBAAIE32hzNxyi31zQV-F0Tb_SaTwHmBe8AAKAGAACHI05UmuQxnA4ZXUGNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "5️⃣ جلسه پنجم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session5(message): send_anatomy_session_file(message, "پنجم", [
    "BQACAgQAAxkBAAIE4WhzNzb7eWvkByYsjDy1nIb1mUh_AAKBGAACHI05UkoGyPWXj0OaNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "6️⃣ جلسه ششم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session6(message): send_anatomy_session_file(message, "ششم", [
    "BQACAgQAAxkBAAIE42hzNz9pqvgeEUeVCj9i9cM6GCd_AAKCGAACHI05UgHKpz6ITYV2NgQ"])


@bot.message_handler(func=lambda msg: msg.text == "7️⃣ جلسه هفتم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session7(message): send_anatomy_session_file(message, "هفتم", [
    "BQACAgQAAxkBAAIE5WhzN0df6A1-q0-z5AvApiAMNzhcAAKDGAACHI05UmtWoiRm5VZGNgQ", "BQACAgQAAxkBAAIE5mhzN0dyGufHtyLhnsu_hxdXkGkkAAKEGAACHI05UsHwcJvEQQ0aNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "8️⃣ جلسه هشتم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session8(message): send_anatomy_session_file(message, "هشتم", [
    "BQACAgQAAxkBAAIE6WhzN1EkdiIu4qkTMScI-13S7YCDAAKFGAACHI05UuFEvk0YZayqNgQ", "BQACAgQAAxkBAAIE6mhzN1Gz-2O1_KPGq1GEOJ6R3j4SAAKGGAACHI05Ug6OKXVCbQXlNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "9️⃣ جلسه نهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session9(message): send_anatomy_session_file(message, "نهم", [
    "BQACAgQAAxkBAAIE7mhzN1qrs-u1hUypaexE-DnrECOSAAKIGAACHI05Uorp3k7vdyuUNgQ", "BQACAgQAAxkBAAIE7WhzN1piQKtGl-QbFowQBjxaE3pZAAKHGAACHI05UgoQzf9oFxq3NgQ"])


@bot.message_handler(func=lambda msg: msg.text == "🔟 جلسه دهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session10(message): send_anatomy_session_file(message, "دهم", [
    "BQACAgQAAxkBAAIE8mhzN2Iu-WBG1ovzEN9QwehXshLJAAKKGAACHI05Uj5YXBFUuOk5NgQ", "BQACAgQAAxkBAAIE8WhzN2JOPYC-XT_3unvMDp6q0wP0AAKJGAACHI05UhRimec8ShvLNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "1️⃣1️⃣ جلسه یازدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session11(message): send_anatomy_session_file(message, "یازدهم", [
    "BQACAgQAAxkBAAIE9WhzN2o-WatGYF1WVPdEeuGFzOhyAAKLGAACHI05UsAFbOYlq0HjNgQ", "BQACAgQAAxkBAAIE9mhzN2pZUGtvUuknrcEWSd7nkG1_AAKMGAACHI05Ur8dNu-o-uFiNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "1️⃣2️⃣ جلسه دوازدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session12(message): send_anatomy_session_file(message, "دوازدهم", [
    "BQACAgQAAxkBAAIE-WhzN8Y_YtdKYzC_3qhQIBG2BVx6AAKOGAACHI05Ui4zTZ4zFHV6NgQ"])


@bot.message_handler(func=lambda msg: msg.text == "1️⃣3️⃣ جلسه سیزدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session13(message): send_anatomy_session_file(message, "سیزدهم", [
    "BQACAgQAAxkBAAIE_GhzN85wDBZjjp91lK0AAZFs6cxoMgACkBgAAhyNOVLSwlck7xyXfzYE", "BQACAgQAAxkBAAIE-2hzN86TOUg7ipEOqKmmzrlPyQdXAAKPGAACHI05UjrqWaEXEl1zNgQ"])


@bot.message_handler(func=lambda msg: msg.text == "1️⃣4️⃣ جلسه چهاردهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session14(message): send_anatomy_session_file(message, "چهاردهم", [
    "BQACAgQAAxkBAAIE_2hzOFu6HlbViUy1OXunBNcom8AQAAKRGAACHI05Uj1IzE8UnEveNgQ", "BQACAgQAAxkBAAIFAAFoczhbleKEFw68aKn0YsgxUf441QACkhgAAhyNOVIVyxwoUDbF6jYE"])


@bot.message_handler(func=lambda msg: msg.text == "1️⃣5️⃣ جلسه پانزدهم" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY_SESSIONS')
def session15(message): send_anatomy_session_file(message, "پانزدهم", [
    "BQACAgQAAxkBAAIFBGhzOGNmoXnksq_kqqTXbKX0bCpyAAKUGAACHI05UlfZOqOB4z7BNgQ", "BQACAgQAAxkBAAIFA2hzOGMDWgNuMOeGRpbAyrxLbMVpAAKTGAACHI05UpgU1TVIMfF_NgQ"])


@bot.message_handler(func=lambda msg: msg.text == "🔬 بافت‌شناسی (استاد منصوری )" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY')
def show_histology_section_menu(message):
    user_states[message.from_user.id] = 'HISTOLOGY_SECTION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📊 پاور"), types.KeyboardButton(
        "📚 منابع مطالعاتی"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'HISTOLOGY_SECTION')
def send_histology_powerpoints(message):
    # فایل آیدی‌های پاورپوینت‌ها
    power_file_ids = [
        "BQACAgQAAxkBAAIFC2hzOdM2VJlSqZW1Yf5ju_V7pZYBAAI5GwACGo5wUdy7En6ZCGPqNgQ",
        "BQACAgQAAxkBAAIFDGhzOdMfaCT7qS5O__4JxpwMSeOrAAI9GwACGo5wUdNWZN35rr2ANgQ",
        "BQACAgQAAxkBAAIFDWhzOdPfjwunkQK6PtlyZUJud0VUAAI7GwACGo5wUdl-oc-P0xrJNgQ",
        "BQACAgQAAxkBAAIFDmhzOdN042TLZKOfPMDTVY5i7anxAAI8GwACGo5wUctorZo0EkEgNgQ",
        "BQACAgQAAxkBAAIFD2hzOdNCSvwSnOTgOR4eF8bQccyIAAI6GwACGo5wUSbVJQbWP3NJNgQ"
        # ... در صورت نیاز فایل‌های بیشتر اضافه کن
    ]
    bot.send_message(message.chat.id, "📊 پاورپوینت‌های استاد منصوری:")

    for file_id in power_file_ids:
        bot.send_document(message.chat.id, file_id)


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'HISTOLOGY_SECTION')
def show_histology_resources_menu(message):
    user_states[message.from_user.id] = 'HISTOLOGY_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton(
        "📑 خلاصه فصول تدریس شده"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'HISTOLOGY_RESOURCES')
def send_histology_references(message):
    reference_file_ids = [
        "BQACAgQAAxkBAAIFHmhzOkYicm23fNbEQULYNshrAYehAAJRBgACFrMxU04aoXutPgN_NgQ",
        "BQACAgQAAxkBAAIFHWhzOkZhl-wjDeCS7oBhkpnprquLAAJhCgACBK_xUE5ZFdjuLrSCNgQ",
        # فایل‌های بیشتر در صورت نیاز
    ]
    bot.send_message(message.chat.id, "📘 رفرنس‌های بافت‌شناسی:")

    for file_id in reference_file_ids:
        bot.send_document(message.chat.id, file_id)


@bot.message_handler(func=lambda msg: msg.text == "📑 خلاصه فصول تدریس شده" and user_states.get(msg.from_user.id) == 'HISTOLOGY_RESOURCES')
def send_histology_chapter_summaries(message):
    summary_file_ids = [
        "BQACAgQAAxkBAAIFIWhzOqEeheroKLEIEu9o-4QDejkZAAJqGAACrD-YU-AzYyPz9f4gNgQ",
        # ادامه بده اگر بیشتر داری
    ]
    bot.send_message(message.chat.id, "📑 خلاصه فصول تدریس‌شده استاد منصوری:")

    for file_id in summary_file_ids:
        bot.send_document(message.chat.id, file_id)


@bot.message_handler(func=lambda msg: msg.text == "👶 جنین‌شناسی (استاد کرمیان)" and user_states.get(msg.from_user.id) == 'ANATOMY_THEORY')
def show_embryology_section_menu(message):
    user_states[message.from_user.id] = 'EMBRYOLOGY_SECTION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📄 جزوه استاد"), types.KeyboardButton(
        "📘 رفرنس"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه استاد" and user_states.get(msg.from_user.id) == 'EMBRYOLOGY_SECTION')
def send_embryology_prof_notes(message):
    prof_notes_file_ids = [
        "BQACAgQAAxkBAAIFI2hzOtHKwh34RtPPNRu0hoOwR7AqAAKnGAACHI05UjHRkh7eAX8pNgQ",
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
    markup.add(types.KeyboardButton("🦴 آناتومی ( استاد سلطانی )"), types.KeyboardButton(
        "🔬 بافت‌شناسی (استاد  )"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم مبحث؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🦴 آناتومی (استاد سلطانی)" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL')
def show_anatomy_practical_subsection(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_SUB'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton(
        "🎬 ویدیو"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🎬 ویدیو" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_SUB')
def show_anatomy_practical_video_sessions(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_VIDEO_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم",
               "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text in [
    "1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم",
    "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم",
    "1️⃣1️⃣ جلسه یازدهم"])
def send_anatomy_practical_video(message):
    video_file_ids = {
        "1️⃣ جلسه اول": ["BAACAgQAAxkBAAIFsWhzPROXvZz9AfSFphIrqwRidoG9AAJcGgACLwmwUT5LN7n4H4liNgQ"],
        "2️⃣ جلسه دوم": ["BAACAgQAAxkBAAIFt2hzPlxUGtq6z46bDMvQv7dwOc6CAAJpGQAClh7QUfwggS9WV34cNgQ", "BAACAgQAAxkBAAIFuGhzPlykmwN35zthFIrq-ALmK74xAAJqGQAClh7QUaK6a1JBuHk8NgQ",
                         "BAACAgQAAxkBAAIFuWhzPlxkKKRBb8jPZ4YadT2cqN_qAAJrGQAClh7QUXkfkCQi5kkINgQ",
                         "BAACAgQAAxkBAAIFumhzPlzhia98QDqYZJXL4Bq-ip0jAAJtGQAClh7QUYsuwGiQgixGNgQ",
                         "BAACAgQAAxkBAAIFu2hzPlz6N8xmlG5J-XUZOjVe9iLeAAJuGQAClh7QUUisMknR_NgnNgQ",
                         "BAACAgQAAxkBAAIFvGhzPlzwrnxDCzTix_SVOnWVyC9cAAJvGQAClh7QURInqx6ZmuQlNgQ",
                         "BAACAgQAAxkBAAIFvWhzPlzJX_Jt61-UqOHxJqA2N9oRAAJwGQAClh7QUSvVVN8B8uTVNgQ",
                         "BAACAgQAAxkBAAIFvmhzPlwCq0SSFNj0EVv357SCqO6fAAJxGQAClh7QUXPGVn5G3dFsNgQ",
                         "BAACAgQAAxkBAAIFv2hzPlwlrbf2MgsiKJ5E8A5Vgw28AAJyGQAClh7QUalS6r0kswABETYE",
                         "BAACAgQAAxkBAAIFwGhzPlzoKW7kNR22717DecvyNy5MAAJzGQAClh7QUfiPmcXzvkZWNgQ",
                         "BAACAgQAAxkBAAIFwWhzPlwNJd578-L_QGd46TCNMfFiAAJ0GQAClh7QUZZD2u_WtBYXNgQ",
                         "BAACAgQAAxkBAAIFwmhzPlx_LlPDEB396fRLY0_earinAAJ1GQAClh7QUd6VCWRCbUpqNgQ",
                         "BAACAgQAAxkBAAIFw2hzPlyxgX_EYYReUL_m54vyvw0PAAJ2GQAClh7QURySwwZMLtvoNgQ",
                         "BAACAgQAAxkBAAIFxGhzPlx_fk4pPDyyA36-bClfLILtAAJ3GQAClh7QUVrBcSCVtnnGNgQ",
                         "BAACAgQAAxkBAAIFxWhzPly0tkieboYC2O74YH8LzTinAAJ4GQAClh7QUYaWbu2ng0FgNgQ",
                         "BAACAgQAAxkBAAIFxmhzPlzlR5n7BxdGwQJ9h4OQatx2AAJ5GQAClh7QUaizlWciKgFvNgQ",
                         ],
        "3️⃣ جلسه سوم": ["BAACAgQAAxkBAAIF2GhzP5qC8ZBU6whTDkVzGRwDuuXwAAKBFQACWBs5UpeXuY2QP_dWNgQ", "BAACAgQAAxkBAAIF12hzP5om1s66PASxMDNRPJHO8oc-AAKAFQACWBs5UsuV0jXyfS21NgQ",
                         "BAACAgQAAxkBAAIF2WhzP5qUFliMCeGOLn_IIQKhIMdYAAKDFQACWBs5UpawamcUL33XNgQ",
                         "BAACAgQAAxkBAAIF2mhzP5p9Ls6BOc2_l6eE2MRw5UQ1AAKFFQACWBs5UkJHwSUVV7G2NgQ",
                         "BAACAgQAAxkBAAIF22hzP5qYB9TmcQZ6R4JQJ3gNjiPNAAKJFQACWBs5UmPzEzjRNFw2NgQ",
                         "BAACAgQAAxkBAAIF3GhzP5qzoWyV3sblEWuBhTu5OqzCAAKLFQACWBs5Ug5H1eL9tW0hNgQ",
                         "BAACAgQAAxkBAAIF3WhzP5o1SFlaXtzBsM06PqRpFvYLAAKMFQACWBs5UkhSP33K8ySmNgQ",
                         "BAACAgQAAxkBAAIF3mhzP5rh50pUsz3hII79_ijeq5KUAALSHQACMtNAUuXUFshPrrmfNgQ",
                         "BAACAgQAAxkBAAIF32hzP5pj2-j-OtJkr63a9cmJE7x3AALVHQACMtNAUrmGHFVj1pj3NgQ",
                         "BAACAgQAAxkBAAIF4GhzP5rleQLs2DOZ66gqxykPQsN2AALWHQACMtNAUqq8Hr-HZI3TNgQ",
                         "BAACAgQAAxkBAAIF4WhzP5pM8xtE7yRj9z4l5a0lnt-kAAL7HQACMtNAUh5aV504ia8FNgQ", "BAACAgQAAxkBAAIF4mhzP5o0K3Epyg61HSO1E0Gpo8olAAL8HQACMtNAUrcJQHDCpVmRNgQ"],
        "4️⃣ جلسه چهارم": ["BAACAgQAAxkBAAIF8WhzQC-UBDx3-g64Xb3KHn9oS-hyAAK1FAACEKaAUlUdmO9yuap0NgQ", "BAACAgQAAxkBAAIF8mhzQC8bLSbudYopv2tS3rc9SqeLAAJgGQACIriBUqRv1AfVhWRVNgQ",
                           "BAACAgQAAxkBAAIF82hzQC8HwsPdbQ1TeR0WVkQ9W18tAAJ1GQACIriBUjnhmS1hGgRpNgQ",
                           "BAACAgQAAxkBAAIF9GhzQC8Ew_bWaF7a39Ir8rxZLl2AAAJ3GQACIriBUmSiZnG8WWSDNgQ",
                           "BAACAgQAAxkBAAIF9WhzQC_y5zQyvg3VCAgE9A74Q37-AAJ8GQACIriBUk7rOsxaWlR8NgQ"
                           ],
        "5️⃣ جلسه پنجم": ["BAACAgQAAxkBAAIF_GhzQMcNlolOTQGtEMMwhe_T66YoAAIsFgACjheQU31HCXT6N_0bNgQ",
                          "BAACAgQAAxkBAAIF-2hzQMeADjLNIOBDUJnEXp35S27aAAIvFgACjheQU7rGrJ9mfYIsNgQ",
                          "BAACAgQAAxkBAAIF_WhzQMfET59ABTnPVYyWKA_9wYnIAAIzFgACjheQUzPlyx5g81PiNgQ",
                          "BAACAgQAAxkBAAIF_mhzQMcrba_FwamIx0KXdX890NZPAAL3GQAC4-WQU5RGl-J00SxvNgQ"],
        "6️⃣ جلسه ششم": ["BAACAgQAAxkBAAIGBGhzQSZKtSwz9XcN70t-vtcH6KxoAALyGgAC27XwU5wU--OCsBoKNgQ",
                         "BAACAgQAAxkBAAIGA2hzQSamrMEk6rmv4ofiJ-CuZL3QAALuGgAC27XwU5866GlXcD-VNgQ",
                         "BAACAgQAAxkBAAIGBWhzQSa4CO2CpTkum4gZEac1WYaTAAL0GgAC27XwU_Z3acXGwIIeNgQ",
                         "BAACAgQAAxkBAAIGBmhzQSY2_ugjOZb6s9l2GjXZusYKAAL3GgAC27XwUzuAh_tp93JGNgQ"],
        "7️⃣ جلسه هفتم": ["BAACAgQAAxkBAAIGC2hzQX40K56KitSYJLp-Cm1YHa8FAAKxHQACnvlAUONoBXA6N5hDNgQ",
                          "BAACAgQAAxkBAAIGDGhzQX54Sbk2DloOCsT4xa8E-7fpAAK2HQACnvlAUFNMvZDcY0tQNgQ",
                          "BAACAgQAAxkBAAIGDWhzQX6DerE8_26PaF8Zbpp2dbycAAK7HQACnvlAUHBqoAdvI36SNgQ",
                          "BAACAgQAAxkBAAIGDmhzQX7fD5if9I1wssbLm4s6lX2nAALBHQACnvlAUDliw7hXTZ_pNgQ",
                          ],
        "8️⃣ جلسه هشتم": ["BAACAgQAAxkBAAIGE2hzQeiqcYp0h1SvlW-F_DSLullFAAIRFgACVHuIUBxmIJ_YHncHNgQ",
                          "BAACAgQAAxkBAAIGFGhzQeiGdlAdAWQjcbnQE7YpbM0JAAIUFgACVHuIUBMh2tH70b1yNgQ",
                          "BAACAgQAAxkBAAIGFWhzQehoiFAoz_hX9gzRUenfXxcPAAIiFgACVHuIUN6ceH4hMt5yNgQ",
                          "BAACAgQAAxkBAAIGFmhzQegmuxJqTq1asNBNF8n8xi-nAAIsFgACVHuIUDE0GCJmqMXgNgQ",
                          "BAACAgQAAxkBAAIGF2hzQegkfqlq5VJEekOdbZ5PXCZFAAI1FgACVHuIUKgf1rBD5FCWNgQ"],
        "9️⃣ جلسه نهم": ["BAACAgQAAxkBAAIGHWhzQjM2ppwr-dZGW-BIq3VrkMoJAALkGAACRY_RUJqhCtZBbIhNNgQ",
                         "BAACAgQAAxkBAAIGHmhzQjPs1gIbvBCIQeC9FffBMEjYAALqGAACRY_RUPWda7PKtZZtNgQ",
                         "BAACAgQAAxkBAAIGH2hzQjMZnL7lVKxXJ4q77om2hCBwAALsGAACRY_RUCZFqiNT9OrsNgQ",
                         "BAACAgQAAxkBAAIGIGhzQjOtZge20qfDL0g0SfB-m9rtAALtGAACRY_RUEcRVSqfnQszNgQ"],
        "🔟 جلسه دهم": ["BAACAgQAAxkBAAIGJWhzQnHfDJJdcdRvtJYJuQOEFZonAAL2FQACoiMYUcNYokZLKlGuNgQ",
                       "BAACAgQAAxkBAAIGJmhzQnF_0plsL0qZiHF4n6yFJTpdAAIBFgACoiMYUaZZ_A86sLlZNgQ",
                       "BAACAgQAAxkBAAIGJ2hzQnEsjOB6EGQ2RkoUBlr7Af73AAIDFgACoiMYUYoE30sT0YzWNgQ"],
        "1️⃣1️⃣ جلسه یازدهم": ["BAACAgQAAxkBAAIGK2hzQqcg9hMNe0eKcr2INEnamKT3AAJRHAACHx6oUYMrCY-y8l6-NgQ",
                               "BAACAgQAAxkBAAIGLGhzQqcXYYZJfr_AHUMbt1xcWraNAAJSHAACHx6oUQNnUxiM2MSdNgQ",
                               "BAACAgQAAxkBAAIGLWhzQqcJyftcTUTxWF1-oGmL5SW5AAJTHAACHx6oUVvv_FU5XbUJNgQ"],
    }
    selected = message.text
    file_id = video_file_ids.get(selected)
    if file_id:
       print("🔍 file_id is:", file_id)
       bot.send_video(message.chat.id, file_id)
    else:
        bot.send_message(
            message.chat.id, "❗ فایل ویدیویی این جلسه موجود نیست.")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_SUB')
def show_anatomy_practical_resources_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 جزوات جامع"), types.KeyboardButton(
        "📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📚 جزوات جامع" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_RESOURCES')
def show_anatomy_practical_comprehensive_menu(message):
    user_states[message.from_user.id] = 'ANATOMY_PRACTICAL_COMPREHENSIVE'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🎓 جزوه 401"), types.KeyboardButton(
        "🎓 جزوه 403"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم جزوه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text in ["🎓 جزوه 401", "🎓 جزوه 403"] and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL_COMPREHENSIVE')
def send_anatomy_practical_comprehensive_file(message):
    file_ids = {
        "🎓 جزوه 401": "BQACAgQAAxkBAAIGMWhzQxcgrM1w7Qgu7EAePXF_3QJ7AALBFwACaDQZUsDIDLK84BO0NgQ",
        "🎓 جزوه 403": "BQACAgQAAxkBAAIGM2hzQzj-f3dbIUFJQNE1JRBxLMPUAAKtFgAC0xwgUvhgX6PSmT4jNgQ"
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
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم",
               "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "🔙 بازگشت به منوی قبلی"]
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
        "1️⃣ جلسه اول": "BQACAgQAAxkBAAIGNmhzQ5HmavGiDt4AAenVb3YBGdD-ewACnxYAAtMcIFIKflw81sUKYzYE",
        "2️⃣ جلسه دوم": "BQACAgQAAxkBAAIGNWhzQ5GWU1vAy3N29XFnB7O0GH0aAAKeFgAC0xwgUvKuglwojPfRNgQ",
        "3️⃣ جلسه سوم": "BQACAgQAAxkBAAIGN2hzQ5GuPPhFx3xMLJGJ6Ti0fSpdAAKgFgAC0xwgUi7WuRnUx7NSNgQ",
        "4️⃣ جلسه چهارم": "BQACAgQAAxkBAAIGOGhzQ5HibhfzJzrx9ubuthDafp3IAAKhFgAC0xwgUkn0fG-memHONgQ",
        "5️⃣ جلسه پنجم": "BQACAgQAAxkBAAIGOWhzQ5H6YfxcAhzPtukJRK04WwfoAAKiFgAC0xwgUhEtbzokMznJNgQ",
        "6️⃣ جلسه ششم": "BQACAgQAAxkBAAIGOmhzQ5H7U72xUPc1PkTxBPyZrjNSAAKjFgAC0xwgUvefDPFaCxesNgQ",
        "7️⃣ جلسه هفتم": "BQACAgQAAxkBAAIGO2hzQ5GCh0Cod-GRRggCtrHlORTEAAKkFgAC0xwgUg5cRJ1t50XmNgQ",
        "8️⃣ جلسه هشتم": "BQACAgQAAxkBAAIGPGhzQ5FamC0gQvh7PQuuWLd9ilhGAAKlFgAC0xwgUmucZyHy2ydSNgQ",
        "9️⃣ جلسه نهم": "BQACAgQAAxkBAAIGPWhzQ5HWtUFYTUNfE1-UXDtE1O4qAAKmFgAC0xwgUsg7xaKPG8TBNgQ",
        "🔟 جلسه دهم": "BQACAgQAAxkBAAIGPmhzQ5EAAd8qeoaoXiAOpm9k8rRULAACpxYAAtMcIFJ2HT_O6qnjxjYE",
        "1️⃣1️⃣ جلسه یازدهم": "BQACAgQAAxkBAAIGP2hzQ5GcswTbVx5f1NHGMWwglwABygACrBYAAtMcIFKLStroo4-ZvDYE"
    }
    file_id = file_ids.get(message.text)
    if file_id:
        bot.send_document(message.chat.id, file_id)
    else:
        bot.send_message(
            message.chat.id, "❗ فایل این جلسه هنوز بارگذاری نشده.")


@bot.message_handler(func=lambda msg: msg.text == "🔬 بافت‌شناسی (استاد  )" and user_states.get(msg.from_user.id) == 'ANATOMY_PRACTICAL')
def show_histology_practical_subsection(message):
    user_states[message.from_user.id] = 'HISTOLOGY_PRACTICAL_SUB'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton(
        "🎬 ویدیو"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🎬 ویدیو" and user_states.get(msg.from_user.id) == 'HISTOLOGY_PRACTICAL_SUB')
def send_histology_practical_video(message):
    user_states[message.from_user.id] = 'HISTOLOGY_PRACTICAL_VIDEO'
    file_id = "<FILE_ID_Video_Histology_Practical>"  # ← اینجا آی‌دی ویدیو رو قرار بده
    bot.send_video(message.chat.id, file_id,
                   caption="🎥 ویدیوی بافت‌شناسی عملی (استاد)")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'HISTOLOGY_PRACTICAL_SUB')
def show_histology_practical_resources_menu(message):
    user_states[message.from_user.id] = 'HISTO_PRACTICAL_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("📄 جزوه کلی"), types.KeyboardButton(
        "📄 جزوه جلسه اول"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه کلی" and user_states.get(msg.from_user.id) == 'HISTO_PRACTICAL_RESOURCES')
def send_histology_practical_general_notes(message):
    # لیست چند فایل جزوه کلی
    file_ids = [
        # ← این‌ها رو با file_id واقعی جایگزین کن
        "BQACAgQAAxkBAAIGS2hzRDbxx5MU35sBG5wO0yjhBiRMAAKuFgAC0xwgUtooriJJ0mRLNgQ",
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📄 جزوه کلی بافت‌شناسی عملی")


@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه جلسه اول" and user_states.get(msg.from_user.id) == 'HISTO_PRACTICAL_RESOURCES')
def send_histology_practical_first_session_notes(message):
    # لیست چند فایل جزوه جلسه اول
    file_ids = [
        "BQACAgQAAxkBAAIGTWhzRGjVHdqFYAFQD2Lmodo_HZePAAKqFgAC0xwgUhryjl64_OGSNgQ",
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📄 جزوه جلسه اول بافت‌شناسی عملی")

# --- هندلرهای درس ژنتیک ---


@bot.message_handler(func=lambda msg: msg.text == "🧬 ژنتیک" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_genetics_menu(message):
    user_states[message.from_user.id] = 'GENETICS_MENU'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["👩‍🏫 استاد صیاد", "👨‍🏫 استاد یاسایی",
               "👨‍🏫 استاد عمرانی", "👨‍🏫 استاد قادریان", "🔙 بازگشت به دروس"]
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
        # ← این‌ها رو با file_idهای واقعی جایگزین کن
        "BQACAgQAAxkBAAIGs2hzTK23pPAj_0D1XiVcmv1o3E6gAAJ_HwAChL1gU2XrNIeNn7EtNgQ",
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📚 جزوه جامع استاد صیاد - ژنتیک")


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD')
def show_sayyad_sessions_menu(message):
    user_states[message.from_user.id] = 'GENETICS_SAYYAD_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم",
               "3️⃣ جلسه سوم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD_SESSIONS')
def send_sayyad_session1(message):
    # ← جایگزین با file_idهای واقعی
    file_ids = [
        "BQACAgQAAxkBAAIGv2hzTPpMlTaf_x6ZA9NFnn_jxZ9TAAIcHAACv1f5Uqy0I0Zm4ZktNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه اول - استاد صیاد")


@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD_SESSIONS')
def send_sayyad_session2(message):
    file_ids = [
        "BQACAgQAAxkBAAIGwmhzTQ9GxUiS4G0X9MY0SebOpgi8AAIsFwACk-8gUYZD_811Q0dGNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه دوم - استاد صیاد")


@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'GENETICS_SAYYAD_SESSIONS')
def send_sayyad_session3(message):
    file_ids = [
        "BQACAgQAAxkBAAIGx2hzTSfjTW0xUr2oh-k3674F2OrjAAKZHAACiLAQUZkc6PCY2geuNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه سوم - استاد صیاد")


@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 استاد یاسایی" and user_states.get(msg.from_user.id) == 'GENETICS_MENU')
def show_yasaei_menu(message):
    user_states[message.from_user.id] = 'GENETICS_YASAEI'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه", "🔙 بازگشت به منوی ژنتیک")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI')
def send_yasaei_full_note(message):
    # ← اینجا فایل‌آیدی‌ها رو بذار
    file_ids = [
        "BQACAgQAAxkBAAIGymhzTaB33D8BUStLukI0ByoQxhvZAAKAHwAChL1gUxdZCdRWh9haNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📚 جزوه جامع - استاد یاسایی")


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI')
def show_yasaei_sessions_menu(message):
    user_states[message.from_user.id] = 'GENETICS_YASAEI_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم",
               "4️⃣ جلسه چهارم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_1(message):
    # فایل‌آیدی‌های جلسه اول
    file_ids = [
        "BQACAgQAAxkBAAIGz2hzTeBzXtjs9wlddni4hW8uFBafAAKaFQACDQxBU2z5WFBkaFuwNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه اول - استاد یاسایی")


@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_2(message):
    # فایل‌آیدی‌های جلسه دوم
    file_ids = [
        "BQACAgQAAxkBAAIG2WhzTpZgFj9qScw5bHnqf1ftxE1qAAKkFgACa9GQUWuwVTsOhj0CNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه دوم - استاد یاسایی")


@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_3(message):
    # فایل‌آیدی‌های جلسه سوم
    file_ids = [
        "BQACAgQAAxkBAAIG1WhzTjvbx6YYdenFn_dMCOELng7qAAJtHwAChL1gUx821SSDfoibNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه سوم - استاد یاسایی")


@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'GENETICS_YASAEI_SESSIONS')
def send_yasaei_session_4(message):
    # فایل‌آیدی‌های جلسه چهارم
    file_ids = [
        "BQACAgQAAxkBAAIG1mhzTjtxLI-dS02yAAHqxyGAJvVWbQACbh8AAoS9YFOgl826zLe_qzYE"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه چهارم - استاد یاسایی")


@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 استاد عمرانی" and user_states.get(msg.from_user.id) == 'GENETICS_MENU')
def show_omrani_menu(message):
    user_states[message.from_user.id] = 'GENETICS_OMRANI'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("❓ نمونه‌سوالات", "🔙 بازگشت به منوی ژنتیک")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "❓ نمونه‌سوالات" and user_states.get(msg.from_user.id) == 'GENETICS_OMRANI')
def send_omrani_questions(message):
    # جایگزین با فایل‌آیدی‌های واقعی
    file_ids = [
        "BQACAgQAAxkBAAIG22hzTtFxp-0Tj4CXtS9nZd4UgnhCAAJ-HwAChL1gUykVb1TUTZshNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="❓ نمونه‌سوالات - استاد عمرانی")


@bot.message_handler(func=lambda msg: msg.text == "👨‍🏫 استاد قادریان" and user_states.get(msg.from_user.id) == 'GENETICS_MENU')
def show_ghaderian_menu(message):
    user_states[message.from_user.id] = 'GENETICS_GHADERIAN'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 پاور", "📚 منابع مطالعاتی", "🔙 بازگشت به منوی ژنتیک")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN')
def send_ghaderian_powerpoints(message):
    # اینجا فایل‌آیدی‌های پاورپوینت‌ها رو بزار
    file_ids = ["BQACAgQAAxkBAAIG3WhzTzLgVYKjAhBuvj7OaGC0K6O1AAJtGgAConcgUQ_7zKM6Uy_QNgQ", "BQACAgQAAxkBAAIG3mhzTzKctv5YHsWTd820jlb86WtfAAJsGgAConcgUe_FGydhVQwgNgQ",
                "BQACAgQAAxkBAAIG4mhzT0LMjDpg7B3OGn_0X2dId6isAAJ9HwACGo5oUXbozRaUTCvkNgQ", "BQACAgQAAxkBAAIG4WhzT0KEbntf_7oSA3l5i7XUfAwsAAJ8HwACGo5oURbRyuCOmv_gNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📊 پاور - استاد قادریان")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN')
def show_ghaderian_resources_menu(message):
    user_states[message.from_user.id] = 'GENETICS_GHADERIAN_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📘 رفرنس", "📑 خلاصه رفرنس", "🔙 بازگشت به منوی قبلی")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📘 رفرنس" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN_RESOURCES')
def send_ghaderian_references(message):
    # جایگزین فایل‌آیدی‌های رفرنس
    file_ids = ["BQACAgQAAxkBAAIG5WhzT5OZ0z6etN2ekhaQt6YgrJPqAAIQFQACa9GAUQ-qmiS0W-ukNgQ",
                "BQACAgQAAxkBAAIG5mhzT5MxODtHnLXuE0VE4U7dS3w7AAIWFQACa9GAUeCDvd5v06YbNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📘 رفرنس - استاد قادریان")


@bot.message_handler(func=lambda msg: msg.text == "📑 خلاصه رفرنس" and user_states.get(msg.from_user.id) == 'GENETICS_GHADERIAN_RESOURCES')
def send_ghaderian_reference_summaries(message):
    # جایگزین فایل‌آیدی‌های خلاصه رفرنس
    file_ids = ["<SUMMARY_FILE_ID_1>", "<SUMMARY_FILE_ID_2>"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📑 خلاصه رفرنس - استاد قادریان")

# --- هندلرهای درس بیوشیمی ---


@bot.message_handler(func=lambda msg: msg.text == "⚗️ بیوشیمی" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_biochemistry_menu(message):
    user_states[message.from_user.id] = 'BIOCHEMISTRY'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("⚗️ بیوشیمی نظری 2"), types.KeyboardButton(
        "🧫 بیوشیمی عملی"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم بخش؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "⚗️ بیوشیمی نظری 2" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY')
def show_biochemistry_theory_menu(message):
    user_states[message.from_user.id] = 'BIOCHEMISTRY_THEORY'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📊 پاور"), types.KeyboardButton(
        "📄 جزوه استاد"), types.KeyboardButton("🔙 بازگشت به منوی بیوشیمی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY_THEORY')
def send_biochemistry_powerpoints(message):
    # فایل‌آیدی‌های پاورپوینت
    file_ids = ["BQACAgQAAxkBAAIG6mhzUDPPRfaEc5BXjemgahkHYJpmAAKkHAACiLAQUUJw3AfZBH3mNgQ", "BQACAgQAAxkBAAIG6WhzUDPybCgfyu4el291iNOB8095AAKiHAACiLAQUfqmOpNawN8HNgQ",
                "BQACAgQAAxkBAAIG62hzUDNCtNF8e4j8uDCT5nq35a24AAKlHAACiLAQUcKg-Sl0cuCONgQ",
                "BQACAgQAAxkBAAIG7GhzUDOVNr-nXDzdC-tfCplvfZqHAAKmHAACiLAQUVeAPxeAQj6aNgQ",
                "BQACAgQAAxkBAAIG7WhzUDN3Tt4Ied9dHXeFeT9VATnzAAKnHAACiLAQURyPasZoJfYXNgQ",
                "BQACAgQAAxkBAAIG7mhzUDMMC0AhiA5BRk7FmgskAlmEAAKpHAACiLAQUYqoj8BtpiuENgQ",
                "BQACAgQAAxkBAAIG72hzUDNApOsGMtds3iSdtOYPkoOKAAKqHAACiLAQUTLcldB-NWjKNgQ",
                "BQACAgQAAxkBAAIG8GhzUDMnqtruvjeQOpR57PDJpmrwAAKsHAACiLAQUesG5vC52OBwNgQ",
                "BQACAgQAAxkBAAIG8WhzUDNWti-AR_x6UF8w8gU9Zse_AAKuHAACiLAQUVSFr8LjlgT3NgQ",
                "BQACAgQAAxkBAAIG8mhzUDPafOgHZIy5AAE__wFH-EvS6gACrxwAAoiwEFGjEytu4ojPBDYE",
                "BQACAgQAAxkBAAIG82hzUDNJP2L8MvinwflaCGiJGR8IAAKwHAACiLAQUbtr10luRAFbNgQ",
                "BQACAgQAAxkBAAIG9GhzUDMOCEldfhD6S1NrNqYybTm3AAKxHAACiLAQUZbWc_U12H_cNgQ",
                "BQACAgQAAxkBAAIG9WhzUDNg36r4h4NCDcSHcfb_LAgDAAKyHAACiLAQUSca0K7Z7x16NgQ",
                "BQACAgQAAxkBAAIG9mhzUDOaLhOucCI2geT-zElBCC0_AAKzHAACiLAQUdhY-_mUksePNgQ",
                "BQACAgQAAxkBAAIG92hzUDOyJ-wP-9oxTQmi3ULcqL0KAAK1HAACiLAQUTvujynCQx4gNgQ",
                ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📊 پاور بیوشیمی نظری 2")


@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه استاد" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY_THEORY')
def send_biochemistry_lecturer_notes(message):
    # فایل‌آیدی‌های جزوه استاد
    file_ids = [
        "BQACAgQAAxkBAAIHB2hzUSVYBQ7qiFmocUJAeEYegst2AAKzEwACmyKQUa_FTh1KPYBYNgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📄 جزوه استاد بیوشیمی نظری 2")


@bot.message_handler(func=lambda msg: msg.text == "🧫 بیوشیمی عملی" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY')
def show_biochemistry_practical_menu(message):
    user_states[message.from_user.id] = 'BIOCHEMISTRY_PRACTICAL'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("📄 جزوه استاد"),
               types.KeyboardButton("🔙 بازگشت به منوی بیوشیمی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه استاد" and user_states.get(msg.from_user.id) == 'BIOCHEMISTRY_PRACTICAL')
def send_biochemistry_practical_lecturer_notes(message):
    file_ids = [
        "BQACAgQAAxkBAAIHCWhzUU5g4bRNtXxnBfEP7wglJ_6QAAJrFAAC9-CoUWIaSqnlCw54NgQ"]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📄 جزوه استاد بیوشیمی عملی")

# --- هندلرهای درس فیزیک پزشکی ---


@bot.message_handler(func=lambda msg: msg.text == "⚛️ فیزیک پزشکی" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_physics_menu(message):
    user_states[message.from_user.id] = 'PHYSICS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📚 منابع مطالعاتی"), types.KeyboardButton(
        "📊 پاور"), types.KeyboardButton("🎤 ویس"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'PHYSICS')
def send_physics_powers(message):
    file_ids = [
        "BQACAgQAAxkBAAO8aG9K7EOHy-mZow2eLOIFk8mNBoEAAtsaAAJg14hRvOuW4dPoIAABNgQ",
        "BQACAgQAAxkBAAO9aG9K7GFz02UAAd9BFS9bdrw_BvYqAALcGgACYNeIUX8iA7I7ENjLNgQ",
        "BQACAgQAAxkBAAO-aG9K7N6uVgyYIHXINekvqpUcScsAAt0aAAJg14hRz2yQ9tzMWLs2BA",
        "BQACAgQAAxkBAAO_aG9K7NDR6jkyHXOx9tOlZHsXcuAAAt4aAAJg14hRMm5pBbZO7uI2BA"
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📊 پاور فیزیک پزشکی")


@bot.message_handler(func=lambda msg: msg.text == "🎤 ویس" and user_states.get(msg.from_user.id) == 'PHYSICS')
def send_physics_voice_notes(message):
    file_ids = [
        "CQACAgQAAxkBAAIHE2hzUfN8zirh2fh7iBvSz7cz-5WWAALiGgACYNeIUbtLhGJVfdc3NgQ",
        "CQACAgQAAxkBAAIHFGhzUfOVGIhOU9_E8-00iiVTuRfoAAL4GgACYNeIUQABwqKYP9_tXDYE",
        "CQACAgQAAxkBAAIHFWhzUfM37s81NPZVXOhBigpbAYh0AAL6GgACYNeIUbFDO4ahO5JbNgQ",
        "CQACAgQAAxkBAAIHFmhzUfMrcUqA8ZzD7-lA5QizahdWAAL7GgACYNeIUU-selm0HHlJNgQ",
        "CQACAgQAAxkBAAIHF2hzUfMesU8y4KLu07cpzK8aDod7AAL8GgACYNeIUQ4LUJeDIs0_NgQ",
        "CQACAgQAAxkBAAIHGGhzUfOCLjKuQ6c4sri04T9qNPngAAL9GgACYNeIUYjnpG897j9RNgQ"
        # فایل‌آیدی‌های بیشتر ویس‌ها
    ]
    for file_id in file_ids:
        bot.send_voice(message.chat.id, file_id, caption="🎤 ویس فیزیک پزشکی")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSICS')
def show_physics_resources_menu(message):
    user_states[message.from_user.id] = 'PHYSICS_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("❓ نمونه سوال"), types.KeyboardButton("📄 جزوات جامع"), types.KeyboardButton(
        "📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی فیزیک پزشکی"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "❓ نمونه سوال" and user_states.get(msg.from_user.id) == 'PHYSICS_RESOURCES')
def send_physics_sample_questions(message):
    file_ids = [
        "BQACAgQAAxkBAAPMaG9LcDPdu9RsvYCRBlMKYPSVIu8AArcWAAKfmcBTDQ_6qcgHnzo2BA",]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="❓ نمونه سوال فیزیک پزشکی")


@bot.message_handler(func=lambda msg: msg.text == "📄 جزوات جامع" and user_states.get(msg.from_user.id) == 'PHYSICS_RESOURCES')
def show_physics_comprehensive_menu(message):
    user_states[message.from_user.id] = 'PHYSICS_COMPREHENSIVE'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🎓 جزوه ورودی 401"), types.KeyboardButton(
        "📎 فایل ضمیمه"), types.KeyboardButton("🔙 بازگشت به منوی قبلی"))
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🎓 جزوه ورودی 401" and user_states.get(msg.from_user.id) == 'PHYSICS_COMPREHENSIVE')
def send_physics_401_notes(message):
    file_ids = [
        "BQACAgQAAxkBAAIHIWhzUo102Tb7ajSupnlBZeLiOnS2AAKRFQAChiixUqLFEeZHmxb-NgQ",
        # فایل‌آیدی‌های بیشتر جزوه 401
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="🎓 جزوه ورودی 401 فیزیک پزشکی")


@bot.message_handler(func=lambda msg: msg.text == "📎 فایل ضمیمه" and user_states.get(msg.from_user.id) == 'PHYSICS_COMPREHENSIVE')
def send_physics_attached_files(message):
    file_ids = [
        "BQACAgQAAxkBAAIHI2hzUrGbBetV_WKDkVHqpijlFaF9AAJrGAACrD-YU_UYPeCOtD-xNgQ",
        # فایل‌آیدی‌های بیشتر فایل ضمیمه
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📎 فایل ضمیمه فیزیک پزشکی")


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSICS_RESOURCES')
def show_physics_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSICS_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم",
               "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "2️⃣1️⃣ جلسه دوازدهم", "3️⃣1️⃣ جلسه سیزدهم", "🔙 بازگشت به منابع فیزیک پزشکی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text in [
    "1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم",
    "6️⃣ جلسه ششم", "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم",
    "1️⃣1️⃣ جلسه یازدهم", "2️⃣1️⃣ جلسه دوازدهم", "3️⃣1️⃣ جلسه سیزدهم"
] and user_states.get(msg.from_user.id) == 'PHYSICS_SESSIONS')
def send_physics_session_files(message):
    session_files = {
        # اگر چند فایل دارید
        "1️⃣ جلسه اول":"BQACAgQAAxkBAAIL2Gh3ZT_LlDNZdfzy1ZIfhZBuG6EAA0QfAAKEvWBTWdwpURlVH-A2BA",
        "2️⃣ جلسه دوم":"BQACAgQAAxkBAAIHP2hzU0kQpiDnx-0axfbnB1TZwZbIAALRFQAC_6CIUuv_rlAm79iHNgQ",
        "3️⃣ جلسه سوم":"BQACAgQAAxkBAAIHJ2hzUx7tBhaifcrkZSAjqROENxuZAAJEHwAChL1gU1ncKVEZVR_gNgQ",
        "4️⃣ جلسه چهارم":"BQACAgQAAxkBAAIHKWhzUx5D7s29iJ4I1BWXQyeYPlHaAAJGHwAChL1gU9wqjayux49ONgQ",
        "5️⃣ جلسه پنجم":"BQACAgQAAxkBAAIHKmhzUx7fsxL4NtCQA-s4qyVfyNJgAAJHHwAChL1gU9yHox6yLv9JNgQ",
        "6️⃣ جلسه ششم":"BQACAgQAAxkBAAIHK2hzUx6rnGj34AE1bpcY2QsFV9YqAAJIHwAChL1gU6RMEtT-Qm1ZNgQ",
        "7️⃣ جلسه هفتم":"BQACAgQAAxkBAAIHLGhzUx77tRN1vN3ajScCbypI0HCcAAJJHwAChL1gU43nnLUq4pA2Ng",
        "8️⃣ جلسه هشتم":"BQACAgQAAxkBAAIHLWhzUx7JziYEkORe8TWEg6ipSYlXAAJKHwAChL1gUwABM-g8pnmY0TYE",
        "9️⃣ جلسه نهم":"BQACAgQAAxkBAAIHLmhzUx6-NIaqJD83HRGyt5k5lrIPAAJLHwAChL1gU2e0WBib8nYVNgQ",
        "🔟 جلسه دهم":"BQACAgQAAxkBAAIHL2hzUx7BXT91Syxbg9E1RGAxvZJTAAJMHwAChL1gU0TgP1FumLFSNgQ",
        "1️⃣1️⃣ جلسه یازدهم":"BQACAgQAAxkBAAIHMGhzUx7dP9khEoPgoAABu145zVERYQACTR8AAoS9YFMCSlBlDRuatzYE",
        "2️⃣1️⃣ جلسه دوازدهم":"BQACAgQAAxkBAAIHMWhzUx5Ik8dcbIwrsK_wsn6J3o4MAAJOHwAChL1gUyhjTX89d8W9NgQ",
        "3️⃣1️⃣ جلسه سیزدهم":"BQACAgQAAxkBAAIHMmhzUx4IUCiKF2Wy_xbxts6RGcpsAAJPHwAChL1gU992MuBbFk2sNgQ",
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
    buttons = ["🔬 سلول (استاد گشادرو)", "❤️ قلب (استاد زردوز)",
               "🍔 گوارش (استاد قاسمی)", "🩸 گردش خون (استاد حسین‌مردی)", "🔙 بازگشت به دروس"]
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
    "BQACAgQAAxkBAAIHQWhzVL3ysK8GV6iUZ56fZ3URa4kNAALiFgACVhOpUrmI0GpoyVi3NgQ",
    "BQACAgQAAxkBAAIHQmhzVL2ENbHrcWaQJWR-aPK3SzTbAALoFgACVhOpUl9Y3FT0UuvANgQ",
    "BQACAgQAAxkBAAIHQ2hzVL2haSdsLqGRcNYxe-iZ_ah9AALqFgACVhOpUg15P0aaJHH9NgQ",
]


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CELL')
def show_physiology_cell_resources(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CELL_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📄 جزوه استاد", "🔙 بازگشت به منوی سلول")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


# فایل ایدی‌های جزوه استاد برای بخش سلول (استاد گشادرو)
physiology_cell_teacher_notes = [
    "BQACAgQAAxkBAAIBUGhvrYz8Se4kdQF0mZDsYBr7bOmwAAKBDwAC5btBULqNUX60u1naNgQ",
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
    "BQACAgQAAxkBAAIHSWhzVWLZsnU2jUJVVh338t64hMRyAAKwGgAC7ZJhUBT9VDEUBMkVNgQ",
    "BQACAgQAAxkBAAIHSmhzVWLDa1Sm6BrJi53wMNZbws8ZAAKxGgAC7ZJhUHGHPauLGelYNgQ",
    "BQACAgQAAxkBAAIHS2hzVWJuV0O37gHCq795GcrQfjWzAAKyGgAC7ZJhUChZR-FFynh6NgQ",
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
physiology_heart_comprehensive_note_file_id = "BQACAgQAAxkBAAIHT2hzVeGdA1QRvpPwSXc_ccIvGkYgAAJsGAACrD-YU7PnYMxABEgmNgQ"


@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART_RESOURCES')
def send_physiology_heart_comprehensive_note(message):
    bot.send_document(
        message.chat.id, physiology_heart_comprehensive_note_file_id)


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_HEART_RESOURCES')
def show_zardouz_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_HEART_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم",
               "3️⃣ جلسه سوم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


# فایل ایدی جزوات جلسات قلب (استاد زردوز)
physiology_heart_session_files = {
    "1️⃣ جلسه اول": "BQACAgQAAxkBAAIHUWhzVjOVLNBrPLJYrMFnY3bAatzFAAJcGQACTAoAAVDGPKzNqzkNlTYE",
    "2️⃣ جلسه دوم": "BQACAgQAAxkBAAIHU2hzVkZXcliyyeRD3jirEfWzchgaAALpGgACTAoQUGDfhPN-onNMNgQ",
    "3️⃣ جلسه سوم": "BQACAgQAAxkBAAIHVWhzVlyjJYR7aCk-wqtH1DHuixzpAALGGAACljpwUCdeZe0BjIbSNgQ",
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
        "BQACAgQAAxkBAAIHV2hzVqNgVKxtPOdqPFYhtXwTjdOdAAJDGwACWg7YUPZGTKXvfcl4NgQ",
        "BQACAgQAAxkBAAIHWWhzVs7SxM0ZWbgt3G7f1v7bn5w-AALNFgACk-8YUVDUKJIX0G4pNgQ",
        "BQACAgQAAxkBAAIHW2hzVtck--yYTanJacs_hPilHukeAAIbHQACEDBBUUKF73hExQ5wNgQ",
        "BQACAgQAAxkBAAIHXWhzVu-bsng-_EOtjYT52YduF680AAKeGgACeFzpUSD8Xlu8KZ6xNgQ"
        # فایل آیدی‌های بیشتر پاور گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📊 پاور گوارش (استاد قاسمی)")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION')
def show_physiology_digestion_resources(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_DIGESTION_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه", "🔙 بازگشت به منوی گوارش")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_RESOURCES')
def send_physiology_digestion_comprehensive_files(message):
    file_ids = [
        "BQACAgQAAxkBAAIHX2hzVzwcW5zOPI4ZtGo6PtOr2DXQAAJ1GAACrD-YU1N-DcnoNSfgNgQ",
        # فایل آیدی‌های بیشتر جزوه جامع گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📚 جزوه جامع گوارش (استاد قاسمی)")


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_RESOURCES')
def show_ghasemi_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_DIGESTION_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم",
               "4️⃣ جلسه چهارم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session1_files(message):
    file_ids = [
        "BQACAgQAAxkBAAIHYWhzV3LwV53d3Tdf5Awyix0FsNR3AAI5HAACpdr5UDQxsWzfX7siNgQ"
        # فایل آیدی‌های بیشتر جلسه اول گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جزوه جلسه اول گوارش (استاد قاسمی)")


@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session2_files(message):
    file_ids = [
        "BQACAgQAAxkBAAIHY2hzV32mX1Ai5TmdfA18ZPqoP5CtAAICFwAC0mk4UcbL1IX4A7spNgQ"
        # فایل آیدی‌های بیشتر جلسه دوم گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جزوه جلسه دوم گوارش (استاد قاسمی)")


@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session3_files(message):
    file_ids = [
        "BQACAgQAAxkBAAIHZWhzV4bp8WCADMFDWYNEW6yx3gMIAALOHAACFC1ZUeUrxJn5ZR7INgQ"
        # فایل آیدی‌های بیشتر جلسه سوم گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جزوه جلسه سوم گوارش (استاد قاسمی)")


@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_DIGESTION_SESSIONS')
def send_ghasemi_session4_files(message):
    file_ids = [
        "BQACAgQAAxkBAAIHZ2hzV-CbdFOvTszbLwqf6y6d-SIAA2AYAAKsP5hTovGxYRPQQnQ2BA"
        # فایل آیدی‌های بیشتر جلسه چهارم گوارش
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جزوه جلسه چهارم گوارش (استاد قاسمی)")


@bot.message_handler(func=lambda msg: msg.text == "🩸 گردش خون (استاد حسین‌مردی)" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_MENU')
def show_physiology_circulation_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CIRCULATION'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 پاور", "📚 منابع مطالعاتی", "🔙 بازگشت به منوی فیزیولوژی")
    bot.send_message(message.chat.id, "کدوم؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION')
def send_circulation_powerpoint_files(message):
    file_ids = [
        "BQACAgQAAxkBAAIHaWhzWFp3j8G0Ccn6e8Bf1CiWzXlzAAIxGgACEDBRUZY0w8xp5JyaNgQ"
        # فایل آیدی‌های بیشتر پاور گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📊 پاور گردش خون (استاد حسین‌مردی)")


@bot.message_handler(func=lambda msg: msg.text == "📚 منابع مطالعاتی" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION')
def show_physiology_circulation_resources(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CIRCULATION_RESOURCES'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 جزوه جامع", "📝 جزوات جلسه به جلسه",
               "🔙 بازگشت به منوی گردش خون")
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📚 جزوه جامع" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_RESOURCES')
def send_circulation_comprehensive_notes(message):
    file_ids = [
        "BQACAgQAAxkBAAIHa2hzWLdu7YdFC-O3VRBm49rT0U5VAAJ2GAACrD-YUwljm18WC6eDNgQ"
        # فایل آیدی‌های بیشتر جزوه جامع گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📚 جزوه جامع گردش خون (استاد حسین‌مردی)")


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_RESOURCES')
def show_hosseinmardi_sessions_menu(message):
    user_states[message.from_user.id] = 'PHYSIOLOGY_CIRCULATION_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم",
               "4️⃣ جلسه چهارم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "1️⃣ جلسه اول" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_1(message):
    file_ids = [
        "BQACAgQAAxkBAAIHcGhzWQpa0XR0KAYOt0oW2hSBHW-lAAJeGAACrD-YU_6329JQ_XEhNgQ"
        # فایل آیدی‌های بیشتر جلسه اول گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه اول گردش خون (استاد حسین‌مردی)")


@bot.message_handler(func=lambda msg: msg.text == "2️⃣ جلسه دوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_2(message):
    file_ids = [
        "BQACAgQAAxkBAAIHb2hzWQqfs-aaFzF55YIXtz2ge12HAAJdGAACrD-YU8HXiw8j3evUNgQ",
        # فایل آیدی‌های بیشتر جلسه دوم گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه دوم گردش خون (استاد حسین‌مردی)")


@bot.message_handler(func=lambda msg: msg.text == "3️⃣ جلسه سوم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_3(message):
    file_ids = [
        "BQACAgQAAxkBAAIHcWhzWQqEIpCSWf6L7XO39vzhe05XAAJzGAACrD-YU_ECVUQAAU76YjYE",
        # فایل آیدی‌های بیشتر جلسه سوم گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه سوم گردش خون (استاد حسین‌مردی)")


@bot.message_handler(func=lambda msg: msg.text == "4️⃣ جلسه چهارم" and user_states.get(msg.from_user.id) == 'PHYSIOLOGY_CIRCULATION_SESSIONS')
def send_hosseinmardi_session_4(message):
    file_ids = [
        "BQACAgQAAxkBAAIHcmhzWQqFp5cZRkjb3YKp8F3WAmy_AAJhGAACrD-YU2EhV9dmZ5eNNgQ"
        # فایل آیدی‌های بیشتر جلسه چهارم گردش خون (استاد حسین‌مردی)
    ]
    for file_id in file_ids:
        bot.send_document(message.chat.id, file_id,
                          caption="📝 جلسه چهارم گردش خون (استاد حسین‌مردی)")

# --- هندلرهای درس اندیشه اسلامی 1 ---


@bot.message_handler(func=lambda msg: msg.text == "🕌 اندیشه اسلامی 1" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_islamic_thought_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_MENU'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🧕 بانوان"), types.KeyboardButton(
        "🧔 آقایان"), types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم گروه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🧕 بانوان" and user_states.get(msg.from_user.id) == 'ISLAMIC_THOUGHT_MENU')
def show_islamic_thought_women_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_WOMEN'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 رفرنس"), types.KeyboardButton("📚 جزوه جامع"), types.KeyboardButton(
        "📝 جزوات جلسه به جلسه"), types.KeyboardButton("🔙 بازگشت به منوی اندیشه"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📝 جزوات جلسه به جلسه" and user_states.get(msg.from_user.id) == 'ISLAMIC_THOUGHT_WOMEN')
def show_islamic_thought_women_sessions_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_WOMEN_SESSIONS'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = ["1️⃣ جلسه اول", "2️⃣ جلسه دوم", "3️⃣ جلسه سوم", "4️⃣ جلسه چهارم", "5️⃣ جلسه پنجم", "6️⃣ جلسه ششم",
               "7️⃣ جلسه هفتم", "8️⃣ جلسه هشتم", "9️⃣ جلسه نهم", "🔟 جلسه دهم", "1️⃣1️⃣ جلسه یازدهم", "🔙 بازگشت به منوی قبلی"]
    markup.add(*[types.KeyboardButton(b) for b in buttons])
    bot.send_message(message.chat.id, "کدوم جلسه؟ 🤔", reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "🧔 آقایان" and user_states.get(msg.from_user.id) == 'ISLAMIC_THOUGHT_MENU')
def show_islamic_thought_men_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_THOUGHT_MEN'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("❓ نمونه سوالات"),
               types.KeyboardButton("🔙 بازگشت به منوی اندیشه"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

# --- هندلرهای درس فرهنگ و تمدن اسلام ---


@bot.message_handler(func=lambda msg: msg.text == "📜 فرهنگ و تمدن اسلام" and user_states.get(msg.from_user.id) == 'TERM_2')
def show_islamic_culture_menu(message):
    user_states[message.from_user.id] = 'ISLAMIC_CULTURE_MENU'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("❓ نمونه سوالات"),
               types.KeyboardButton("🔙 بازگشت به دروس"))
    bot.send_message(message.chat.id, "کدوم منبع؟ 🤔", reply_markup=markup)

# --- TERM 2 هندلرهای بازگشت ---


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
    bot.send_message(
        message.chat.id, "⚠️ دستور نامعتبر! لطفاً از دکمه‌های منو استفاده کنید. بازگشت به منوی اصلی...")
    send_welcome(message)

# ===============================================================
# بخش ۵: اجرای نهایی ربات 🚀
# ===============================================================


if __name__ == "__main__":
    print("Starting keep-alive server...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    bot.remove_webhook()
    print("Bot server started. Running polling...")

    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=2)
        except Exception as e:
            print(f" Error in polling: {e}")
            # ذخیره وضعیت کاربران قبل از ری‌استارت یا توقف
            save_user_states()
            if ADMIN_CHAT_ID:
                try:
                    bot.send_message(
                        ADMIN_CHAT_ID, f"⚠️ خطا در اجرای ربات:\n{e}")
                except Exception as e_send:
                    print(f"Could not send error message to admin: {e_send}")
            time.sleep(15)
