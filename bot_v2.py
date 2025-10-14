# bot_v2.py
import telebot
from telebot import types
import os, json, time
import random

# ---------- CONFIG ----------
TOKEN = "8218883930:AAHv4Hgenj2zfC9rs88ACjjxrCfAqoSWbn0"  # <- tu token
DATA_FILE = "users.json"
START_BALANCE = 0.0
CREDIT_PER_AD = 0.05   # saldo por anuncio visto
ADS_LIST = [
    {"title_es": "Mira este video divertido", "title_en": "Watch this funny video", "url": "https://example.com/ad1"},
    {"title_es": "Revisa esta oferta especial", "title_en": "Check this special offer", "url": "https://example.com/ad2"},
    {"title_es": "Prueba esta app gratis", "title_en": "Try this free app", "url": "https://example.com/ad3"}
]
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
            "history": [],
            "ads_seen": []
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

def record_ad_seen(user_id, ad_url):
    data = load_data()
    sid = str(user_id)
    if sid not in data:
        ensure_user(user_id)
        data = load_data()
    data[sid]["ads_seen"].append({
        "url": ad_url,
        "at": int(time.time())
    })
    save_data(data)

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

    # Mostrar saldo
    if text == "📊 Saldo" or text.lower() == "balance":
        bal = user.get("balance", 0.0)
        if lang == "es":
            bot.send_message(message.chat.id, f"💰 Tu saldo: ${bal:.2f}")
        else:
            bot.send_message(message.chat.id, f"💰 Your balance: ${bal:.2f}")

    # Ver anuncio
    elif text == "💸 Ver anuncio" or text.lower() == "earn":
        # Elegir anuncio aleatorio que no haya visto
        unseen_ads = [ad for ad in ADS_LIST if ad["url"] not in user.get("ads_seen", [])]
        if not unseen_ads:
            if lang == "es":
                bot.send_message(message.chat.id, "✅ Ya viste todos los anuncios disponibles por ahora. Vuelve luego.")
            else:
                bot.send_message(message.chat.id, "✅ You have seen all available ads for now. Come back later.")
            return

        ad = random.choice(unseen_ads)
        markup = types.InlineKeyboardMarkup()
        btn_text = "He visto" if lang=="es" else "I watched"
        markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"watched_ad|{ad['url']}"))

        ad_text = ad["title_es"] if lang=="es" else ad["title_en"]
        bot.send_message(message.chat.id, f"👉 {ad_text}\n{ad['url']}\n\nCuando termines, pulsa el botón.", reply_markup=markup)

    # Retiro simulado
    elif text == "📤 Retirar" or text.lower() == "withdraw":
        if lang == "es":
            bot.send_message(message.chat.id, "📤 Para retirar, envía tu método (paypal/binance) y la cuenta, ejemplo:\n\npaypal: tuemail@ejemplo.com")
        else:
            bot.send_message(message.chat.id, "📤 To withdraw, send your method (paypal/binance) and account, e.g.:\n\npaypal: youremail@example.com")

    # Guardar solicitud de retiro
    elif text.startswith("paypal:") or text.startswith("binance:"):
        if lang == "es":
            bot.send_message(message.chat.id, "✅ Solicitud recibida. Vamos a revisarla y te responderemos pronto (simulación).")
        else:
            bot.send_message(message.chat.id, "✅ Request received. We'll review it and reply soon (simulation).")
        user["history"].append({"at": int(time.time()), "withdraw": text})
        save_data(load_data())  # guardar cambios

    # Cambio de idioma
    elif text == "⚙️ Idioma" or text.lower() == "lang":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Español", "English")
        bot.send_message(message.chat.id, "Selecciona idioma / Select language:", reply_markup=kb)

    elif text == "Español":
        user["lang"] = "es"
        save_data(load_data())
        bot.send_message(message.chat.id, "Idioma cambiado a Español.", reply_markup=main_keyboard("es"))

    elif text == "English":
        user["lang"] = "en"
        save_data(load_data())
        bot.send_message(message.chat.id, "Language changed to English.", reply_markup=main_keyboard("en"))

    else:
        if lang == "es":
            bot.send_message(message.chat.id, "No te entendí. Usa los botones del teclado.", reply_markup=main_keyboard("es"))
        else:
            bot.send_message(message.chat.id, "I didn't understand. Use the keyboard buttons.", reply_markup=main_keyboard("en"))

# ----------------- CALLBACK PARA "HE VISTO" -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("watched_ad"))
def callback_watched(call):
    user_id = call.from_user.id
    user = ensure_user(user_id, call.from_user.username)
    lang = user.get("lang", "es")

    # Extraer URL del callback
    _, ad_url = call.data.split("|")

    # Registrar anuncio visto
    record_ad_seen(user_id, ad_url)

    # Acreditar saldo
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
