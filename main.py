# main.py
import os
from dotenv import load_dotenv
from flask import Flask, request
import telebot

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN no está en las variables de entorno")

# Crear instancia del bot que usará Render (webhook)
bot = telebot.TeleBot(TOKEN)

# Importar módulo del bot y registrar handlers en la instancia creada
import bot_v8
bot_v8.register_handlers(bot)

# Inicializar DB / migraciones (si tu database.init_db está bien)
bot_v8.init_db()
bot_v8.migrate_json_to_sqlite()

# Flask app
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot funcionando en Render!"

# Webhook URL: Render expone RENDER_EXTERNAL_HOSTNAME
HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if not HOSTNAME:
    # Si no está, sólo imprimir advertencia; Render siempre debe proveerla.
    print("Advertencia: RENDER_EXTERNAL_HOSTNAME no definida.")
WEBHOOK_URL = f"https://{HOSTNAME}/webhook" if HOSTNAME else None

if WEBHOOK_URL:
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Webhook configurado en: {WEBHOOK_URL}")
else:
    print("No se configuró webhook (no hay RENDER_EXTERNAL_HOSTNAME).")

@app.route("/webhook", methods=["POST"])
def webhook():
    json_data = request.get_json()
    if json_data:
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    # Local: si quieres probar con polling cuando no estás en Render, puedes hacerlo
    if os.environ.get("RENDER") is None:
        print("Ejecutando en local: arrancando polling (sólo para pruebas locales).")
        bot.infinity_polling()
    app.run(host="0.0.0.0", port=port)
