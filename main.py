import asyncio
import aiohttp
import json
import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from flask import Flask
from threading import Thread

# ---------------- Flask xizmatlari ----------------
app = Flask(__name__)

@app.route("/health")
def health():
    return "ok", 200

def run_flask():
    app.run(host="0.0.0.0", port=5000)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ---------------- Bot sozlamalari ----------------
MONITOR_BOT_TOKEN = "8144186293:AAGLBCcnmgmfSg9YAzGVe3vcafYy6CXZNTg"
ADMIN_ID = 7483732504
CHECK_INTERVAL = 300
JSON_FILE = "bots.json"

bot = Bot(token=MONITOR_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------------- FSM ----------------
class AddBotState(StatesGroup):
    token = State()
    chat_id = State()

# ---------------- JSON bilan ishlash ----------------
def load_bots():
    try:
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_bots(bots):
    with open(JSON_FILE, "w") as f:
        json.dump(bots, f, indent=4, ensure_ascii=False)

# ---------------- Monitoring ----------------
async def check_bots():
    await bot.send_message(ADMIN_ID, "✅ Monitoring bot ishga tushdi.")
    while True:
        bots = load_bots()
        for b in bots:
            token = b["token"]
            chat_id = b["chat_id"]
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text=/start", timeout=10) as response:
                        data = await response.json()
                        if not data.get("ok"):
                            b["status"] = "offline"
                            b["last_down"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            save_bots(bots)
                            await bot.send_message(
                                ADMIN_ID,
                                f"⚠️ Bot ishlamayapti!\nToken: {token}\nXato: {data}"
                            )
                        else:
                            b["status"] = "online"
                            save_bots(bots)
            except Exception as e:
                b["status"] = "offline"
                b["last_down"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_bots(bots)
                await bot.send_message(
                    ADMIN_ID,
                    f"❌ Bot o‘chib qoldi!\nToken: {token}\nXato: {e}"
                )
        await asyncio.sleep(CHECK_INTERVAL)

# ---------------- Telegram komandalar ----------------
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Bu bot faqat admin uchun.")

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Bot qo‘shish", "📋 Botlar ro‘yxati")
    keyboard.add("❌ Botni o‘chirish", "📊 Bot statistikasi")
    await message.answer("👋 Salom Admin!\nQuyidagi menyudan tanlang:", reply_markup=keyboard)

# ➕ Qo‘shish
@dp.message_handler(lambda message: message.text == "➕ Bot qo‘shish")
async def add_bot(message: types.Message, state: FSMContext):
    await message.answer("🔑 Menga yangi bot token yuboring:")
    await AddBotState.token.set()

@dp.message_handler(state=AddBotState.token)
async def save_token(message: types.Message, state: FSMContext):
    await state.update_data(token=message.text.strip())
    await message.answer("📩 Endi shu botga xabar yuboradigan chat_id ni yuboring:")
    await AddBotState.chat_id.set()

@dp.message_handler(state=AddBotState.chat_id)
async def save_chat_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    token = data["token"]
    chat_id = message.text.strip()
    bots = load_bots()

    for b in bots:
        if b["token"] == token:
            await message.answer("⚠️ Bu bot allaqachon ro‘yxatda mavjud.")
            await state.finish()
            return

    new_bot = {"token": token, "chat_id": chat_id, "status": "unknown", "last_down": "Hech qachon"}
    bots.append(new_bot)
    save_bots(bots)
    await message.answer(f"✅ Bot qo‘shildi:\n{token}")
    await state.finish()

# 📋 Ro‘yxat
@dp.message_handler(lambda message: message.text == "📋 Botlar ro‘yxati")
async def list_bots(message: types.Message):
    bots = load_bots()
    if not bots:
        await message.answer("📭 Hozircha hech qanday bot qo‘shilmagan.")
    else:
        text = "📋 Botlar ro‘yxati:\n\n"
        for i, b in enumerate(bots, start=1):
            text += f"{i}. {b['token']} (status: {b['status']})\n"
        await message.answer(text)

# ❌ O‘chirish
@dp.message_handler(lambda message: message.text == "❌ Botni o‘chirish")
async def delete_bot(message: types.Message):
    bots = load_bots()
    if not bots:
        return await message.answer("📭 Hozircha hech qanday bot yo‘q.")

    keyboard = types.InlineKeyboardMarkup()
    for b in bots:
        keyboard.add(types.InlineKeyboardButton(text=b["token"], callback_data=f"delete:{b['token']}"))
    await message.answer("❌ O‘chirish uchun botni tanlang:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("delete:"))
async def confirm_delete(callback_query: types.CallbackQuery):
    token = callback_query.data.split("delete:")[1]
    bots = load_bots()
    for b in bots:
        if b["token"] == token:
            bots.remove(b)
            save_bots(bots)
            await bot.send_message(ADMIN_ID, f"🗑 Bot o‘chirildi:\n{token}")
            break
    await callback_query.answer()

# 📊 Statistikasi
@dp.message_handler(lambda message: message.text == "📊 Bot statistikasi")
async def stats_menu(message: types.Message):
    bots = load_bots()
    if not bots:
        return await message.answer("📭 Hozircha hech qanday bot yo‘q.")

    keyboard = types.InlineKeyboardMarkup()
    for b in bots:
        keyboard.add(types.InlineKeyboardButton(text=b["token"], callback_data=f"stats:{b['token']}"))
    await message.answer("📊 Statistika uchun botni tanlang:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("stats:"))
async def show_stats(callback_query: types.CallbackQuery):
    token = callback_query.data.split("stats:")[1]
    bots = load_bots()
    for b in bots:
        if b["token"] == token:
            status = b.get("status", "unknown")
            last_down = b.get("last_down", "Hech qachon")
            await bot.send_message(
                ADMIN_ID,
                f"📊 Bot statistikasi:\n\n"
                f"🆔 Token: {token}\n"
                f"📡 Status: {status}\n"
                f"⏱ Oxirgi o‘chgan vaqt: {last_down}"
            )
    await callback_query.answer()

# ---------------- Run ----------------
if __name__ == "__main__":
    keep_alive()
    loop = asyncio.get_event_loop()
    loop.create_task(check_bots())
    executor.start_polling(dp, skip_updates=True)
