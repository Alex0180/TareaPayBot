from dotenv import load_dotenv
import os, time, random

from flask import Flask, request
import telebot
from telebot import types

# Carga variables de entorno
load_dotenv()
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("El token no está configurado en las variables de entorno")

# ---------------- INICIALIZAR BOT ----------------
bot = telebot.TeleBot(TOKEN)
try:
    BOT_USERNAME = bot.get_me().username
except Exception:
    BOT_USERNAME = "TareaPayBot"

# ---------------- INICIALIZAR FLASK ----------------
app = Flask(__name__)

# ---------------- IMPORTAR DB ----------------
import database
ensure_user_db = database.ensure_user
get_user_db = database.get_user
save_user_db = database.save_user
save_withdraw_db = database.save_withdraw
get_withdraw_db = database.get_withdraw
get_all_pending_withdraws = database.get_all_pending_withdraws
update_withdraw_status = database.update_withdraw_status
migrate_json_to_sqlite = database.migrate_json_to_sqlite
init_db = database.init_db

# ---------------- CONFIG ----------------
START_BALANCE = 0.0
CREDIT_PER_AD = 0.05
DAILY_BONUS = 0.10
MIN_WITHDRAW = 2.00
REF_PERCENT = 0.10
ADMIN_IDS = [1523794576]
MAX_DAILY_EARN = 5.00

# ---------------- FUNCIONES AUXILIARES ----------------
def reset_daily_earn_if_needed_db(user):
    now = int(time.time())
    last = int(user.get("last_earn_reset", 0))
    if now - last >= 86400:
        user["daily_earned"] = 0.0
        user["last_earn_reset"] = now

def add_balance_db(user_id, amount, reason="reward"):
    user = get_user_db(user_id) or ensure_user_db(user_id)
    reset_daily_earn_if_needed_db(user)
    potential_daily = round(user.get("daily_earned",0)+amount,8)
    if potential_daily > MAX_DAILY_EARN:
        allowed = round(max(0.0, MAX_DAILY_EARN - user.get("daily_earned",0)),8)
        if allowed <= 0:
            return None
        amount = allowed
    user["balance"] = round(user.get("balance",0)+amount,8)
    hist = user.get("history",[])
    hist.append({"at": int(time.time()), "amount": amount, "reason": reason})
    user["history"] = hist
    user["daily_earned"] = round(user.get("daily_earned",0)+amount,8)
    save_user_db(user)

    # Referidos
    ref = user.get("referred_by")
    if ref:
        try:
            ref_user = get_user_db(int(ref))
            if ref_user and amount>0:
                ref_amount = round(amount*REF_PERCENT,8)
                ref_user["balance"] = round(ref_user.get("balance",0)+ref_amount,8)
                rhist = ref_user.get("history",[])
                rhist.append({"at": int(time.time()), "amount": ref_amount, "reason": f"commission_from_{user_id}"})
                ref_user["history"]=rhist
                save_user_db(ref_user)
                try:
                    bot.send_message(int(ref), f"🎉 Has recibido ${ref_amount:.2f} como comisión por referido.")
                except Exception: pass
        except Exception: pass
    return user["balance"]

def give_daily_bonus_db(user_id):
    user = get_user_db(user_id) or ensure_user_db(user_id)
    now = int(time.time())
    if now - int(user.get("last_daily",0)) >= 86400:
        user["last_daily"] = now
        add_balance_db(user_id, DAILY_BONUS, reason="daily_bonus")
        return DAILY_BONUS
    return 0.0

# ---------------- TECLADOS ----------------
def main_keyboard(lang="es"):
    keys = ["💸 Formas de ganar","🎁 Bono Diario","📤 Retirar","📊 Saldo","🔗 Referidos","👤 Mi perfil","⚙️ Idioma"] if lang=="es" else ["💸 Earn","🎁 Daily Bonus","📤 Withdraw","📊 Balance","🔗 Refs","👤 Profile","⚙️ Lang"]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for k in keys: markup.add(types.KeyboardButton(k))
    return markup

