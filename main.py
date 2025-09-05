import asyncio
import aiohttp
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from flask import Flask
from threading import Thread

# ---------------- Flask keep_alive ----------------
app = Flask(__name__)

@app.route("/health")
def health():
    return "ok", 200

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ---------------- Config ----------------
MONITOR_BOT_TOKEN = "8144186293:AAGLBCcnmgmfSg9YAzGVe3vcafYy6CXZNTg"   # monitoring bot token
ADMIN_ID = 7483732504                 # admin id
CHECK_INTERVAL = 300                  # 5 minut
JSON_FILE = "bots.json"

bot = Bot(token=MONITOR_BOT_TOKEN)
dp = Dispatcher(bot)

# ---------------- FSM ----------------
class AddBotState(StatesGroup):
    token = State()
    username = State()

# ---------------- JSON ishlash ----------------
def load_bots():
    try:
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_bots(bots):
    with open(JSON_FILE, "w") as f:
        json.dump(bots, f, indent=4, ensure_ascii=False)

def update_status(token, status):
    bots = load_bots()
    for b in bots:
        if b["token"] == token:
            b["status"] = status
            if status == "online":
                b["last_online"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                b["last_offline"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_bots(bots)

# ---------------- Tekshirish ----------------
async def check_bots():
    await bot.send_message(ADMIN_ID, "✅ Monitoring ishga tushdi.")
    while True:
        bots = load_bots()
        for b in bots:
            token = b["token"]
            username = b["username"]

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10) as resp:
                        if resp.status == 200:
                            # agar hozir offline bo‘lsa → online bo‘ldi
                            if b.get("status") != "online":
                                await bot.send_message(ADMIN_ID, f"🟢 Bot online bo‘ldi: @{username}")
                            update_status(token, "online")
                        else:
                            if b.get("status") != "offline":
                                await bot.send_message(ADMIN_ID, f"❌ Bot offline bo‘ldi: @{username}")
                            update_status(token, "offline")
            except Exception:
                if b.get("status") != "offline":
                    await bot.send_message(ADMIN_ID, f"❌ Bot o‘chdi: @{username}")
                update_status(token, "offline")

        await asyncio.sleep(CHECK_INTERVAL)

# ---------------- Telegram komandalar ----------------
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Bu bot faqat admin uchun.")

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Bot qo‘shish", "📋 Botlar ro‘yxati")
    keyboard.add("❌ Botni o‘chirish", "📊 Bot statistika")
    await message.answer("👋 Salom Admin!\nQuyidagilardan tanlang:", reply_markup=keyboard)

# ➕ qo‘shish
@dp.message_handler(lambda m: m.text == "➕ Bot qo‘shish")
async def add_bot(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🔑 Bot token yuboring:")
    await AddBotState.token.set()

@dp.message_handler(state=AddBotState.token)
async def add_bot_token(message: types.Message, state: FSMContext):
    await state.update_data(token=message.text.strip())
    await message.answer("👤 Bot username yuboring (@ bilan):")
    await AddBotState.username.set()

@dp.message_handler(state=AddBotState.username)
async def add_bot_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    token = data["token"]
    username = message.text.strip().lstrip("@")

    bots = load_bots()
    bots.append({
        "token": token,
        "username": username,
        "status": "unknown",
        "last_online": None,
        "last_offline": None
    })
    save_bots(bots)

    await message.answer(f"✅ Bot qo‘shildi: @{username}")
    await state.finish()

# 📋 ro‘yxat
@dp.message_handler(lambda m: m.text == "📋 Botlar ro‘yxati")
async def list_bots(message: types.Message):
    bots = load_bots()
    if not bots:
        return await message.answer("📭 Hech qanday bot yo‘q.")
    text = "📋 Botlar:\n\n"
    for i, b in enumerate(bots, 1):
        text += f"{i}. @{b['username']} — {b['status']}\n"
    await message.answer(text)

# ❌ o‘chirish
@dp.message_handler(lambda m: m.text == "❌ Botni o‘chirish")
async def delete_bot(message: types.Message):
    bots = load_bots()
    if not bots:
        return await message.answer("📭 Hech qanday bot yo‘q.")
    kb = types.InlineKeyboardMarkup()
    for b in bots:
        kb.add(types.InlineKeyboardButton(f"@{b['username']}", callback_data=f"del:{b['token']}"))
    await message.answer("❌ O‘chirish uchun tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("del:"))
async def delete_bot_confirm(call: types.CallbackQuery):
    token = call.data.split(":")[1]
    bots = load_bots()
    bots = [b for b in bots if b["token"] != token]
    save_bots(bots)
    await call.message.answer("🗑 Bot o‘chirildi.")
    await call.answer()

# 📊 statistika
@dp.message_handler(lambda m: m.text == "📊 Bot statistika")
async def bot_statistics(message: types.Message):
    bots = load_bots()
    if not bots:
        return await message.answer("📭 Hozircha hech qanday bot yo‘q.")
    kb = types.InlineKeyboardMarkup()
    for b in bots:
        kb.add(types.InlineKeyboardButton(f"@{b['username']}", callback_data=f"stat:{b['token']}"))
    await message.answer("📊 Qaysi botni tekshirasiz?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("stat:"))
async def show_stats(call: types.CallbackQuery):
    token = call.data.split(":")[1]
    bots = load_bots()
    for b in bots:
        if b["token"] == token:
            text = f"📊 @{b['username']} statistika:\n\n"
            text += f"🟢 Status: {b['status']}\n"
            text += f"⏰ Oxirgi online: {b['last_online']}\n"
            text += f"❌ Oxirgi offline: {b['last_offline']}\n"
            await call.message.answer(text)
            break
    await call.answer()

# ---------------- Run ----------------
if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    loop = asyncio.get_event_loop()
    loop.create_task(check_bots())
    executor.start_polling(dp, skip_updates=True)
