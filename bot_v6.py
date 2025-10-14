# bot_v6.py
import telebot
from telebot import types
import os, json, time
import random

# ---------------- CONFIG ----------------
TOKEN = "8218883930:AAHv4Hgenj2zfC9rs88ACjjxrCfAqoSWbn0"  # cámbialo si hace falta
DATA_FILE = "users.json"
WITHDRAW_FILE = "withdrawals.json"
START_BALANCE = 0.0
CREDIT_PER_AD = 0.05
DAILY_BONUS = 0.10
MIN_WITHDRAW = 2.00
REF_PERCENT = 0.10  # 10% para referidos
ADMIN_IDS = [1523794576]  # Pon aquí tus IDs de admin (enteros)
MAX_DAILY_EARN = 5.00  # Límite diario por usuario (anti-fraude básico)
# ----------------------------------------

bot = telebot.TeleBot(TOKEN)
try:
    BOT_USERNAME = bot.get_me().username
except Exception:
    BOT_USERNAME = "TareaPayBot"

# ---------- UTILIDADES ----------
def load_data(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_user(user_id, username=None, lang="es"):
    data = load_data(DATA_FILE)
    sid = str(user_id)
    changed = False
    if sid not in data:
        data[sid] = {
            "username": username or "",
            "balance": START_BALANCE,
            "created_at": int(time.time()),
            "lang": lang,
            "history": [],
            "ads_seen": [],
            "last_daily": 0,
            "referred_by": None,
            "daily_earned": 0.0,   # total ganado hoy (reset diario)
            "last_earn_reset": 0,  # timestamp when daily_earned was reset
            "verified": False,     # verification flag (contact or username)
            "phone": None
        }
        changed = True
    else:
        u = data[sid]
        if "ads_seen" not in u:
            u["ads_seen"] = []
            changed = True
        if "daily_earned" not in u:
            u["daily_earned"] = 0.0
            changed = True
        if "last_earn_reset" not in u:
            u["last_earn_reset"] = 0
            changed = True
        if "verified" not in u:
            u["verified"] = False
            changed = True
        if "phone" not in u:
            u["phone"] = None
            changed = True
    if changed:
        save_data(DATA_FILE, data)
    return data[sid]

def reset_daily_earn_if_needed(user):
    now = int(time.time())
    last = user.get("last_earn_reset", 0)
    # reset if different day (86400 seconds)
    if now - last >= 86400:
        user["daily_earned"] = 0.0
        user["last_earn_reset"] = now

def add_balance(user_id, amount, reason="reward"):
    data = load_data(DATA_FILE)
    sid = str(user_id)
    ensure_user(user_id)
    user = data[sid]

    # reset daily if needed
    reset_daily_earn_if_needed(user)

    # anti-fraude: cap daily earnings
    potential_daily = round(user.get("daily_earned", 0.0) + amount, 8)
    if potential_daily > MAX_DAILY_EARN:
        # can't add beyond daily cap
        allowed = round(max(0.0, MAX_DAILY_EARN - user.get("daily_earned", 0.0)), 8)
        if allowed <= 0:
            return None  # denied by daily cap
        amount = allowed

    user["balance"] = round(user.get("balance", 0.0) + amount, 8)
    user["history"].append({
        "at": int(time.time()),
        "amount": amount,
        "reason": reason
    })
    user["daily_earned"] = round(user.get("daily_earned", 0.0) + amount, 8)
    data[sid] = user
    save_data(DATA_FILE, data)

    # pay referrer commission if applicable
    ref = user.get("referred_by")
    if ref:
        ref_sid = str(ref)
        if ref_sid in data and amount > 0:
            ref_amount = round(amount * REF_PERCENT, 8)
            data[ref_sid]["balance"] = round(data[ref_sid].get("balance", 0.0) + ref_amount, 8)
            data[ref_sid]["history"].append({
                "at": int(time.time()),
                "amount": ref_amount,
                "reason": f"commission_from_{sid}"
            })
            save_data(DATA_FILE, data)
            try:
                bot.send_message(int(ref_sid), f"🎉 Has recibido ${ref_amount:.2f} como comisión por referido.")
            except Exception:
                pass

    return user["balance"]

def record_ad_seen(user_id, ad_url):
    data = load_data(DATA_FILE)
    sid = str(user_id)
    ensure_user(user_id)
    if "ads_seen" not in data[sid]:
        data[sid]["ads_seen"] = []
    data[sid]["ads_seen"].append({"url": ad_url, "at": int(time.time())})
    save_data(DATA_FILE, data)

def give_daily_bonus(user_id):
    data = load_data(DATA_FILE)
    sid = str(user_id)
    ensure_user(user_id)
    user = data[sid]
    now = int(time.time())
    if now - user.get("last_daily", 0) >= 86400:
        user["last_daily"] = now
        add_balance(user_id, DAILY_BONUS, reason="daily_bonus")
        data[sid] = user
        save_data(DATA_FILE, data)
        return DAILY_BONUS
    return 0.0

# ---------- TECLADOS ----------
def main_keyboard(lang="es"):
    if lang == "en":
        keys = ["💸 Earn", "📤 Withdraw", "📊 Balance", "🎮 Games", "🎬 Videos", "🧾 Offers", "🔗 Refs", "👤 Profile", "⚙️ Lang"]
    else:
        keys = ["💸 Formas de ganar", "📤 Retirar", "📊 Saldo", "🎮 Juegos", "🎬 Videos", "🧾 Ofertas", "🔗 Referidos", "👤 Mi perfil", "⚙️ Idioma"]
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

# ---------- START ----------
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    parts = message.text.split()
    ref = None
    if len(parts) > 1:
        ref = parts[1]

    user = ensure_user(message.from_user.id, message.from_user.username)
    # register referral if provided
    if ref:
        try:
            if str(ref) != str(message.from_user.id):
                data = load_data(DATA_FILE)
                sid = str(message.from_user.id)
                if data.get(sid, {}).get("referred_by") is None:
                    data.setdefault(sid, ensure_user(message.from_user.id, message.from_user.username))
                    data[sid]["referred_by"] = str(ref)
                    save_data(DATA_FILE, data)
        except Exception:
            pass

    # mark verified True if user has username (light verification)
    if message.from_user.username:
        data = load_data(DATA_FILE)
        data.setdefault(str(message.from_user.id), ensure_user(message.from_user.id, message.from_user.username))
        data[str(message.from_user.id)]["verified"] = True
        save_data(DATA_FILE, data)

    lang = user.get("lang", "es")
    text = "👋 Bienvenido a TareaPay Bot!\n\n" if lang == "es" else "👋 Welcome to TareaPay Bot!\n\n"
    if lang == "es":
        text += "Gana viendo videos, jugando o completando ofertas. Bono diario disponible. Usa el teclado para empezar."
    else:
        text += "Earn by watching videos, playing games or completing offers. Daily bonus available. Use the keyboard to start."
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard(lang))

