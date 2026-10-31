import os, asyncio, logging, aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InputMediaPhoto,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# Токен уже вшит в код
BOT_TOKEN = os.getenv("BOT_TOKEN", "9219451712:AAH4PLqMmz7guXMcxtyOWLEg7k6eCMeBoMU").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
ADMIN_ID = int(ADMIN_ID) if ADMIN_ID.isdigit() else None
DB_PATH = "photos.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL UNIQUE,
                caption TEXT
            )
        """)
        await db.commit()

async def add_photo(file_id: str, caption: str = None) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO photos (file_id, caption) VALUES (?, ?)", (file_id, caption))
            await db.commit()
            return True
    except Exception:
        return False

async def get_all_photos():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT file_id, caption FROM photos ORDER BY id ASC") as cursor:
            return await cursor.fetchall()

async def get_photos_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM photos") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def clear_all_photos():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM photos")
        await db.commit()

def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="📸 Получить все фото")], [KeyboardButton(text="📊 Сколько фото в базе")]]
    if is_admin:
        buttons.append([KeyboardButton(text="🗑 Очистить все фото")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, persistent=True)

def get_confirm_clear_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить всё", callback_data="confirm_clear"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_clear")
    ]])

def is_admin(user_id: int) -> bool:
    return ADMIN_ID is None or user_id == ADMIN_ID

@dp.message(CommandStart())
async def handle_start(message: Message):
    admin = is_admin(message.from_user.id)
    text = (
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        "Я бот для хранения твоих фото.\n"
        "▫️ Нажми <b>«📸 Получить все фото»</b>, чтобы забрать всё сохранённое.\n"
    )
    if admin:
        text += (
            "▫️ <b>Ты администратор:</b> просто отправь мне фото в чат, и я сохраню его!\n\n"
            f"🆔 Твой ID: <code>{message.from_user.id}</code>"
        )
    await message.answer(text, reply_markup=get_main_keyboard(is_admin=admin))

@dp.message(F.photo)
async def handle_photo(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🔒 Загружать фото может только владелец бота.")
        return
    file_id = message.photo[-1].file_id
    success = await add_photo(file_id=file_id, caption=message.caption)
    if success:
        count = await get_photos_count()
        await message.answer(f"✅ Фото сохранено! Всего фото в базе: <b>{count}</b>.")
    else:
        await message.answer("⚠️ Не удалось сохранить фото (возможно, оно уже есть).")
@dp.message(F.text == "📸 Получить все фото")
async def handle_get_photos(message: Message):
    photos = await get_all_photos()
    if not photos:
        await message.answer("📭 В базе пока нет сохранённых фото. Отправьте мне фото!")
        return
    await message.answer(f"📤 Отправляю {len(photos)} фото...")
    for i in range(0, len(photos), 10):
        chunk = photos[i:i + 10]
        media = [InputMediaPhoto(media=item[0], caption=item[1] if idx == 0 else None) for idx, item in enumerate(chunk)]
        await message.answer_media_group(media=media)
        await asyncio.sleep(0.5)

@dp.message(F.text == "📊 Сколько фото в базе")
async def handle_count(message: Message):
    count = await get_photos_count()
    await message.answer(f"📊 Сейчас в базе сохранено фото: <b>{count}</b>")

@dp.message(F.text == "🗑 Очистить все фото")
async def handle_clear_prompt(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Удалить ВСЕ фото из базы?", reply_markup=get_confirm_clear_keyboard())

@dp.callback_query(F.data == "confirm_clear")
async def handle_confirm_clear(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await clear_all_photos()
    await callback.message.edit_text("🗑 Все фотографии были успешно удалены!")

@dp.callback_query(F.data == "cancel_clear")
async def handle_cancel_clear(callback: CallbackQuery):
    await callback.message.edit_text("❌ Удаление отменено.")

async def run_dummy_server():
    app = web.Application()
    app.router.add_get("/", lambda req: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

async def main():
    await init_db()
    if os.getenv("PORT"):
        await run_dummy_server()
    print("Бот успешно запущен и слушает сообщения...")
    await dp.start_polling(bot)
asyncio.run(main())
