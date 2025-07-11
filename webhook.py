from flask import Flask, request
import telebot

API_TOKEN = "7552676791:AAHU-ogfKxQYlg27OO-QeS4sWNxAEdfxzZQ"
bot = telebot.TeleBot(API_TOKEN)

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Bot is running.', 200