# ---------- MENÚ PRINCIPAL ----------
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text.strip()
    user = ensure_user(message.from_user.id, message.from_user.username)
    lang = user.get("lang", "es")
    uid = message.from_user.id

    # Saldo
    if text in ["📊 Saldo", "📊 Balance", "balance"]:
        bal = user.get("balance", 0.0)
        msg = f"💰 Tu saldo: ${bal:.2f}" if lang == "es" else f"💰 Your balance: ${bal:.2f}"
        bot.send_message(message.chat.id, msg, reply_markup=main_keyboard(lang))
        return

    # Formas de ganar
    if text in ["💸 Formas de ganar", "💸 Ganar", "💸 Earn", "earn"]:
        msg = "Elige cómo ganar:" if lang == "es" else "Choose how to earn:"
        bot.send_message(message.chat.id, msg, reply_markup=earn_keyboard(lang))
        return

    # Videos
    if text in ["🎬 Videos", "videos", "Videos"]:
        link = f"https://example-offers.com/videos?user={uid}"
        bot.send_message(message.chat.id, f"🎬 Mira videos aquí: {link}\n(En la siguiente fase lo conectamos con Lootably/CPX).")
        return

    # Ofertas
    if text in ["🧾 Ofertas", "ofertas", "Offers"]:
        link = f"https://example-offers.com/offers?user={uid}"
        bot.send_message(message.chat.id, f"🧾 Completa ofertas aquí: {link}\n(Sin encuestas).")
        return

    # Juegos
    if text in ["🎮 Juegos", "juegos", "Games"]:
        link = f"https://example-offers.com/games?user={uid}"
        bot.send_message(message.chat.id, f"🎮 Juega y gana: {link}\n(Juegos que pagarán).")
        return

    # Referidos
    if text in ["🔗 Referidos", "referidos", "refs"]:
        bot_username = BOT_USERNAME or "TareaPayBot"
        referral_link = f"https://t.me/{bot_username}?start={uid}"
        msg = f"Comparte este enlace y gana {int(REF_PERCENT*100)}% de las ganancias de tus referidos:\n{referral_link}"
        bot.send_message(message.chat.id, msg)
        return

    # Mi perfil
    if text in ["👤 Mi perfil", "mi perfil", "profile"]:
        data = load_data(DATA_FILE)
        u = data.get(str(uid), ensure_user(uid))
        created = time.strftime("%Y-%m-%d", time.localtime(u.get("created_at", int(time.time()))))
        profile_txt = (f"👤 Perfil\nUsuario: @{u.get('username')}\nID: {uid}\nRegistrado: {created}\n"
                       f"Saldo: ${u.get('balance',0.0):.2f}\nGanado hoy: ${u.get('daily_earned',0.0):.2f}\n"
                       f"Verificado: {'✅' if u.get('verified') else '❌'}\nReferido por: {u.get('referred_by')}")
        bot.send_message(message.chat.id, profile_txt, reply_markup=main_keyboard(lang))
        return

    # Retirar
    if text in ["📤 Retirar", "retirar", "withdraw"]:
        bal = user.get("balance", 0.0)
        if bal < MIN_WITHDRAW:
            bot.send_message(message.chat.id, f"❌ Monto mínimo de retiro: ${MIN_WITHDRAW:.2f}. Tu saldo: ${bal:.2f}", reply_markup=main_keyboard(lang))
            return
        msg = bot.send_message(message.chat.id, "Selecciona método de retiro:" if lang == "es" else "Select withdraw method:", reply_markup=withdraw_keyboard(lang))

        bot.register_next_step_handler(msg, retiro_step)
        return

    # Bono diario
    if text in ["🎁 Bono Diario", "bono diario", "daily bonus"]:
        bonus = give_daily_bonus(uid)
        if bonus > 0:
            msg = f"🎁 Has recibido tu bono diario de ${bonus:.2f}!" if lang == "es" else f"🎁 You received your daily bonus of ${bonus:.2f}!"
        else:
            msg = "❌ Ya reclamaste hoy. Vuelve mañana." if lang == "es" else "❌ Already claimed today."
        bot.send_message(message.chat.id, msg, reply_markup=main_keyboard(lang))
        return

    # Idioma
    if text in ["⚙️ Idioma", "Idioma", "lang", "⚙️ Lang"]:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Español", "English")
        bot.send_message(message.chat.id, "Selecciona idioma / Select language:", reply_markup=kb)
        return

    if text == "Español":
        user["lang"] = "es"
        data = load_data(DATA_FILE)
        data[str(uid)] = user
        save_data(DATA_FILE, data)
        bot.send_message(message.chat.id, "Idioma cambiado a Español.", reply_markup=main_keyboard("es"))
        return

    if text == "English":
        user["lang"] = "en"
        data = load_data(DATA_FILE)
        data[str(uid)] = user
        save_data(DATA_FILE, data)
        bot.send_message(message.chat.id, "Language changed to English.", reply_markup=main_keyboard("en"))
        return

    # Comando /verify para pedir contacto
    if text.startswith("/verify"):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(types.KeyboardButton("Enviar mi contacto ✅", request_contact=True))
        kb.add("Cancelar")
        bot.send_message(message.chat.id, "Comparte tu contacto para verificar tu cuenta (opcional).", reply_markup=kb)
        return

    # Fallback
    bot.send_message(message.chat.id, "No entendí. Usa el menú.", reply_markup=main_keyboard(user.get("lang", "es")))

