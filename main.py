import os
import shutil
import uuid
from flask import Flask, request, abort
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8526042266:AAEYo689YISaPfOM9X3FMHtElGUCbgkZcUw"
DOMAIN = os.getenv("DOMAIN") or "https://xotirabotwh-production.up.railway.app"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or "xotirabot_0343"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ================= STORAGE =================
BASE_DIR = "storage"
TEMP_DIR = "temp"
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ================= MEMORY =================
user_state = {}          # user_id -> step
temp_files = {}          # user_id -> list of temp file paths
opened_messages = {}     # user_id -> list of message_ids

# ================= HELPERS =================
def gen_code():
    return str(uuid.uuid4()).split("-")[0].upper()

def list_albums(user_id):
    path = f"{BASE_DIR}/{user_id}"
    if not os.path.exists(path):
        return []
    return os.listdir(path)

# ================= WEBHOOK =================
@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") != "application/json":
        abort(403)
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

# ================= START =================
@bot.message_handler(commands=["start"])
def start(msg):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📁 Albom yaratish", callback_data="create"))
    kb.add(InlineKeyboardButton("📂 Albomni ochish", callback_data="open"))

    bot.send_message(
        msg.chat.id,
        "📦 *XotiraBot*\n\n"
        "Rasm va videolarni yuboring — chatdan o‘chadi, kerak bo‘lganda qayta ochib olasiz.",
        parse_mode="Markdown",
        reply_markup=kb
    )

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    uid = str(call.from_user.id)

    # ===== CREATE =====
    if call.data == "create":
        user_state[uid] = {"step": "NAME"}
        bot.send_message(call.message.chat.id, "✍️ Albom nomini yozing:")

    # ===== OPEN =====
    elif call.data == "open":
        albums = list_albums(uid)
        if not albums:
            bot.send_message(call.message.chat.id, "❌ Sizda albom yo‘q.")
            return

        kb = InlineKeyboardMarkup()
        for alb in albums:
            kb.add(InlineKeyboardButton(alb, callback_data=f"open_album_{alb}"))
        bot.send_message(call.message.chat.id, "📂 Albomni tanlang:", reply_markup=kb)

    # ===== OPEN ALBUM =====
    elif call.data.startswith("open_album_"):
        album = call.data.replace("open_album_", "")
        album_path = f"{BASE_DIR}/{uid}/{album}"

        opened_messages[uid] = []

        for f in os.listdir(album_path):
            fp = os.path.join(album_path, f)
            with open(fp, "rb") as file:
                if f.lower().endswith(".jpg"):
                    m = bot.send_photo(call.message.chat.id, file)
                elif f.lower().endswith(".mp4"):
                    m = bot.send_video(call.message.chat.id, file)
                else:
                    continue
                opened_messages[uid].append(m.message_id)

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ TAYYOR (hammasini yopish)", callback_data="close_view"))
        bot.send_message(call.message.chat.id,
                         "Fayllarni ko‘rib bo‘lgach *TAYYOR* ni bosing.",
                         parse_mode="Markdown",
                         reply_markup=kb)

    # ===== CLOSE VIEW =====
    elif call.data == "close_view":
        msgs = opened_messages.get(uid, [])
        for mid in msgs:
            try:
                bot.delete_message(call.message.chat.id, mid)
            except:
                pass
        opened_messages[uid] = []

        # Saqlash tugmachalari
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📂 Albomni ochish", callback_data="open"))
        kb.add(InlineKeyboardButton("➕ Albomga qo‘shish", callback_data="add_files"))
        bot.send_message(call.message.chat.id, "✅ Albom yopildi. Chat tozalandi.", reply_markup=kb)

    # ===== ADD FILES TO EXISTING =====
    elif call.data == "add_files":
        albums = list_albums(uid)
        if not albums:
            bot.send_message(call.message.chat.id, "❌ Sizda mavjud albom yo‘q. Yangi albom yaratishingiz mumkin.")
            return

        kb = InlineKeyboardMarkup()
        for alb in albums:
            kb.add(InlineKeyboardButton(alb, callback_data=f"add_to_{alb}"))
        kb.add(InlineKeyboardButton("📁 Yangi albom yaratish", callback_data="create"))
        bot.send_message(call.message.chat.id, "Qaysi albomga qo‘shmoqchisiz?", reply_markup=kb)

    elif call.data.startswith("add_to_"):
        album = call.data.replace("add_to_", "")
        user_state[uid] = {"step": "ADD", "album": album}
        temp_files[uid] = []
        bot.send_message(call.message.chat.id,
                         f"Albomingizga fayllarni yuboring: *{album}*\nTugagach `tayyor` tugmasini bosing.",
                         parse_mode="Markdown")

# ================= MESSAGE HANDLER =================
@bot.message_handler(content_types=["text", "photo", "video"])
def messages(msg):
    uid = str(msg.from_user.id)
    state = user_state.get(uid)

    # ===== NAME ALBUM =====
    if state and state.get("step") == "NAME":
        album = msg.text
        path = f"{BASE_DIR}/{uid}/{album}"
        os.makedirs(path, exist_ok=True)
        code = gen_code()
        with open(f"{path}/code.txt", "w") as f:
            f.write(code)

        user_state[uid] = {"step": "ADD", "album": album}
        temp_files[uid] = []

        bot.send_message(msg.chat.id,
                         f"✅ Albom yaratildi: *{album}*\nRasm yoki video yuboring.\nTugagach `tayyor` deb yozing.",
                         parse_mode="Markdown")
        return

    # ===== ADD FILES =====
    if state and state.get("step") == "ADD":
        album = state["album"]
        album_path = f"{BASE_DIR}/{uid}/{album}"

        # TAYYOR tugmasi
        if msg.text and msg.text.lower() == "tayyor":
            for p in temp_files[uid]:
                shutil.move(p, album_path)
            temp_files[uid] = []
            user_state.pop(uid)

            # Saqlashdan keyin tugmalar
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("📂 Albomni ochish", callback_data="open"))
            kb.add(InlineKeyboardButton("➕ Albomga qo‘shish", callback_data="add_files"))
            bot.send_message(msg.chat.id, "✅ Albom saqlandi.", reply_markup=kb)
            return

        # Fayllarni temp ga saqlash va chatdan o‘chirish
        if msg.content_type == "photo":
            fid = msg.photo[-1].file_id
            info = bot.get_file(fid)
            data = bot.download_file(info.file_path)
            p = f"{TEMP_DIR}/{fid}.jpg"
            open(p, "wb").write(data)
            temp_files[uid].append(p)
            bot.delete_message(msg.chat.id, msg.message_id)

        elif msg.content_type == "video":
            fid = msg.video.file_id
            info = bot.get_file(fid)
            data = bot.download_file(info.file_path)
            p = f"{TEMP_DIR}/{fid}.mp4"
            open(p, "wb").write(data)
            temp_files[uid].append(p)
            bot.delete_message(msg.chat.id, msg.message_id)

# ================= RUN =================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(f"{DOMAIN}/webhook/{WEBHOOK_SECRET}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
