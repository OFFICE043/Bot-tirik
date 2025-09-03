import asyncio
import aiohttp
import json
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
MONITOR_BOT_TOKEN = "8144186293:AAGLBCcnmgmfSg9YAzGVe3vcafYy6CXZNTg"   # Monitoring bot tokeni
ADMIN_ID = 7483732504                     # Admin ID
CHECK_INTERVAL = 300                      # 5 minut = 300
JSON_FILE = "bots.json"

bot = Bot(token=MONITOR_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------------- FSM ----------------
class AddBotState(StatesGroup):
    token = State()  # Yangi bot token kiritish

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
        for token in bots:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10) as response:
                        data = await response.json()
                        if not data.get("ok"):
                            await bot.send_message(
                                ADMIN_ID,
                                f"⚠️ Bot ishlamayapti!\nToken: {token}\nXato: {data}"
                            )
            except Exception as e:
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
    keyboard.add("❌ Botni o‘chirish")
    await message.answer("👋 Salom Admin!\nQuyidagi menyudan tanlang:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "➕ Bot qo‘shish")
async def add_bot(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🔑 Menga yangi bot token yuboring:")
    await AddBotState.token.set()

@dp.message_handler(state=AddBotState.token)
async def save_new_bot(message: types.Message, state: FSMContext):
    token = message.text.strip()
    bots = load_bots()
    if token in bots:
        await message.answer("⚠️ Bu token allaqachon ro‘yxatda mavjud.")
    else:
        bots.append(token)
        save_bots(bots)
        await message.answer(f"✅ Bot qo‘shildi:\n{token}")
    await state.finish()

@dp.message_handler(lambda message: message.text == "📋 Botlar ro‘yxati")
async def list_bots(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    bots = load_bots()
    if not bots:
        await message.answer("📭 Hozircha hech qanday bot qo‘shilmagan.")
    else:
        text = "📋 Botlar ro‘yxati:\n\n"
        for i, token in enumerate(bots, start=1):
            text += f"{i}. {token}\n"
        await message.answer(text)

@dp.message_handler(lambda message: message.text == "❌ Botni o‘chirish")
async def delete_bot(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    bots = load_bots()
    if not bots:
        return await message.answer("📭 Hozircha hech qanday bot yo‘q.")

    keyboard = types.InlineKeyboardMarkup()
    for token in bots:
        keyboard.add(types.InlineKeyboardButton(text=token, callback_data=f"delete:{token}"))
    await message.answer("❌ O‘chirish uchun botni tanlang:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("delete:"))
async def confirm_delete(callback_query: types.CallbackQuery):
    token = callback_query.data.split("delete:")[1]
    bots = load_bots()
    if token in bots:
        bots.remove(token)
        save_bots(bots)
        await bot.send_message(ADMIN_ID, f"🗑 Bot o‘chirildi:\n{token}")
    else:
        await bot.send_message(ADMIN_ID, "⚠️ Bu bot ro‘yxatda topilmadi.")
    await callback_query.answer()

# ---------------- Run ----------------
if __name__ == "__main__":
    keep_alive()  # Flask run

    loop = asyncio.get_event_loop()
    loop.create_task(check_bots())  # Monitoring start
    executor.start_polling(dp, skip_updates=True)