# ---------- RETIRO ---------- 
def retiro_step(message):
    user_id = message.from_user.id
    metodo = message.text.strip()
    if metodo not in ["PayPal", "Binance", "Payoneer", "WesternUnion"]:
        bot.send_message(message.chat.id, "Método inválido. Volviendo al menú.", reply_markup=main_keyboard())
        return

    msg = bot.send_message(message.chat.id, f"Ingresa tu cuenta/correo de {metodo}:")
    bot.register_next_step_handler(msg, lambda m: guardar_retiro(m, metodo))

def guardar_retiro(message, metodo):
    user_id = message.from_user.id
    cuenta = message.text.strip()
    user = ensure_user(user_id)

    if not cuenta:
        bot.send_message(message.chat.id, "Cuenta inválida. Volviendo al menú.", reply_markup=main_keyboard(user.get("lang", "es")))
        return

    # Revalidar mínimo
    if user.get("balance", 0.0) < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ No alcanzas el mínimo ${MIN_WITHDRAW:.2f}. Tu saldo: ${user.get('balance',0.0):.2f}", reply_markup=main_keyboard(user.get("lang", "es")))
        return

    withdraws = load_data(WITHDRAW_FILE)
    sid = str(user_id)
    withdraws[sid] = {
        "user_id": user_id,
        "username": user.get("username"),
        "method": metodo,
        "account": cuenta,
        "balance": user.get("balance", 0.0),
        "status": "pendiente",
        "timestamp": int(time.time())
    }

    # reset saldo
    user["balance"] = 0.0
    data = load_data(DATA_FILE)
    data[str(user_id)] = user
    save_data(DATA_FILE, data)
    save_data(WITHDRAW_FILE, withdraws)

    bot.send_message(message.chat.id, f"✅ Solicitud de retiro guardada vía {metodo}. Espera aprobación del admin.", reply_markup=main_keyboard(user.get("lang", "es")))

    # Notify admins
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, f"Nuevo retiro pendiente:\nUsuario: {user.get('username')}\nMétodo: {metodo}\nCuenta: {cuenta}\nMonto: ${withdraws[sid]['balance']:.2f}", reply_markup=admin_inline_keyboard(sid))
        except Exception:
            pass

