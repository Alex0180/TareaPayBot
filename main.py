from dotenv import load_dotenv
import os
from flask import Flask, request
import telebot
import threading

# ---------------- CARGAR TOKEN ----------------
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("El token ")

# ---------------- INICIALIZAR BOT ----------------
bot = telebot.TeleBot(TOKEN)

# ---------------- INICIALIZAR FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot funcionando!"

@app.route("/postback", methods=["GET", "POST"])
def postback():
    data = request.values
    user_id = data.get("user_id")
    amount = data.get("amount")
    
    # Validar datos
    if not user_id or not amount:
        return "Faltan datos", 400
    
    try:
        user_id_int = int(user_id)
        amount_float = float(amount)
    except ValueError:
        return "Datos inválidos", 400

    # Enviar mensaje al usuario
    bot.send_message(user_id_int, f"¡Ganaste ${amount_float}!")
    return "OK", 200

# ---------------- EJECUTAR BOT EN SEGUNDO PLANO ----------------
threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()

# ---------------- EJECUTAR FLASK ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
