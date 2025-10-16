# main.py
import os
from dotenv import load_dotenv
from flask import Flask, request
import telebot
import bot_v8  # Tu bot actualizado

# ---------------- CARGAR TOKEN ----------------
load_dotenv()
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN no está en las variables de entorno")

# ---------------- INICIALIZAR BOT ----------------
bot = telebot.TeleBot(TOKEN)

# ---------------- REGISTRAR HANDLERS ----------------
bot_v8.register_handlers(bot)

# ---------------- INICIALIZAR BASE DE DATOS ----------------
bot_v8.init_db()
bot_v8.migrate_json_to_sqlite()

# ---------------- INICIALIZAR DB DE JUEGOS ----------------
bot_v8.init_games_db()

# ---------------- FLASK APP ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot funcionando en Render!"

# ---------------- CONFIGURAR WEBHOOK ----------------
HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_URL = f"https://{HOSTNAME}/webhook" if HOSTNAME else None

if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        print("Webhook eliminado (si existía)")
    except Exception as e:
        print("No se pudo eliminar webhook previo:", e)

    try:
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Webhook configurado correctamente en: {WEBHOOK_URL}")
    except Exception as e:
        print("Error configurando webhook:", e)
else:
    print("No se configuró webhook: RENDER_EXTERNAL_HOSTNAME no está definido")

# ---------------- ENDPOINT WEBHOOK ----------------
@app.route("/webhook", methods=["POST"])
def webhook():
    json_data = request.get_json()
    if json_data:
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    return "OK", 200

# ---------------- ENDPOINT POSTBACK (para anuncios) ----------------
@app.route("/postback", methods=["POST"])
def postback():
    data = request.get_json()
    user_id = data.get("user_id")
    payout = data.get("payout", 0)
    if user_id:
        bot_v8.handle_postback(user_id, payout)
    return "OK", 200

# ---------------- EJECUTAR APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    if os.environ.get("RENDER") is None:
        print("Ejecutando en local: polling activado")
        bot.infinity_polling()
    else:
        print(f"Ejecutando en Render: puerto {port}")
        app.run(host="0.0.0.0", port=port)
