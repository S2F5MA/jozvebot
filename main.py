import telebot
from telebot import types
from dotenv import load_dotenv
import os
from keep_alive import keep_alive

# 📥 بارگذاری متغیرهای محیطی (از .env)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# 🧠 ساخت بات با توکن
bot = telebot.TeleBot(TOKEN)

# ----------------------------------------
# 📎 هندل فایل‌های تکی
# ----------------------------------------


@bot.message_handler(content_types=['document', 'video', 'photo', 'audio', 'voice'])
def get_file_id_single(message):
    file_id = None
    file_type = None

    if message.document:
        file_id = message.document.file_id
        file_type = "📄 Document"
    elif message.video:
        file_id = message.video.file_id
        file_type = "🎬 Video"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "🖼️ Photo"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "🎵 Audio"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "🎤 Voice"

    if file_id:
        bot.send_message(
            message.chat.id, f"{file_type}\n`{file_id}`", parse_mode='Markdown')

# 📎 هندل فایل‌های گروهی


@bot.message_handler(content_types=['media_group'])
def get_file_ids_group(messages):
    for message in messages:
        get_file_id_single(message)

# ----------------------------------------
# 🏠 /start command
# ----------------------------------------


@bot.message_handler(commands=["start"])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📘 ترم 1"),
               types.KeyboardButton("📗 ترم 2"))

    bot.send_message(
        message.chat.id,
        """سلام 👋
قبل اینکه شروع کنی چند تا نکته رو دقت کن : 
1. بعضی درس‌ها جزوه‌هاشون فایلی به اسم فایل ضمیمه داره که نکاتی علاوه بر جزوه اصلی توش نوشته شده !
2. ...
3. ...

حالا لطفاً ترم مورد نظرتو انتخاب کن:""",
        reply_markup=markup
    )

# ----------------------------------------
# 📗 ترم ۲ - لیست دروس
# ----------------------------------------


@bot.message_handler(func=lambda msg: msg.text == "📗 ترم 2")
def show_term2_subjects(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "🧠 علوم تشریح نظری 2", "🦴 علوم تشریح عملی 2",
        "💓 فیزیولوژی نظری 1", "🧪 بیوشیمی نظری 2",
        "🧬 ژنتیک", "🧫 بیوشیمی عملی",
        "🦷 سلامت دهان و جامعه", "📡 فیزیک پزشکی",
        "📚 زبان عمومی", "🕌 فرهنگ و تمدن اسلام",
        "☪️ اندیشه اسلامی", "🔙 بازگشت به خانه"
    ]
    for b in buttons:
        markup.add(types.KeyboardButton(b))

    bot.send_message(message.chat.id, "✅ درس‌های ترم 2:", reply_markup=markup)

# ----------------------------------------
# 📡 فیزیک پزشکی - منو
# ----------------------------------------


@bot.message_handler(func=lambda msg: msg.text == "📡 فیزیک پزشکی")
def show_physic_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📘 جزوه"),
        types.KeyboardButton("❓ نمونه سوال"),
        types.KeyboardButton("📊 پاور"),
        types.KeyboardButton("🔙 بازگشت به درس‌ها")
    )

    bot.send_message(
        message.chat.id,
        """دبیر : دکتر قربانی

لطفاً یکی از گزینه‌های زیر رو برای درس *فیزیک پزشکی* انتخاب کن 🧪:""",
        parse_mode="Markdown",
        reply_markup=markup
    )

# 📘 جزوه اصلی و ضمیمه


@bot.message_handler(func=lambda msg: msg.text == "📘 جزوه")
def show_jozve_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📄 جزوه اصلی"),
        types.KeyboardButton("📎 جزوه ضمیمه"),
        types.KeyboardButton("🔙 بازگشت به منوی فیزیک پزشکی")
    )
    bot.send_message(message.chat.id, "نوع جزوه رو انتخاب کن:",
                     reply_markup=markup)


@bot.message_handler(func=lambda msg: msg.text == "📄 جزوه اصلی")
def send_physic_main_note(message):
    bot.send_document(
        message.chat.id, "BQACAgQAAxkBAAOMaG86XK3gm-cW4bhkJfFof5vmUcsAAnIfAAKEvWBTYvYB0xEXUrc2BA")


@bot.message_handler(func=lambda msg: msg.text == "📎 جزوه ضمیمه")
def send_physic_attach_note(message):
    bot.send_document(
        message.chat.id, "BQACAgQAAxkBAAOAaG85n1nNFFKCpsVcFXPwH7lzmkgAAlsXAAK9vHhTwAh6kf1fS_82BA")

# ❓ نمونه سوال


@bot.message_handler(func=lambda msg: msg.text == "❓ نمونه سوال")
def send_physic_sample_questions(message):
    bot.send_document(
        message.chat.id, "BQACAgQAAxkBAAPMaG9LcDPdu9RsvYCRBlMKYPSVIu8AArcWAAKfmcBTDQ_6qcgHnzo2BA")

# 📊 پاورپوینت‌ها


@bot.message_handler(func=lambda msg: msg.text == "📊 پاور")
def send_physic_ppt_files(message):
    file_ids = [
        "BQACAgQAAxkBAAO8aG9K7EOHy-mZow2eLOIFk8mNBoEAAtsaAAJg14hRvOuW4dPoIAABNgQ",
        "BQACAgQAAxkBAAO-aG9K7N6uVgyYIHXINekvqpUcScsAAt0aAAJg14hRz2yQ9tzMWLs2BA",
        "BQACAgQAAxkBAAO9aG9K7GFz02UAAd9BFS9bdrw_BvYqAALcGgACYNeIUX8iA7I7ENjLNgQ",
        "BQACAgQAAxkBAAO_aG9K7NDR6jkyHXOx9tOlZHsXcuAAAt4aAAJg14hRMm5pBbZO7uI2BA"
    ]
    for fid in file_ids:
        bot.send_document(message.chat.id, fid)

# 🔙 برگشت به منوها


@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به درس‌ها")
def back_to_term2_subjects(message):
    show_term2_subjects(message)


@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به خانه")
def back_home(message):
    send_welcome(message)


@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی فیزیک پزشکی")
def back_to_physic_menu(message):
    show_physic_menu(message)


# ----------------------------------------
# 🚀 اجرای اصلی ربات
# ----------------------------------------
if __name__ == "__main__":
    bot.remove_webhook()
    keep_alive()
    print("✅ keep_alive started. Running bot now...")
    bot.infinity_polling()

print("kir")