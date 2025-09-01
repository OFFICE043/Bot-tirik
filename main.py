import asyncio
import aiohttp
import json
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from flask import Flask
from threading import Thread

# ---------------- Flask қызыметі ----------------
app = Flask(__name__)

@app.route("/health")
def health():
    return "ok", 200

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ---------------- Бот параметрлері ----------------
MONITOR_BOT_TOKEN = "8289643931:AAHaci9ymD2EDaMLBjSM1VYH_kVijtj4wwQ"  # Мониторинг бот токені
ADMIN_ID = 7483732504  # Әкімші ID
CHECK_INTERVAL = 300  # секунд (5 мин = 300, 30 мин = 1800)
JSON_FILE = "bots.json"

bot = Bot(token=MONITOR_BOT_TOKEN)
dp = Dispatcher(bot)

# ---------------- Күйлерді анықтау (FSM) ----------------
class AddBotState(StatesGroup):
    url = State()  # URL енгізу күйі

# ---------------- JSON-мен жұмыс ----------------
def load_bots():
    try:
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_bots(bots):
    with open(JSON_FILE, "w") as f:
        json.dump(bots, f, indent=4)

# ---------------- Негізгі мониторинг тапсырмасы ----------------
async def check_bots():
    await bot.send_message(ADMIN_ID, "✅ Monitoring bot ishga tushdi.")
    while True:
        bots = load_bots()
        for url in bots:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status != 200:
                            await bot.send_message(ADMIN_ID, f"⚠️ Bot ishlamayapti!\n{url}\nStatus: {response.status}")
            except Exception as e:
                await bot.send_message(ADMIN_ID, f"❌ Bot o‘chib qoldi!\n{url}\nXato: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# ---------------- Telegram командалары ----------------
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
    await message.answer("🔗 Menga health URL yuboring:")
    await AddBotState.url.set()  # Күйді орнату

@dp.message_handler(state=AddBotState.url)
async def save_new_bot(message: types.Message, state: FSMContext):
    url = message.text.strip()
    bots = load_bots()
    if url in bots:
        await message.answer("⚠️ Bu URL allaqachon ro‘yxatda mavjud.")
    else:
        bots.append(url)
        save_bots(bots)
        await message.answer(f"✅ Bot qo‘shildi:\n{url}")
    await state.finish()  # Күйді аяқтау

@dp.message_handler(lambda message: message.text == "📋 Botlar ro‘yxati")
async def list_bots(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    bots = load_bots()
    if not bots:
        await message.answer("📭 Hozircha hech qanday bot qo‘shilmagan.")
    else:
        text = "📋 Botlar ro‘yxati:\n\n"
        for i, url in enumerate(bots, start=1):
            text += f"{i}. {url}\n"
        await message.answer(text)

@dp.message_handler(lambda message: message.text == "❌ Botni o‘chirish")
async def delete_bot(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    bots = load_bots()
    if not bots:
        return await message.answer("📭 Hozircha hech qanday bot yo‘q.")

    keyboard = types.InlineKeyboardMarkup()
    for url in bots:
        keyboard.add(types.InlineKeyboardButton(text=url, callback_data=f"delete:{url}"))
    await message.answer("❌ O‘chirish uchun botni tanlang:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("delete:"))
async def confirm_delete(callback_query: types.CallbackQuery):
    url = callback_query.data.split("delete:")[1]
    bots = load_bots()
    if url in bots:
        bots.remove(url)
        save_bots(bots)
        await bot.send_message(ADMIN_ID, f"🗑 Bot o‘chirildi:\n{url}")
    else:
        await bot.send_message(ADMIN_ID, "⚠️ Bu bot ro‘yxatda topilmadi.")
    await callback_query.answer()  # Callback-қа жауап беру

# ---------------- Іске қосу ----------------
if __name__ == "__main__":
    # Flask-ті бөлек ағында іске қосу
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    loop = asyncio.get_event_loop()
    loop.create_task(check_bots())  # Фондық тексеру тапсырмасы
    executor.start_polling(dp, skip_updates=True)