# ---------- CALLBACKS (earn & approve) ----------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data
    user_id = call.from_user.id
    user = ensure_user(user_id, call.from_user.username)
    lang = user.get("lang", "es")

    # Earn buttons
    if data == "earn_videos":
        # simulate opening a real offerwall page (we provide link)
        link = f"https://example-offers.com/videos?user={user_id}"
        # We also provide a button to simulate completion in testing
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Marcar como completado ✅", callback_data="complete_videos"))
        bot.answer_callback_query(call.id, "Abriendo videos...")
        bot.send_message(user_id, f"🎬 Abre y mira videos aquí:\n{link}\n\nCuando termines, pulsa el botón debajo para simular la recompensa (prueba).", reply_markup=markup)
        return

    if data == "earn_games":
        link = f"https://example-offers.com/games?user={user_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Marcar como completado ✅", callback_data="complete_games"))
        bot.answer_callback_query(call.id, "Abriendo juegos...")
        bot.send_message(user_id, f"🎮 Juega aquí:\n{link}\n\nCuando termines, pulsa el botón debajo para simular la recompensa (prueba).", reply_markup=markup)
        return

    if data == "earn_offers":
        link = f"https://example-offers.com/offers?user={user_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Marcar como completado ✅", callback_data="complete_offers"))
        bot.answer_callback_query(call.id, "Abriendo ofertas...")
        bot.send_message(user_id, f"🧾 Ofertas aquí:\n{link}\n\nCuando termines, pulsa el botón debajo para simular la recompensa (prueba).", reply_markup=markup)
        return

    # Simulate completion callbacks (for testing / local)
    if data.startswith("complete_"):
        kind = data.split("_", 1)[1]  # videos / games / offers
        # determine reward range
        if kind == "videos":
            amt = round(random.uniform(0.01, 0.10), 2)  # small per video
        elif kind == "games":
            amt = round(random.uniform(0.10, 1.50), 2)
        else:  # offers
            amt = round(random.uniform(0.20, 3.00), 2)

        # add balance with anti-fraud check
        new_bal = add_balance(user_id, amt, reason=f"{kind}_reward")
        if new_bal is None:
            # daily cap reached
            bot.answer_callback_query(call.id, "Límite diario alcanzado. No se acreditó la ganancia.")
            bot.send_message(user_id, "❌ Límite diario de ganancias alcanzado. Intenta mañana.", reply_markup=main_keyboard(lang))
            return

        # message to user
        msg = (f"✅ ¡Tarea completada!\n"
               f"💵 Ganancia recibida: ${amt:.2f}\n"
               f"💰 Tu nuevo saldo: ${new_bal:.2f}")
        bot.answer_callback_query(call.id, "Ganancia acreditada.")
        bot.send_message(user_id, msg, reply_markup=main_keyboard(lang))
        return

    # Admin approve/reject callbacks
    if data.startswith("aprobar_") or data.startswith("rechazar_"):
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Acceso denegado.")
            return
        action, sid = data.split("_", 1)
        withdraws = load_data(WITHDRAW_FILE)
        if sid not in withdraws:
            bot.answer_callback_query(call.id, "Solicitud no encontrada.")
            return
        info = withdraws[sid]
        if action == "aprobar":
            withdraws[sid]["status"] = "aprobado"
            save_data(WITHDRAW_FILE, withdraws)
            try:
                bot.send_message(int(sid), f"✅ Tu retiro vía {info.get('method')} ha sido aprobado.")
            except Exception:
                pass
            bot.answer_callback_query(call.id, "Retiro aprobado ✅")
            return
        else:
            # on reject, return balance to user
            withdraws[sid]["status"] = "rechazado"
            save_data(WITHDRAW_FILE, withdraws)
            try:
                data_users = load_data(DATA_FILE)
                data_users.setdefault(sid, ensure_user(int(sid)))
                # return the amount
                returned = info.get("balance", 0.0)
                data_users[sid]["balance"] = round(data_users[sid].get("balance", 0.0) + returned, 8)
                data_users[sid]["history"].append({
                    "at": int(time.time()),
                    "amount": returned,
                    "reason": "withdraw_rejected_return"
                })
                save_data(DATA_FILE, data_users)
                bot.send_message(int(sid), f"❌ Tu retiro ha sido rechazado. Se devolvió ${returned:.2f} a tu saldo.")
            except Exception:
                pass
            bot.answer_callback_query(call.id, "Retiro rechazado ❌")
            return

