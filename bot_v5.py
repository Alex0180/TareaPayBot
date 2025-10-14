# bot_v5.py
import telebot
from telebot import types
import os, json, time
import random

# ---------- CONFIG ----------
TOKEN = "8218883930:AAHv4Hgenj2zfC9rs88ACjjxrCfAqoSWbn0"
DATA_FILE = "users.json"
WITHDRAW_FILE = "withdrawals.json"
START_BALANCE = 0.0
CREDIT_PER_AD = 0.05
DAILY_BONUS = 0.10
MIN_WITHDRAW = 2.00
REF_PERCENT = 0.10  # 10% para referidos
ADMIN_IDS = [1523794576]  # <- Tus IDs de admin aquí
# ----------------------------

bot = telebot.TeleBot(TOKEN)
BOT_USERNAME = bot.get_me().username if bot.get_me() else "TareaPayBot"

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
            "referred_by": None  # guardamos quien lo refirió (user_id string)
        }
        changed = True
    else:
        if "ads_seen" not in data[sid]:
            data[sid]["ads_seen"] = []
            changed = True
        if "last_daily" not in data[sid]:
            data[sid]["last_daily"] = 0
            changed = True
        if "referred_by" not in data[sid]:
            data[sid]["referred_by"] = None
            changed = True
    if changed:
        save_data(DATA_FILE, data)
    return data[sid]

def add_balance(user_id, amount, reason="reward"):
    data = load_data(DATA_FILE)
    sid = str(user_id)
    ensure_user(user_id)
    data[sid]["balance"] = round(data[sid].get("balance", 0.0) + amount, 8)
    data[sid]["history"].append({
        "at": int(time.time()),
        "amount": amount,
        "reason": reason
    })
    save_data(DATA_FILE, data)

    # Pago de comisión al referidor si aplica
    ref = data[sid].get("referred_by")
    if ref and amount > 0:
        ref_sid = str(ref)
        if ref_sid in data:
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

    return data[sid]["balance"]

def record_ad_seen(user_id, ad_url):
    data = load_data(DATA_FILE)
    sid = str(user_id)
    ensure_user(user_id)
    if "ads_seen" not in data[sid]:
        data[sid]["ads_seen"] = []
    data[sid]["ads_seen"].append({"url": ad_url, "at": int(time.time())})
    save_data(DATA_FILE, data)

def give_daily_bonus(user_id):
    user = ensure_user(user_id)
    now = int(time.time())
    if now - user.get("last_daily", 0) >= 86400:
        user["last_daily"] = now
        add_balance(user_id, DAILY_BONUS, reason="daily_bonus")
        data = load_data(DATA_FILE)
        data[str(user_id)] = user
        save_data(DATA_FILE, data)
        return DAILY_BONUS
    return 0.0

# ---------- TECLADOS ----------
def main_keyboard(lang="es"):
    if lang=="en":
        keys = ["💸 Ganar", "📤 Retirar", "📊 Saldo", "🎮 Juegos", "🎬 Videos", "🧾 Ofertas", "🔗 Referidos", "⚙️ Lang"]
    else:
        keys = ["💸 Ganar", "📤 Retirar", "📊 Saldo", "🎮 Juegos", "🎬 Videos", "🧾 Ofertas", "🔗 Referidos", "⚙️ Idioma"]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for k in keys: markup.add(types.KeyboardButton(k))
    return markup

