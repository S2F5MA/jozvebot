import telebot
from telebot import types
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# =================================================================
# ⚙️ DATA STRUCTURE ⚙️
# تمام اطلاعات ربات در این دیکشنری ذخیره می‌شود
# برای اضافه کردن درس یا فایل جدید، فقط اینجا را ویرایش کنید
# =================================================================
DATA = {
    "term2": {
        "title": "✅ درس‌های ترم ۲",
        "buttons": {
            "physic": "📡 فیزیک پزشکی",
            "biochem_n": "🧪 بیوشیمی نظری ۲",
            # ... بقیه درس‌ها را اینجا اضافه کنید
            "back_home": "🔙 بازگشت به خانه"
        }
    },
    "physic": {
        "title": "دبیر: دکتر قربانی\nلطفاً یکی از گزینه‌های زیر را برای درس *فیزیک پزشکی* انتخاب کن:",
        "buttons": {
            "physic_jozve": "📘 جزوه",
            "physic_sample": "❓ نمونه سوال",
            "physic_ppt": "📊 پاور",
            "back_term2": "🔙 بازگشت به درس‌ها"
        },
        "files": {
            "sample": "BQACAgQAAxkBAAPMaG9LcDPdu9RsvYCRBlMKYPSVIu8AArcWAAKfmcBTDQ_6qcgHnzo2BA",
            "ppt": [
                "BQACAgQAAxkBAAO8aG9K7EOHy-mZow2eLOIFk8mNBoEAAtsaAAJg14hRvOuW4dPoIAABNgQ",
                "BQACAgQAAxkBAAO-aG9K7N6uVgyYIHXINekvqpUcScsAAt0aAAJg14hRz2yQ9tzMWLs2BA",
                "BQACAgQAAxkBAAO9aG9K7GFz02UAAd9BFS9bdrw_BvYqAALcGgACYNeIUX8iA7I7ENjLNgQ",
                "BQACAgQAAxkBAAO_aG9K7NDR6jkyHXOx9tOlZHsXcuAAAt4aAAJg14hRMm5pBbZO7uI2BA"
            ]
        }
    },
    "physic_jozve": {
        "title": "نوع جزوه را انتخاب کن:",
        "buttons": {
            "physic_jozve_main": "📄 جزوه اصلی",
            "physic_jozve_attach": "📎 جزوه ضمیمه",
            "back_physic": "🔙 بازگشت به منوی فیزیک"
        },
        "files": {
            "main": "BQACAgQAAxkBAAOMaG86XK3gm-cW4bhkJfFof5vmUcsAAnIfAAKEvWBTYvYB0xEXUrc2BA",
            "attach": "BQACAgQAAxkBAAOAaG85n1nNFFKCpsVcFXPwH7lzmkgAAlsXAAK9vHhTwAh6kf1fS_82BA"
        }
    }
}


# =================================================================
# Handlers & Functions
# =================================================================

# ---------- File ID Finder (بدون تغییر) ----------
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
        bot.send_message(message.chat.id, f"{file_type}\n`{file_id}`", parse_mode='Markdown')


# ---------- Start Command ----------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📘 ترم ۱ (فعلاً غیرفعال)", callback_data="term1")
    btn2 = types.InlineKeyboardButton("📗 ترم ۲", callback_data="show_term2")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, "سلام 👋\nبه ربات جزوه خوش آمدی. لطفاً ترم مورد نظرت را انتخاب کن:", reply_markup=markup)


# ---------- Callback Query Handler (قلب ربات جدید شما) ----------
# این تابع تمام کلیک‌های روی دکمه‌های شیشه‌ای را مدیریت می‌کند
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    callback_data = call.data

    # --- نمایش منوها ---
    if callback_data.startswith("show_"):
        menu_key = callback_data.split("_")[1] # e.g., "term2" from "show_term2"
        menu_data = DATA.get(menu_key)
        if menu_data:
            markup = types.InlineKeyboardMarkup(row_width=2)
            buttons = [types.InlineKeyboardButton(text, callback_data=key) for key, text in menu_data["buttons"].items()]
            markup.add(*buttons)
            # ویرایش پیام قبلی به جای ارسال پیام جدید
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=menu_data["title"],
                reply_markup=markup,
                parse_mode="Markdown"
            )

    # --- ارسال فایل‌ها ---
    elif callback_data == "physic_sample":
        bot.send_document(chat_id, DATA["physic"]["files"]["sample"])
        bot.answer_callback_query(call.id, "نمونه سوال ارسال شد.")

    elif callback_data == "physic_jozve_main":
        bot.send_document(chat_id, DATA["physic_jozve"]["files"]["main"])
        bot.answer_callback_query(call.id, "جزوه اصلی ارسال شد.")
        
    elif callback_data == "physic_jozve_attach":
        bot.send_document(chat_id, DATA["physic_jozve"]["files"]["attach"])
        bot.answer_callback_query(call.id, "جزوه ضمیمه ارسال شد.")

    elif callback_data == "physic_ppt":
        bot.answer_callback_query(call.id, "در حال ارسال فایل‌های پاورپوینت...")
        for file_id in DATA["physic"]["files"]["ppt"]:
            bot.send_document(chat_id, file_id)

    # --- مدیریت دکمه‌های بازگشت ---
    elif callback_data == "back_home":
        send_welcome(call.message) # منوی اصلی را دوباره نشان می‌دهد
        bot.delete_message(chat_id, message_id) # پیام قبلی (منوی درس‌ها) را پاک می‌کند

    elif callback_data == "back_term2":
        handle_callback_query(type('obj', (object,),{'data': 'show_term2', 'message': call.message}))

    elif callback_data == "back_physic":
        handle_callback_query(type('obj', (object,),{'data': 'show_physic', 'message': call.message}))

    # به تلگرام اطلاع می‌دهد که کلیک دریافت شد
    bot.answer_callback_query(call.id)


# =================================================================
# 🚀 Start Bot
# =================================================================
print("Bot is running...")
bot.infinity_polling()
