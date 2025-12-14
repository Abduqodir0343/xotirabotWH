import os
import shutil
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
DOMAIN = os.getenv("DOMAIN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not TOKEN or not DOMAIN or not WEBHOOK_SECRET:
    raise ValueError("BOT_TOKEN, DOMAIN yoki WEBHOOK_SECRET set qilinmagan!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= STORAGE =================
os.makedirs("albums", exist_ok=True)
os.makedirs("temp_files", exist_ok=True)

user_state = {}
temp_files = {}

# ================= WEBHOOK =================
@app.route(f"/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ================= START =================
@bot.message_handler(commands=["start"])
def start(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📁 Albom yaratish", callback_data="create"))
    kb.add(InlineKeyboardButton("📂 Albomni ochish", callback_data="open"))
    kb.add(InlineKeyboardButton("🗑 Albomni o‘chirish", callback_data="delete"))
    bot.send_message(message.chat.id, "👋 Albom botga xush kelibsiz", reply_markup=kb)

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    uid = str(c.from_user.id)

    if c.data == "create":
        user_state[uid] = {"step": "album_name"}
        bot.send_message(c.message.chat.id, "📝 Albom nomini yozing:")

    elif c.data == "open":
        base = f"albums/{uid}"
        if not os.path.exists(base):
            bot.send_message(c.message.chat.id, "❌ Albom yo‘q")
            return
        kb = InlineKeyboardMarkup()
        for a in os.listdir(base):
            kb.add(InlineKeyboardButton(a, callback_data=f"open_{a}"))
        bot.send_message(c.message.chat.id, "📂 Albomni tanlang:", reply_markup=kb)

    elif c.data.startswith("open_"):
        album = c.data.replace("open_", "")
        path = f"albums/{uid}/{album}"
        if not os.path.exists(path):
            bot.send_message(c.message.chat.id, "❌ Albom topilmadi")
            return
        for f in os.listdir(path):
            fp = os.path.join(path, f)
            with open(fp, "rb") as file:
                if f.lower().endswith((".jpg",".png",".jpeg")):
                    bot.send_photo(c.message.chat.id, file)
                else:
                    bot.send_video(c.message.chat.id, file)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Tayyor / Yopish", callback_data="done"))
        bot.send_message(c.message.chat.id, "Tugatdingizmi?", reply_markup=kb)

    elif c.data == "delete":
        base = f"albums/{uid}"
        if not os.path.exists(base):
            bot.send_message(c.message.chat.id, "❌ Albom yo‘q")
            return
        kb = InlineKeyboardMarkup()
        for a in os.listdir(base):
            kb.add(InlineKeyboardButton(a, callback_data=f"del_{a}"))
        bot.send_message(c.message.chat.id, "🗑 Qaysi albom o‘chadi?", reply_markup=kb)

    elif c.data.startswith("del_"):
        album = c.data.replace("del_", "")
        shutil.rmtree(f"albums/{uid}/{album}", ignore_errors=True)
        bot.send_message(c.message.chat.id, f"✅ {album} o‘chirildi")

    elif c.data == "done":
        bot.send_message(c.message.chat.id, "✅ Albom yopildi")

# ================= FILE HANDLER =================
@bot.message_handler(content_types=["photo", "video", "text"])
def files(message):
    uid = str(message.from_user.id)
    state = user_state.get(uid)

    # ALBOM NOMI
    if state and state.get("step") == "album_name":
        album = message.text
        path = f"albums/{uid}/{album}"
        os.makedirs(path, exist_ok=True)
        user_state[uid] = {"step": "upload", "album": album}
        temp_files[uid] = []
        bot.send_message(
            message.chat.id,
            "📤 Rasm/video yuboring.\nTugagach 👉 *tayyor* deb yozing",
            parse_mode="Markdown"
        )
        return

    # UPLOAD
    if state and state.get("step") == "upload":
        album = state["album"]
        album_path = f"albums/{uid}/{album}"

        if message.text and message.text.lower() == "tayyor":
            for t in temp_files[uid]:
                shutil.move(t, album_path)
            temp_files[uid].clear()
            user_state.pop(uid)
            bot.send_message(message.chat.id, "✅ Albom saqlandi")
            return

        if message.content_type == "photo":
            f_id = message.photo[-1].file_id
            info = bot.get_file(f_id)
            data = bot.download_file(info.file_path)
            path = f"temp_files/{f_id}.jpg"
            open(path, "wb").write(data)
            temp_files[uid].append(path)

        elif message.content_type == "video":
            f_id = message.video.file_id
            info = bot.get_file(f_id)
            data = bot.download_file(info.file_path)
            path = f"temp_files/{f_id}.mp4"
            open(path, "wb").write(data)
            temp_files[uid].append(path)

        bot.send_message(message.chat.id, "📥 Qabul qilindi")

# ================= RUN =================
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    bot.remove_webhook()
    bot.set_webhook(
        url=f"https://{DOMAIN}/{WEBHOOK_SECRET}",
        drop_pending_updates=True
    )
    app.run(host="0.0.0.0", port=PORT)