def withdraw_keyboard(lang="es"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("PayPal", "Binance", "Payoneer", "WesternUnion")
    return markup

def earn_keyboard(lang="es"):
    markup = types.InlineKeyboardMarkup()
    # Los enlaces son placeholders; en la fase siguiente los reemplazamos por offerwalls reales con user param
    markup.add(types.InlineKeyboardButton("🎬 Ver Videos", callback_data="earn_videos"))
    markup.add(types.InlineKeyboardButton("🧾 Ofertas", callback_data="earn_offers"))
    markup.add(types.InlineKeyboardButton("🎮 Juegos", callback_data="earn_games"))
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
        # si vino con /start <ref>
        try:
            ref = parts[1]
        except:
            ref = None

    user = ensure_user(message.from_user.id, message.from_user.username)
    # Si hay param ref y es distinto, guardarlo
    if ref:
        try:
            if str(ref) != str(message.from_user.id):
                data = load_data(DATA_FILE)
                sid = str(message.from_user.id)
                if data.get(sid, {}).get("referred_by") is None:
                    # solo setear si no tiene referidor ya
                    data.setdefault(sid, ensure_user(message.from_user.id, message.from_user.username))
                    data[sid]["referred_by"] = str(ref)
                    save_data(DATA_FILE, data)
        except Exception:
            pass

    lang = user.get("lang","es")
    text = "👋 Bienvenido a TareaPay Bot!\n\n" if lang=="es" else "👋 Welcome to TareaPay Bot!\n\n"
    if lang=="es":
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
    user_id = message.from_user.id

    # ✅ Saldo
    if text == "📊 Saldo" or text.lower()=="balance":
        bal = user.get("balance",0.0)
        msg = f"💰 Tu saldo: ${bal:.2f}" if lang=="es" else f"💰 Your balance: ${bal:.2f}"
        bot.send_message(message.chat.id, msg)
        return

    # 💸 Ganar -> mostramos opciones (videos, ofertas, juegos)
    elif text == "💸 Ganar" or text.lower()=="earn":
        msg = "Elige cómo ganar:" if lang=="es" else "Choose how to earn:"
        bot.send_message(message.chat.id, msg, reply_markup=earn_keyboard(lang))
        return

    # 🎬 Videos
    elif text == "🎬 Videos" or text.lower()=="videos":
        # Enviar link con parametro user para que podamos trackear
        link = f"https://example-offers.com/videos?user={user_id}"
        bot.send_message(message.chat.id, f"🎬 Mira videos aquí: {link}\n(En la próxima fase lo conectamos con Lootably/CPX/partner).")
        return

    # 🧾 Ofertas
    elif text == "🧾 Ofertas" or text.lower()=="offers":
        link = f"https://example-offers.com/offers?user={user_id}"
        bot.send_message(message.chat.id, f"🧾 Completa ofertas aquí: {link}\n(Sin encuestas; apps y juegos).")
        return

    # 🎮 Juegos
    elif text == "🎮 Juegos" or text.lower()=="games":
        link = f"https://example-offers.com/games?user={user_id}"
        bot.send_message(message.chat.id, f"🎮 Juega y gana: {link}\n(Juegos que pagan).")
        return

    # 🔗 Referidos
    elif text == "🔗 Referidos" or text.lower()=="referidos":
        bot_username = BOT_USERNAME or "TareaPayBot"
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        msg = f"Comparte este enlace con tus amigos y gana {int(REF_PERCENT*100)}% de sus ganancias:\n{referral_link}"
        bot.send_message(message.chat.id, msg)
        return

    # 📤 Retirar
    elif text == "📤 Retirar" or text.lower()=="withdraw":
        bal = user.get("balance", 0.0)
        if bal < MIN_WITHDRAW:
            bot.send_message(message.chat.id, f"❌ El monto mínimo de retiro es ${MIN_WITHDRAW:.2f}. Tu saldo actual es ${bal:.2f}.", reply_markup=main_keyboard(lang))
            return
        msg = bot.send_message(message.chat.id, "Selecciona método de retiro:" if lang=="es" else "Select withdraw method:", reply_markup=withdraw_keyboard(lang))
        bot.register_next_step_handler(msg, retiro_step)
        return

    # 🎁 Bono diario
    elif text == "🎁 Bono Diario" or text.lower()=="daily bonus":
        bonus = give_daily_bonus(user_id)
        if bonus>0:
            msg = f"🎁 Has recibido tu bono diario de ${bonus:.2f}!" if lang=="es" else f"🎁 You received your daily bonus of ${bonus:.2f}!"
        else:
            msg = "❌ Ya reclamaste tu bono diario. Vuelve mañana." if lang=="es" else "❌ You already claimed your daily bonus. Come back tomorrow."
        bot.send_message(message.chat.id,msg)
        return

    # ⚙️ Idioma
    elif text == "⚙️ Idioma" or text.lower()=="lang":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Español","English")
        bot.send_message(message.chat.id,"Selecciona idioma / Select language:",reply_markup=kb)
        return

    elif text=="Español":
        user["lang"]="es"
        data = load_data(DATA_FILE)
        data[str(user_id)] = user
        save_data(DATA_FILE, data)
        bot.send_message(message.chat.id,"Idioma cambiado a Español.", reply_markup=main_keyboard("es"))
        return

    elif text=="English":
        user["lang"]="en"
        data = load_data(DATA_FILE)
        data[str(user_id)] = user
        save_data(DATA_FILE, data)
        bot.send_message(message.chat.id,"Language changed to English.", reply_markup=main_keyboard("en"))
        return

# ---------- RETIRO PASO A PASO ----------
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
        bot.send_message(message.chat.id, "Cuenta inválida. Volviendo al menú.", reply_markup=main_keyboard(user.get("lang","es")))
        return

    # Revalidar mínimo
    if user.get("balance", 0.0) < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ No alcanzas el mínimo de retiro ${MIN_WITHDRAW:.2f}. Tu saldo: ${user.get('balance',0.0):.2f}", reply_markup=main_keyboard(user.get("lang","es")))
        return

    # Cargar y actualizar withdrawals
    withdraws = load_data(WITHDRAW_FILE)
    sid = str(user_id)
    withdraws[sid] = {
        "user_id": user_id,
        "username": user.get("username"),
        "method": metodo,
        "account": cuenta,
        "balance": user.get("balance",0.0),
        "status": "pendiente",
        "timestamp": int(time.time())
    }

    # Reset saldo a 0 y guardar cambios correctamente
    user["balance"] = 0.0
    data = load_data(DATA_FILE)
    data[str(user_id)] = user
    save_data(DATA_FILE, data)
    save_data(WITHDRAW_FILE, withdraws)

    # Notificar al usuario y regresar al menú principal
    bot.send_message(message.chat.id, f"✅ Solicitud de retiro guardada vía {metodo}. Espera aprobación del admin.",
                     reply_markup=main_keyboard(user.get("lang","es")))

    # Notificar admin
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin,
                             f"Nuevo retiro pendiente:\nUsuario: {user.get('username')}\nMétodo: {metodo}\nCuenta: {cuenta}\nMonto: ${withdraws[sid]['balance']:.2f}",
                             reply_markup=admin_inline_keyboard(sid))
        except Exception:
            pass

