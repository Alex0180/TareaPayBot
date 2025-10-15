import os
from flask import Flask, request
import telebot

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Tu handler de mensajes
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "¡Bot funcionando en Render!")

# Ruta para webhook
@app.route("/", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# Establecer puerto dinámico para Render
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=PORT)
