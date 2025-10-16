# bot_v8.py
import os, json, time, random, sqlite3
from telebot import types
import database

# ---------------- CONFIG ----------------
START_BALANCE = 0.0
CREDIT_PER_AD = 0.05
DAILY_BONUS = 0.10
MIN_WITHDRAW = 2.00
REF_PERCENT = 0.10
ADMIN_IDS = [1523794576]
MAX_DAILY_EARN = 5.00
DB_FILE = "bot_games.db"  # Para monedas de juegos
# ------------------------------------------------------------

# Bot global
BOT = None

# Helpers a la base de datos principal
ensure_user_db = database.ensure_user
get_user_db = database.get_user
save_user_db = database.save_user
save_withdraw_db = database.save_withdraw
get_withdraw_db = database.get_withdraw
get_all_pending_withdraws = database.get_all_pending_withdraws
update_withdraw_status = database.update_withdraw_status
migrate_json_to_sqlite = database.migrate_json_to_sqlite
init_db = database.init_db

# ---------------- SQLITE JUEGOS ----------------
def init_games_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        coins INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

def add_user_if_not_exists(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def add_coins(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_coins(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

# ---------------- FUNCIONES BASE ----------------
def reset_daily_earn_if_needed_db(user):
    now = int(time.time())
    last = int(user.get("last_earn_reset", 0))
    if now - last >= 86400:
        user["daily_earned"] = 0.0
        user["last_earn_reset"] = now

def add_balance_db(user_id, amount, reason="reward"):
    user = get_user_db(user_id)
    if not user:
        user = ensure_user_db(user_id)
    reset_daily_earn_if_needed_db(user)
    potential_daily = round(user.get("daily_earned", 0.0) + amount, 8)
    if potential_daily > MAX_DAILY_EARN:
        allowed = round(max(0.0, MAX_DAILY_EARN - user.get("daily_earned", 0.0)), 8)
        if allowed <= 0:
            return None
        amount = allowed
    user["balance"] = round(user.get("balance", 0.0) + amount, 8)
    hist = user.get("history", [])
    hist.append({"at": int(time.time()), "amount": amount, "reason": reason})
    user["history"] = hist
    user["daily_earned"] = round(user.get("daily_earned", 0.0) + amount, 8)
    save_user_db(user)
    # Comisión de referido
    ref = user.get("referred_by")
    if ref:
        try:
            ref_user = get_user_db(int(ref))
            if ref_user and amount > 0:
                ref_amount = round(amount * REF_PERCENT, 8)
                ref_user["balance"] = round(ref_user.get("balance", 0.0) + ref_amount, 8)
                rhist = ref_user.get("history", [])
                rhist.append({"at": int(time.time()), "amount": ref_amount, "reason": f"commission_from_{user_id}"})
                ref_user["history"] = rhist
                save_user_db(ref_user)
                try:
                    if BOT:
                        BOT.send_message(int(ref), f"🎉 Has recibido ${ref_amount:.2f} como comisión por referido.")
                except Exception:
                    pass
        except Exception:
            pass
    return user["balance"]

def give_daily_bonus_db(user_id):
    user = get_user_db(user_id) or ensure_user_db(user_id)
    now = int(time.time())
    if now - int(user.get("last_daily", 0)) >= 86400:
        user["last_daily"] = now
        add_balance_db(user_id, DAILY_BONUS, reason="daily_bonus")
        return DAILY_BONUS
    return 0.0

def record_ad_seen_db(user_id, ad_url):
    user = get_user_db(user_id) or ensure_user_db(user_id)
    ads = user.get("ads_seen", [])
    ads.append({"url": ad_url, "at": int(time.time())})
    user["ads_seen"] = ads
    save_user_db(user)

# ---------------- TECLADOS ----------------
def main_keyboard(lang="es"):
    keys = ["💸 Formas de ganar", "🎁 Bono Diario", "📤 Retirar", "📊 Saldo", "🔗 Referidos", "👤 Mi perfil", "⚙️ Idioma"] if lang=="es" else ["💸 Earn", "🎁 Daily Bonus", "📤 Withdraw", "📊 Balance", "🔗 Refs", "👤 Profile", "⚙️ Lang"]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for k in keys:
        markup.add(types.KeyboardButton(k))
    return markup

def withdraw_keyboard(lang="es"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("PayPal", "Binance", "Payoneer", "WesternUnion")
    return markup

def earn_keyboard(lang="es"):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 Videos", callback_data="earn_videos"))
    markup.add(types.InlineKeyboardButton("🎮 Juegos", callback_data="earn_games"))
    markup.add(types.InlineKeyboardButton("🧾 Ofertas", callback_data="earn_offers"))
    return markup

def admin_inline_keyboard(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Aprobar ✅", callback_data=f"aprobar_{user_id}"),
        types.InlineKeyboardButton("Rechazar ❌", callback_data=f"rechazar_{user_id}")
    )
    return markup

# ---------------- HANDLERS PRINCIPAL ----------------
def register_handlers(bot):
    global BOT
    BOT = bot
    init_games_db()  # Inicializa DB de juegos
    BOT_USERNAME = BOT.get_me().username if BOT.get_me() else "PayTareaBot"

    # ---------------- START ----------------
    @BOT.message_handler(commands=["start", "help"])
    def handle_start(message):
        parts = message.text.split()
        ref = parts[1] if len(parts) > 1 else None
        user = ensure_user_db(message.from_user.id, message.from_user.username)
        if ref and ref != str(message.from_user.id):
            existing = get_user_db(message.from_user.id)
            if existing and existing.get("referred_by") is None:
                existing["referred_by"] = str(ref)
                save_user_db(existing)
        u = get_user_db(message.from_user.id) or ensure_user_db(message.from_user.id, message.from_user.username)
        u["verified"] = True
        save_user_db(u)
        lang = u.get("lang", "es")
        text = "👋 Bienvenido a PayTareaBot!\nGana viendo videos, jugando o completando ofertas." if lang=="es" else "👋 Welcome to PayTareaBot!\nEarn by watching videos, playing games or completing offers."
        BOT.send_message(message.chat.id, text, reply_markup=main_keyboard(lang))
        add_user_if_not_exists(message.from_user.id)

    # ---------------- HANDLERS DE MENSAJES ----------------
    @BOT.message_handler(func=lambda m: True)
    def handle_text(message):
        text = (message.text or "").strip()
        user = ensure_user_db(message.from_user.id, message.from_user.username)
        lang = user.get("lang", "es")
        uid = message.from_user.id

        # ---------- MENÚ SALDO ----------
        if text in ["📊 Saldo", "📊 Balance", "balance"]:
            bal = user.get("balance", 0.0)
            coins = get_coins(uid)
            BOT.send_message(message.chat.id, f"💰 Saldo: ${bal:.2f}\n🪙 Monedas: {coins}", reply_markup=main_keyboard(lang))
            return

        # ---------- FORMAS DE GANAR ----------
        if text in ["💸 Formas de ganar", "💸 Earn"]:
            BOT.send_message(message.chat.id, "Elige cómo ganar:" if lang=="es" else "Choose how to earn:", reply_markup=earn_keyboard(lang))
            return

        # ---------- BONO DIARIO ----------
        if text in ["🎁 Bono Diario", "🎁 Daily Bonus"]:
            bonus = give_daily_bonus_db(uid)
            if bonus > 0:
                BOT.send_message(message.chat.id, f"🎁 Has recibido tu bono diario de ${bonus:.2f}!", reply_markup=main_keyboard(lang))
            else:
                BOT.send_message(message.chat.id, "⏳ Ya reclamaste tu bono diario hoy.", reply_markup=main_keyboard(lang))
            return

        # ---------- RETIRO ----------
        if text in ["📤 Retirar", "📤 Withdraw"]:
            BOT.send_message(message.chat.id, "Elige método de retiro:", reply_markup=withdraw_keyboard(lang))
            return

        # ---------- REFERIDOS ----------
        if text in ["🔗 Referidos", "🔗 Refs"]:
            ref_code = str(uid)
            BOT.send_message(message.chat.id, f"Comparte tu enlace: https://t.me/{BOT_USERNAME}?start={ref_code}", reply_markup=main_keyboard(lang))
            return

        # ---------- PERFIL ----------
        if text in ["👤 Mi perfil", "👤 Profile"]:
            bal = user.get("balance", 0.0)
            coins = get_coins(uid)
            hist = user.get("history", [])
            last_tx = hist[-1] if hist else {"amount":0.0,"reason":"N/A"}
            BOT.send_message(message.chat.id, f"👤 Usuario: {user.get('username')}\n💰 Balance: ${bal:.2f}\n🪙 Monedas: {coins}\nÚltima transacción: {last_tx['amount']} ({last_tx['reason']})", reply_markup=main_keyboard(lang))
            return

        # ---------- IDIOMA ----------
        if text in ["⚙️ Idioma", "⚙️ Lang"]:
            user["lang"] = "en" if lang=="es" else "es"
            save_user_db(user)
            BOT.send_message(message.chat.id, f"Idioma cambiado a {user['lang']}", reply_markup=main_keyboard(user['lang']))
            return

    # ---------------- CALLBACK HANDLER ----------------
    @BOT.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        uid = call.from_user.id
        add_user_if_not_exists(uid)
        data = call.data

        # Juegos
        if data == "earn_games":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Trivia 🎲", callback_data="game_trivia"))
            markup.add(types.InlineKeyboardButton("Tap-to-Earn 🖱️", callback_data="game_tap"))
            BOT.send_message(call.message.chat.id, "Elige un juego:", reply_markup=markup)

        elif data == "game_trivia":
            add_coins(uid, 5)
            BOT.answer_callback_query(call.id, "¡Ganaste 5 monedas en Trivia!")

        elif data == "game_tap":
            add_coins(uid, 3)
            BOT.answer_callback_query(call.id, "¡Ganaste 3 monedas en Tap-to-Earn!")

        # Admin aprobaciones
        if any(data.startswith(p) for p in ["aprobar_", "rechazar_"]):
            if uid not in ADMIN_IDS:
                BOT.answer_callback_query(call.id, "No tienes permisos de admin.")
                return
            target_id = int(data.split("_")[1])
            if data.startswith("aprobar_"):
                update_withdraw_status(target_id, "aprobado")
                BOT.send_message(target_id, "✅ Tu retiro ha sido aprobado.")
            else:
                update_withdraw_status(target_id, "rechazado")
                BOT.send_message(target_id, "❌ Tu retiro ha sido rechazado.")
            BOT.answer_callback_query(call.id, "Acción realizada.")

# ---------------- POSTBACK ----------------
def handle_postback(user_id, payout):
    add_user_if_not_exists(user_id)
    add_coins(user_id, int(payout))

