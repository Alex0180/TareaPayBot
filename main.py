from dotenv import load_dotenv
import os
from flask import Flask, request
import telebot

# ---------------- CARGAR TOKEN ----------------
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("El token no está configurado en las variables de entorno")

# ---------------- INICIALIZAR BOT ----------------
bot = telebot.TeleBot(TOKEN)

# ---------------- HANDLER /start ----------------
@bot.message_handler(commands=['start'])
def start(message):
    print(f"Comando /start recibido de: {message.chat.id}")
    bot.send_message(message.chat.id, "¡Bot funcionando en Render!")

# ---------------- INICIALIZAR FLASK ----------------
app = Flask(__name__)

# ---------------- RUTA DE PRUEBA ----------------
@app.route("/")
def home():
    return "Bot funcionando!"

# ---------------- POSTBACK ----------------
@app.route("/postback", methods=["GET", "POST"])
def postback():
    data = request.values
    print("POSTBACK RECIBIDO:", data)
    
    user_id = data.get("user_id")
    amount = data.get("amount")
    
    if not user_id or not amount:
        return "Faltan datos", 400
    
    try:
        user_id_int = int(user_id)
        amount_float = float(amount)
    except ValueError:
        return "Datos inválidos", 400

    bot.send_message(user_id_int, f"¡Ganaste ${amount_float}!")
    return "OK", 200

# ---------------- WEBHOOK ----------------
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/"

# Elimina cualquier webhook antiguo
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)
print(f"Webhook configurado en: {WEBHOOK_URL}")

@app.route("/", methods=["POST"])
def webhook():
    json_data = request.get_json()
    print("MENSAJE RECIBIDO:", json_data)
    if json_data:
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    return "OK", 200

# ---------------- EJECUTAR FLASK ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
