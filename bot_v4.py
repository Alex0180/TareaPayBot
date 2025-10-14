# bot_v4.py
import telebot
from telebot import types
import os, json, time
import random

# ---------- CONFIG ----------
TOKEN = "8218883930:AAHv4Hgenj2zfC9rs88ACjjxrCfAqoSWbn0"
DATA_FILE = "users.json"
START_BALANCE = 0.0
CREDIT_PER_AD = 0.05
DAILY_BONUS = 0.10
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
            "ads_seen": [],
            "last_daily": 0
        }
        save_data(data)
    else:
        # 🔹 Corregir usuarios antiguos
        if "ads_seen" not in data[sid]:
            data[sid]["ads_seen"] = []
        if "last_daily" not in data[sid]:
            data[sid]["last_daily"] = 0
        save_data(data)
    return data[sid]

def add_balance(user_id, amount, reason="reward"):
    data = load_data()
    sid = str(user_id)
    ensure_user(user_id)
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
    ensure_user(user_id)
    if "ads_seen" not in data[sid]:
        data[sid]["ads_seen"] = []
    data[sid]["ads_seen"].append({
        "url": ad_url,
        "at": int(time.time())
    })
    save_data(data)

def give_daily_bonus(user_id):
    user = ensure_user(user_id)
    now = int(time.time())
    if now - user.get("last_daily", 0) >= 86400:  # 24h
        user["last_daily"] = now
        add_balance(user_id, DAILY_BONUS, reason="daily_bonus")
        save_data(load_data())
        return DAILY_BONUS
    return 0.0

# ----------------- TECLADOS -----------------
def main_keyboard(lang="es"):
    if lang == "en":
        keys = ["💸 Earn", "📤 Withdraw", "📊 Balance", "🏆 Ranking", "🎁 Daily Bonus", "⚙️ Lang"]
    else:
        keys = ["💸 Ver anuncio", "📤 Retirar", "📊 Saldo", "🏆 Ranking", "🎁 Bono Diario", "⚙️ Idioma"]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for k in keys:
        markup.add(types.KeyboardButton(k))
    return markup

def withdraw_keyboard(lang="es"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if lang=="es":
        markup.add("PayPal", "Binance")
    else:
        markup.add("PayPal", "Binance")
    return markup

# ----------------- START -----------------
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    user = ensure_user(message.from_user.id, message.from_user.username)
    lang = user.get("lang", "es")
    text = "👋 Bienvenido a TareaPay Bot!\n\n" if lang=="es" else "👋 Welcome to TareaPay Bot!\n\n"
    if lang == "es":
        text += "Gana viendo anuncios, completando tareas y recibe bonos diarios. Usa el teclado para empezar."
    else:
        text += "Earn by watching ads, completing tasks, and claim daily bonuses. Use the keyboard to start."
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard(lang))

# ----------------- MENÚ PRINCIPAL -----------------
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text.strip()
    user = ensure_user(message.from_user.id, message.from_user.username)
    lang = user.get("lang", "es")

    if text == "📊 Saldo" or text.lower() == "balance":
        bal = user.get("balance", 0.0)
        msg = f"💰 Tu saldo: ${bal:.2f}" if lang=="es" else f"💰 Your balance: ${bal:.2f}"
        bot.send_message(message.chat.id, msg)

    elif text == "💸 Ver anuncio" or text.lower() == "earn":
        unseen_ads = [ad for ad in ADS_LIST if ad["url"] not in [a.get("url") for a in user.get("ads_seen", [])]]
        if not unseen_ads:
            msg = "✅ Ya viste todos los anuncios por hoy." if lang=="es" else "✅ You have seen all ads for today."
            bot.send_message(message.chat.id, msg)
            return
        ad = random.choice(unseen_ads)
        markup = types.InlineKeyboardMarkup()
        btn_text = "He visto" if lang=="es" else "I watched"
        markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"watched_ad|{ad['url']}"))
        ad_text = ad["title_es"] if lang=="es" else ad["title_en"]
        bot.send_message(message.chat.id, f"👉 {ad_text}\n{ad['url']}\n\nCuando termines, pulsa el botón.", reply_markup=markup)

    elif text == "🏆 Ranking":
        data = load_data()
        ranking = sorted(data.items(), key=lambda x: x[1].get("balance",0), reverse=True)[:10]
        msg = "🏆 Ranking de usuarios:\n" if lang=="es" else "🏆 User ranking:\n"
        for i, (uid, u) in enumerate(ranking, 1):
            name = u.get("username") or str(uid)
            msg += f"{i}. {name} - ${u.get('balance',0):.2f}\n"
        bot.send_message(message.chat.id, msg)

    elif text == "🎁 Bono Diario" or text.lower() == "daily bonus":
        bonus = give_daily_bonus(message.from_user.id)
        if bonus > 0:
            msg = f"🎁 Has recibido tu bono diario de ${bonus:.2f}!" if lang=="es" else f"🎁 You received your daily bonus of ${bonus:.2f}!"
        else:
            msg = "❌ Ya reclamaste tu bono diario. Vuelve mañana." if lang=="es" else "❌ You already claimed your daily bonus. Come back tomorrow."
        bot.send_message(message.chat.id, msg)

    elif text == "📤 Retirar" or text.lower() == "withdraw":
        bot.send_message(message.chat.id, "Selecciona método de retiro:" if lang=="es" else "Select withdraw method:", reply_markup=withdraw_keyboard(lang))

    elif text.lower() in ["paypal","binance"]:
        bot.send_message(message.chat.id, f"✅ Retiro solicitado vía {text}. (Simulación)" if lang=="es" else f"✅ Withdraw requested via {text}. (Simulation)")

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
        msg = "No te entendí. Usa los botones del teclado." if lang=="es" else "I didn't understand. Use the keyboard buttons."
        bot.send_message(message.chat.id, msg, reply_markup=main_keyboard(lang))

# ----------------- CALLBACK PARA "HE VISTO" -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("watched_ad"))
def callback_watched(call):
    user_id = call.from_user.id
    user = ensure_user(user_id, call.from_user.username)
    lang = user.get("lang", "es")

    _, ad_url = call.data.split("|")
    record_ad_seen(user_id, ad_url)
    new_bal = add_balance(user_id, CREDIT_PER_AD, reason="ad_watch")

    if lang=="es":
        bot.answer_callback_query(call.id, text=f"Has recibido ${CREDIT_PER_AD:.2f} (saldo: ${new_bal:.2f})")
        bot.send_message(call.message.chat.id, f"✅ Acreditado ${CREDIT_PER_AD:.2f}. Saldo actual: ${new_bal:.2f}", reply_markup=main_keyboard(lang))
    else:
        bot.answer_callback_query(call.id, text=f"You received ${CREDIT_PER_AD:.2f} (balance: ${new_bal:.2f})")
        bot.send_message(call.message.chat.id, f"✅ Credited ${CREDIT_PER_AD:.2f}. Current balance: ${new_bal:.2f}", reply_markup=main_keyboard(lang))

# ----------------- INICIAR BOT -----------------
print("Bot v4 corriendo... presiona Ctrl+C para detener.")
bot.infinity_polling()