def withdraw_keyboard(lang="es"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("PayPal","Binance","Payoneer","WesternUnion")
    return markup

def earn_keyboard(lang="es"):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 Videos", callback_data="earn_videos"))
    markup.add(types.InlineKeyboardButton("🎮 Juegos", callback_data="earn_games"))
    markup.add(types.InlineKeyboardButton("🧾 Ofertas", callback_data="earn_offers"))
    return markup

def admin_inline_keyboard(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Aprobar ✅", callback_data=f"aprobar_{user_id}"),
               types.InlineKeyboardButton("Rechazar ❌", callback_data=f"rechazar_{user_id}"))
    return markup

# ---------------- HANDLERS ----------------
@bot.message_handler(commands=["start","help"])
def handle_start(message):
    parts = message.text.split()
    ref = parts[1] if len(parts)>1 else None
    user = ensure_user_db(message.from_user.id, message.from_user.username)
    if ref and str(ref)!=str(message.from_user.id):
        existing = get_user_db(message.from_user.id)
        if existing and existing.get("referred_by") is None:
            existing["referred_by"]=str(ref)
            save_user_db(existing)
    if message.from_user.username:
        u = get_user_db(message.from_user.id) or ensure_user_db(message.from_user.id, message.from_user.username)
        u["verified"]=True
        save_user_db(u)
    lang = user.get("lang","es")
    text = "👋 Bienvenido a TareaPay Bot!\n\n"
    text += "Gana viendo videos, jugando o completando ofertas. Bono diario disponible. Usa el teclado para empezar." if lang=="es" else "Earn by watching videos, playing games or completing offers. Daily bonus available. Use the keyboard to start."
    bot.send_message(message.chat.id,text,reply_markup=main_keyboard(lang))

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = (message.text or "").strip()
    user = ensure_user_db(message.from_user.id, message.from_user.username)
    lang = user.get("lang","es")
    uid = message.from_user.id

    if text in ["📊 Saldo","📊 Balance","balance"]:
        bal = user.get("balance",0.0)
        bot.send_message(message.chat.id,f"💰 Tu saldo: ${bal:.2f}",reply_markup=main_keyboard(lang))
        return

    if text in ["💸 Formas de ganar","💸 Ganar","💸 Earn","earn"]:
        bot.send_message(message.chat.id,"Elige cómo ganar:" if lang=="es" else "Choose how to earn:",reply_markup=earn_keyboard(lang))
        return

    if text in ["🎬 Videos","videos","Videos"]:
        link=f"https://example-offers.com/videos?user={uid}"
        bot.send_message(message.chat.id,f"🎬 Mira videos aquí: {link}\n(En la siguiente fase lo conectamos con Lootably/CPX).")
        return

    if text in ["🧾 Ofertas","ofertas","Offers"]:
        link=f"https://example-offers.com/offers?user={uid}"
        bot.send_message(message.chat.id,f"🧾 Completa ofertas aquí: {link}\n(Sin encuestas).")
        return

    if text in ["🎮 Juegos","juegos","Games"]:
        link=f"https://example-offers.com/games?user={uid}"
        bot.send_message(message.chat.id,f"🎮 Juega y gana: {link}\n(Juegos que pagarán).")
        return

    if text in ["🔗 Referidos","referidos","refs"]:
        referral_link=f"https://t.me/{BOT_USERNAME}?start={uid}"
        bot.send_message(message.chat.id,f"Comparte este enlace y gana {int(REF_PERCENT*100)}% de las ganancias de tus referidos:\n{referral_link}")
        return

    if text in ["👤 Mi perfil","mi perfil","profile"]:
        u = get_user_db(uid) or ensure_user_db(uid)
        created=time.strftime("%Y-%m-%d", time.localtime(u.get("created_at",int(time.time()))))
        profile_txt=(f"👤 Perfil\nUsuario: @{u.get('username')}\nID: {uid}\nRegistrado: {created}\nSaldo: ${u.get('balance',0.0):.2f}\nGanado hoy: ${u.get('daily_earned',0.0):.2f}\nVerificado: {'✅' if u.get('verified') else '❌'}\nReferido por: {u.get('referred_by')}")
        bot.send_message(message.chat.id,profile_txt,reply_markup=main_keyboard(lang))
        return

    if text in ["📤 Retirar","retirar","withdraw"]:
        bal=user.get("balance",0.0)
        if bal<MIN_WITHDRAW:
            bot.send_message(message.chat.id,f"❌ Monto mínimo de retiro: ${MIN_WITHDRAW:.2f}. Tu saldo: ${bal:.2f}",reply_markup=main_keyboard(lang))
            return
        msg=bot.send_message(message.chat.id,"Selecciona método de retiro:" if lang=="es" else "Select withdraw method:",reply_markup=withdraw_keyboard(lang))
        bot.register_next_step_handler(msg,retiro_step)
        return

    if text in ["🎁 Bono Diario","bono diario","daily bonus","🎁 Daily Bonus"]:
        bonus=give_daily_bonus_db(uid)
        if bonus>0:
            bot.send_message(message.chat.id,f"🎁 Has recibido tu bono diario de ${bonus:.2f}!",reply_markup=main_keyboard(lang))
        else:
            bot.send_message(message.chat.id,"❌ Ya reclamaste hoy. Vuelve mañana.",reply_markup=main_keyboard(lang))
        return

    if text in ["⚙️ Idioma","Idioma","lang","⚙️ Lang"]:
        kb=types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Español","English")
        bot.send_message(message.chat.id,"Selecciona idioma / Select language:",reply_markup=kb)
        return

    if text=="Español":
        user["lang"]="es"
        save_user_db(user)
        bot.send_message(message.chat.id,"Idioma cambiado a Español.",reply_markup=main_keyboard("es"))
        return

    if text=="English":
        user["lang"]="en"
        save_user_db(user)
        bot.send_message(message.chat.id,"Language changed to English.",reply_markup=main_keyboard("en"))
        return

    if text.startswith("/verify"):
        kb=types.ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True)
        kb.add(types.KeyboardButton("Enviar mi contacto ✅",request_contact=True))
        kb.add("Cancelar")
        bot.send_message(message.chat.id,"Comparte tu contacto para verificar tu cuenta (opcional).",reply_markup=kb)
        return

    bot.send_message(message.chat.id,"No entendí. Usa el menú.",reply_markup=main_keyboard(user.get("lang","es")))

