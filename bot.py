# bot.py
import telebot
from telebot import types
import os, json, time

# ---------- CONFIG ----------
TOKEN = "8218883930:AAHv4Hgenj2zfC9rs88ACjjxrCfAqoSWbn0"  # <- pega tu token aquí
DATA_FILE = "users.json"
START_BALANCE = 0.0
CREDIT_PER_AD = 0.05   # saldo simulado por 'ver anuncio' (para pruebas)
# ----------------------------

bot = telebot.TeleBot(TOKEN)

# ----------------- UTILIDADES -----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_user(user_id, username=None, lang="es"):
    data = load_data()
    sid = str(user_id)
    if sid not in data:
        data[sid] = {
            "username": username or "",
            "balance": START_BALANCE,
            "created_at": int(time.time()),
            "lang": lang,
            "history": []
        }
        save_data(data)
    return data[sid]

def add_balance(user_id, amount, reason="reward"):
    data = load_data()
    sid = str(user_id)
    if sid not in data:
        ensure_user(user_id)
        data = load_data()
    data[sid]["balance"] = round(data[sid]["balance"] + amount, 8)
    data[sid]["history"].append({
        "at": int(time.time()),
        "amount": amount,
        "reason": reason
    })
    save_data(data)
    return data[sid]["balance"]

# ----------------- TECLADOS -----------------
def main_keyboard(lang="es"):
    if lang == "en":
        keys = ["💸 Earn", "📤 Withdraw", "📊 Balance", "⚙️ Lang"]
    else:
        keys = ["💸 Ver anuncio", "📤 Retirar", "📊 Saldo", "⚙️ Idioma"]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for k in keys:
        markup.add(types.KeyboardButton(k))
    return markup

# ----------------- START -----------------
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    user = ensure_user(message.from_user.id, message.from_user.username)
    lang = user.get("lang", "es")
    text = "👋 Bienvenido a TareaPay Bot!\n\n" if lang=="es" else "👋 Welcome to TareaPay Bot!\n\n"
    if lang == "es":
        text += "Gana viendo anuncios y completando tareas. Usa el teclado para empezar."
    else:
        text += "Earn by watching ads and completing simple tasks. Use the keyboard to start."
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard(lang))

# ----------------- MENÚ PRINCIPAL -----------------
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text.strip()
    user = ensure_user(message.from_user.id, message.from_user.username)
    lang = user.get("lang", "es")

    if text == "📊 Saldo" or text.lower() == "balance":
        data = load_data()
        bal = data.get(str(message.from_user.id), {}).get("balance", 0.0)
        if lang == "es":
            bot.send_message(message.chat.id, f"💰 Tu saldo: ${bal:.2f}")
        else:
            bot.send_message(message.chat.id, f"💰 Your balance: ${bal:.2f}")

    elif text == "💸 Ver anuncio" or text.lower() == "earn":
        markup = types.InlineKeyboardMarkup()
        btn_text = "He visto" if lang=="es" else "I watched"
        markup.add(types.InlineKeyboardButton(text=btn_text, callback_data="watched_ad"))

        if lang=="es":
            bot.send_message(
                chat_id=message.chat.id,
                text="👉 Abre este enlace y mira el anuncio:\nhttps://example.com\n\nCuando termines, pulsa el botón.",
                reply_markup=markup
            )
        else:
            bot.send_message(
                chat_id=message.chat.id,
                text="👉 Open this link and watch the ad:\nhttps://example.com\n\nWhen done, press the button.",
                reply_markup=markup
            )

    elif text == "📤 Retirar" or text.lower() == "withdraw":
        if lang == "es":
            bot.send_message(message.chat.id, "📤 Para retirar, envía tu método (paypal/binance) y la cuenta, ejemplo:\n\npaypal: tuemail@ejemplo.com")
        else:
            bot.send_message(message.chat.id, "📤 To withdraw, send your method (paypal/binance) and account, e.g.:\n\npaypal: youremail@example.com")

    elif text.startswith("paypal:") or text.startswith("binance:"):
        if lang == "es":
            bot.send_message(message.chat.id, "✅ Solicitud recibida. Vamos a revisarla y te responderemos pronto (simulación).")
        else:
            bot.send_message(message.chat.id, "✅ Request received. We'll review it and reply soon (simulation).")

    elif text == "⚙️ Idioma" or text.lower() == "lang":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Español", "English")
        bot.send_message(message.chat.id, "Selecciona idioma / Select language:", reply_markup=kb)

    elif text == "Español":
        data = load_data()
        sid = str(message.from_user.id)
        if sid in data:
            data[sid]["lang"] = "es"
            save_data(data)
        bot.send_message(message.chat.id, "Idioma cambiado a Español.", reply_markup=main_keyboard("es"))

    elif text == "English":
        data = load_data()
        sid = str(message.from_user.id)
        if sid in data:
            data[sid]["lang"] = "en"
            save_data(data)
        bot.send_message(message.chat.id, "Language changed to English.", reply_markup=main_keyboard("en"))

    else:
        if lang == "es":
            bot.send_message(message.chat.id, "No te entendí. Usa los botones del teclado.", reply_markup=main_keyboard("es"))
        else:
            bot.send_message(message.chat.id, "I didn't understand. Use the keyboard buttons.", reply_markup=main_keyboard("en"))

# ----------------- CALLBACK PARA "HE VISTO" -----------------
@bot.callback_query_handler(func=lambda call: call.data == "watched_ad")
def callback_watched(call):
    user_id = call.from_user.id
    user = ensure_user(user_id, call.from_user.username)
    lang = user.get("lang", "es")
    new_bal = add_balance(user_id, CREDIT_PER_AD, reason="ad_watch")
    if lang == "es":
        bot.answer_callback_query(call.id, text=f"Has recibido ${CREDIT_PER_AD:.2f} (saldo: ${new_bal:.2f})")
        bot.send_message(call.message.chat.id, f"✅ Acreditado ${CREDIT_PER_AD:.2f}. Saldo actual: ${new_bal:.2f}", reply_markup=main_keyboard(lang))
    else:
        bot.answer_callback_query(call.id, text=f"You received ${CREDIT_PER_AD:.2f} (balance: ${new_bal:.2f})")
        bot.send_message(call.message.chat.id, f"✅ Credited ${CREDIT_PER_AD:.2f}. Current balance: ${new_bal:.2f}", reply_markup=main_keyboard(lang))

# ----------------- INICIAR BOT -----------------
print("Bot corriendo... presiona Ctrl+C para detener.")
bot.infinity_polling()