# ---------- CALLBACKS ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("watched_ad"))
def callback_watched(call):
    user_id = call.from_user.id
    user = ensure_user(user_id, call.from_user.username)
    lang = user.get("lang","es")
    _, ad_url = call.data.split("|")
    record_ad_seen(user_id, ad_url)
    new_bal = add_balance(user_id,CREDIT_PER_AD,reason="ad_watch")
    msg_es = f"✅ Acreditado ${CREDIT_PER_AD:.2f}. Saldo actual: ${new_bal:.2f}"
    msg_en = f"✅ Credited ${CREDIT_PER_AD:.2f}. Current balance: ${new_bal:.2f}"
    bot.answer_callback_query(call.id,text=msg_es if lang=="es" else msg_en)
    bot.send_message(call.message.chat.id,msg_es if lang=="es" else msg_en,reply_markup=main_keyboard(lang))

@bot.callback_query_handler(func=lambda call: call.data.startswith(("aprobar_","rechazar_","earn_")))
def callback_admin(call):
    # admin approve/reject
    if call.data.startswith(("aprobar_","rechazar_")):
        action, user_id = call.data.split("_")
        user_data = load_data(WITHDRAW_FILE)
        if user_id not in user_data:
            bot.answer_callback_query(call.id,"Usuario no encontrado ❌")
            return

        if action=="aprobar":
            user_data[user_id]["status"]="aprobado"
            try:
                bot.send_message(int(user_id), f"✅ Tu retiro vía {user_data[user_id]['method']} ha sido aprobado.")
            except Exception:
                pass
            bot.answer_callback_query(call.id,"Retiro aprobado ✅")
        elif action=="rechazar":
            user_data[user_id]["status"]="rechazado"
            try:
                bot.send_message(int(user_id), f"❌ Tu retiro vía {user_data[user_id]['method']} ha sido rechazado.")
            except Exception:
                pass
            bot.answer_callback_query(call.id,"Retiro rechazado ❌")

        save_data(WITHDRAW_FILE,user_data)
        return

    # earn callbacks: mostrar links rápidos
    if call.data == "earn_videos":
        uid = call.from_user.id
        link = f"https://example-offers.com/videos?user={uid}"
        bot.answer_callback_query(call.id, "Abriendo videos...")
        bot.send_message(call.from_user.id, f"🎬 Mira videos aquí: {link}")
        return
    if call.data == "earn_offers":
        uid = call.from_user.id
        link = f"https://example-offers.com/offers?user={uid}"
        bot.answer_callback_query(call.id, "Abriendo ofertas...")
        bot.send_message(call.from_user.id, f"🧾 Ofertas: {link}")
        return
    if call.data == "earn_games":
        uid = call.from_user.id
        link = f"https://example-offers.com/games?user={uid}"
        bot.answer_callback_query(call.id, "Abriendo juegos...")
        bot.send_message(call.from_user.id, f"🎮 Juegos: {link}")
        return

# ---------- ADMIN: listar retiros pendientes ----------
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Acceso denegado.")
        return
    withdraws = load_data(WITHDRAW_FILE)
    pendings = {k:v for k,v in withdraws.items() if v.get("status")=="pendiente"}
    if not pendings:
        bot.send_message(message.chat.id, "No hay retiros pendientes.")
        return
    for sid, info in pendings.items():
        txt = f"Usuario: {info.get('username')}\nMétodo: {info.get('method')}\nCuenta: {info.get('account')}\nMonto: ${info.get('balance',0.0):.2f}"
        try:
            bot.send_message(message.chat.id, txt, reply_markup=admin_inline_keyboard(sid))
        except Exception:
            pass

# ---------- INICIAR BOT ----------
print("Bot v5 corriendo... presiona Ctrl+C para detener.")
bot.infinity_polling()