def retiro_step(message):
    user_id=message.from_user.id
    metodo=(message.text or "").strip()
    if metodo not in ["PayPal","Binance","Payoneer","WesternUnion"]:
        bot.send_message(message.chat.id,"Método inválido. Volviendo al menú.",reply_markup=main_keyboard())
        return
    msg=bot.send_message(message.chat.id,f"Ingresa tu cuenta/correo de {metodo}:")
    bot.register_next_step_handler(msg,lambda m: guardar_retiro(m,metodo))

def guardar_retiro(message,metodo):
    user_id=message.from_user.id
    cuenta=(message.text or "").strip()
    user=get_user_db(user_id) or ensure_user_db(user_id)
    if not cuenta:
        bot.send_message(message.chat.id,"Cuenta inválida. Volviendo al menú.",reply_markup=main_keyboard(user.get("lang","es")))
        return
    if user.get("balance",0.0)<MIN_WITHDRAW:
        bot.send_message(message.chat.id,f"❌ No alcanzas el mínimo ${MIN_WITHDRAW:.2f}. Tu saldo: ${user.get('balance',0.0):.2f}",reply_markup=main_keyboard(user.get("lang","es")))
        return
    withdraw_obj={"user_id":user_id,"username":user.get("username"),"method":metodo,"account":cuenta,"balance":user.get("balance",0.0),"status":"pendiente","timestamp":int(time.time())}
    user["balance"]=0.0
    user_hist=user.get("history",[])
    user_hist.append({"at":int(time.time()),"amount":-withdraw_obj["balance"],"reason":"withdraw_request"})
    user["history"]=user_hist
    save_user_db(user)
    save_withdraw_db(withdraw_obj)
    bot.send_message(message.chat.id,f"✅ Solicitud de retiro guardada vía {metodo}. Espera aprobación del admin.",reply_markup=main_keyboard(user.get("lang","es")))
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin,f"Nuevo retiro pendiente:\nUsuario: {user.get('username')}\nID: {user_id}\nMétodo: {metodo}\nCuenta: {cuenta}\nMonto: ${withdraw_obj['balance']:.2f}",reply_markup=admin_inline_keyboard(user_id))
        except Exception: pass

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data=call.data
    user_id=call.from_user.id
    user=ensure_user_db(user_id,call.from_user.username)
    lang=user.get("lang","es")

    if data=="earn_videos":
        link=f"https://example-offers.com/videos?user={user_id}"
        markup=types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Marcar como completado ✅",callback_data="complete_videos"))
        bot.answer_callback_query(call.id,"Abriendo videos...")
        bot.send_message(user_id,f"🎬 Abre y mira videos aquí:\n{link}\n\nCuando termines, pulsa el botón debajo para simular la recompensa (prueba).",reply_markup=markup)
        return

    if data=="earn_games":
        link=f"https://example-offers.com/games?user={user_id}"
        markup=types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Marcar como completado ✅",callback_data="complete_games"))
        bot.answer_callback_query(call.id,"Abriendo juegos...")
        bot.send_message(user_id,f"🎮 Juega aquí:\n{link}\n\nCuando termines, pulsa el botón debajo para simular la recompensa (prueba).",reply_markup=markup)
        return

    if data=="earn_offers":
        link=f"https://example-offers.com/offers?user={user_id}"
        markup=types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Marcar como completado ✅",callback_data="complete_offers"))
        bot.answer_callback_query(call.id,"Abriendo ofertas...")
        bot.send_message(user_id,f"🧾 Ofertas aquí:\n{link}\n\nCuando termines, pulsa el botón debajo para simular la recompensa (prueba).",reply_markup=markup)
        return

    if data.startswith("complete_"):
        kind=data.split("_",1)[1]
        if kind=="videos": amt=round(random.uniform(0.01,0.10),2)
        elif kind=="games": amt=round(random.uniform(0.10,1.50),2)
        else: amt=round(random.uniform(0.20,3.00),2)
        new_bal=add_balance_db(user_id,amt,reason=f"{kind}_reward")
        if new_bal is None:
            bot.answer_callback_query(call.id,"Límite diario alcanzado. No se acreditó la ganancia.")
            bot.send_message(user_id,"❌ Límite diario de ganancias alcanzado. Intenta mañana.",reply_markup=main_keyboard(lang))
            return
        bot.answer_callback_query(call.id,"Ganancia acreditada.")
        bot.send_message(user_id,f"✅ ¡Tarea completada!\n💵 Ganancia recibida: ${amt:.2f}\n💰 Tu nuevo saldo: ${new_bal:.2f}",reply_markup=main_keyboard(lang))
        return

    if data.startswith("aprobar_") or data.startswith("rechazar_"):
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id,"Acceso denegado.")
            return
        action,sid=data.split("_",1)
        withdraw=get_withdraw_db(sid)
        if not withdraw:
            bot.answer_callback_query(call.id,"Solicitud no encontrada.")
            return
        if action=="aprobar":
            update_withdraw_status(sid,"aprobado")
            try: bot.send_message(int(sid),f"✅ Tu retiro vía {withdraw.get('method')} ha sido aprobado.")
            except: pass
            bot.answer_callback_query(call.id,"Retiro aprobado ✅")
            return
        else:
            update_withdraw_status(sid,"rechazado")
            try:
                u=get_user_db(int(sid)) or ensure_user_db(int(sid))
                returned=float(withdraw.get("balance",0.0))
                u["balance"]=round(u.get("balance",0.0)+returned,8)
                hist=u.get("history",[])
                hist.append({"at":int(time.time()),"amount":returned,"reason":"withdraw_rejected_return"})
                u["history"]=hist
                save_user_db(u)
                bot.send_message(int(sid),f"❌ Tu retiro ha sido rechazado. Se devolvió ${returned:.2f} a tu saldo.")
            except Exception: pass
            bot.answer_callback_query(call.id,"Retiro rechazado ❌")
            return