# ---------- CONTACT (verification) ----------
@bot.message_handler(content_types=["contact"])
def handle_contact(msg):
    if not msg.contact:
        return
    uid = msg.from_user.id
    data = load_data(DATA_FILE)
    sid = str(uid)
    data.setdefault(sid, ensure_user(uid, msg.from_user.username))
    data[sid]["phone"] = msg.contact.phone_number
    data[sid]["verified"] = True
    save_data(DATA_FILE, data)
    bot.send_message(uid, "✅ Gracias, tu contacto fue registrado y tu cuenta está verificada.", reply_markup=main_keyboard(data[sid].get("lang", "es")))

# ---------- ADMIN COMMANDS ----------
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Acceso denegado.")
        return
    withdraws = load_data(WITHDRAW_FILE)
    pendings = {k: v for k, v in withdraws.items() if v.get("status") == "pendiente"}
    if not pendings:
        bot.send_message(message.chat.id, "No hay retiros pendientes.")
        return
    for sid, info in pendings.items():
        txt = f"Usuario: {info.get('username')}\nID: {sid}\nMétodo: {info.get('method')}\nCuenta: {info.get('account')}\nMonto: ${info.get('balance', 0.0):.2f}"
        bot.send_message(message.chat.id, txt, reply_markup=admin_inline_keyboard(sid))

@bot.message_handler(commands=["credit"])
def admin_credit(message):
    # Usage: /credit <user_id> <amount>
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Acceso denegado.")
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "Uso: /credit <user_id> <amount>")
        return
    try:
        uid = int(parts[1])
        amt = float(parts[2])
    except:
        bot.send_message(message.chat.id, "Parámetros inválidos.")
        return
    new = add_balance(uid, amt, reason="manual_admin_credit")
    if new is None:
        bot.send_message(message.chat.id, "No se pudo acreditar (límite diario?).")
        return
    bot.send_message(message.chat.id, f"Acreditado ${amt:.2f} a {uid}. Nuevo saldo: ${new:.2f}")
    try:
        bot.send_message(uid, f"✅ Ganancia acreditada manualmente: ${amt:.2f}\n💰 Nuevo saldo: ${new:.2f}")
    except Exception:
        pass

# ---------- UTILS / START BOT ----------
print("Bot v6 corriendo... presiona Ctrl+C para detener.")
bot.infinity_polling()
