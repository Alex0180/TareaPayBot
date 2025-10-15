# main.py
import os
from dotenv import load_dotenv
from flask import Flask, request
import telebot

# ---------------- CARGAR TOKEN ----------------
load_dotenv()
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("El token no está configurado en las variables de entorno")

# ---------------- INICIALIZAR BOT ----------------
bot = telebot.TeleBot(TOKEN)

# ---------------- IMPORTAR FUNCIONES DEL BOT ----------------
import bot_v8  # aquí se importa todo tu bot v8
# Reemplazamos el bot que creaste en bot_v8 por el mismo de aquí
bot_v8.bot = bot  

# Inicializamos DB y migraciones
bot_v8.init_db()
bot_v8.migrate_json_to_sqlite()

# ---------------- INICIALIZAR FLASK ----------------
app = Flask(__name__)

# ---------------- RUTA DE PRUEBA ----------------
@app.route("/")
def home():
    return "Bot funcionando en Render!"

# ---------------- WEBHOOK ----------------
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"

# eliminar webhook antiguo y configurar nuevo
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)
print(f"Webhook configurado en: {WEBHOOK_URL}")

@app.route("/webhook", methods=["POST"])
def webhook():
    json_data = request.get_json()
    if json_data:
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    return "OK", 200

# ---------------- EJECUTAR FLASK ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