@bot.message_handler(content_types=["contact"])
def handle_contact(msg):
    if not msg.contact: return
    uid=msg.from_user.id
    u=get_user_db(uid) or ensure_user_db(uid,msg.from_user.username)
    u["phone"]=msg.contact.phone_number
    u["verified"]=True
    save_user_db(u)
    bot.send_message(uid,"✅ Gracias, tu contacto fue registrado y tu cuenta está verificada.",reply_markup=main_keyboard(u.get("lang","es")))

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id,"Acceso denegado.")
        return
    pendings=get_all_pending_withdraws()
    if not pendings:
        bot.send_message(message.chat.id,"No hay retiros pendientes.")
        return
    for info in pendings:
        sid=info.get("user_id")
        txt=f"Usuario: {info.get('username')}\nID: {sid}\nMétodo: {info.get('method')}\nCuenta: {info.get('account')}\nMonto: ${info.get('balance',0.0):.2f}"
        bot.send_message(message.chat.id,txt,reply_markup=admin_inline_keyboard(sid))

@bot.message_handler(commands=["credit"])
def admin_credit(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id,"Acceso denegado.")
        return
    parts=message.text.split()
    if len(parts)!=3:
        bot.send_message(message.chat.id,"Uso: /credit <user_id> <amount>")
        return
    try: uid=int(parts[1]); amt=float(parts[2])
    except: bot.send_message(message.chat.id,"Parámetros inválidos."); return
    new=add_balance_db(uid,amt,reason="manual_admin_credit")
    if new is None:
        bot.send_message(message.chat.id,"No se pudo acreditar (límite diario?)."); return
    bot.send_message(message.chat.id,f"Acreditado ${amt:.2f} a {uid}. Nuevo saldo: ${new:.2f}")
    try: bot.send_message(uid,f"✅ Ganancia acreditada manualmente: ${amt:.2f}\n💰 Nuevo saldo: ${new:.2f}")
    except: pass

# ---------------- FLASK WEBHOOK ----------------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str=request.get_data().decode("utf-8")
    update=telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK",200

@app.route("/")
def index():
    return "Bot corriendo!",200

if __name__=="__main__":
    init_db()
    migrate_json_to_sqlite()
    bot.remove_webhook()
    bot.set_webhook(url=f"https://TU_DOMINIO_RENDERS/render/{TOKEN}")
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
