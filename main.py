from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
import sqlite3
import logging

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
API_TOKEN = "7835080263:AAGS8x3VbbVwxK46ddM0RglJIS2lUXAo8y4"
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

# Подключение к базе данных
conn = sqlite3.connect("bot_database.db")
cursor = conn.cursor()

# Создаем таблицы, если они не существуют
cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL UNIQUE,
    channel_name TEXT NOT NULL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscribers (
    user_id INTEGER NOT NULL,
    channel_id TEXT NOT NULL,
    UNIQUE(user_id, channel_id)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS users_stat (
    user_id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0
)
""")
conn.commit()


# Состояния для админ-команды
class AdminStates(StatesGroup):
    waiting_for_channel_id = State()


# Проверка, является ли пользователь админом
ADMINS = [6850731097]  # Укажите ID администраторов


def is_admin(user_id):
    return user_id in ADMINS


# Команда /start
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    channels = cursor.execute("SELECT channel_id, channel_name FROM channels").fetchall()

    if not channels:
        await message.answer("Пока нет доступных каналов для подписки.")
        return

    keyboard = types.InlineKeyboardMarkup()
    for channel_id, channel_name in channels:
        keyboard.add(
            types.InlineKeyboardButton(f"Подписаться на {channel_name}", callback_data=f"subscribe_{channel_id}"))

    await message.answer("Выберите канал для подписки:", reply_markup=keyboard)


# Обработка подписки на канал
@dp.callback_query_handler(lambda c: c.data.startswith("subscribe_"))
async def subscribe_to_channel(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    channel_id = callback_query.data.split("_")[1]

    try:
        cursor.execute("INSERT INTO subscribers (user_id, channel_id) VALUES (?, ?)", (user_id, channel_id))
        conn.commit()
        await callback_query.answer(f"Вы подписались на канал.", show_alert=True)
    except sqlite3.IntegrityError:
        await callback_query.answer("Вы уже подписаны на этот канал.", show_alert=True)


# Команда /admin
@dp.message_handler(commands=["admin"])
async def admin_command(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    await message.answer("Введите ID канала, который нужно добавить:")
    await AdminStates.waiting_for_channel_id.set()


# Обработка ID канала от админа
@dp.message_handler(state=AdminStates.waiting_for_channel_id)
async def add_channel(message: types.Message, state: FSMContext):
    channel_id = message.text

    try:
        # Получаем информацию о канале
        chat = await bot.get_chat(channel_id)
        channel_name = chat.title

        # Сохраняем канал в базу данных
        cursor.execute("INSERT INTO channels (channel_id, channel_name) VALUES (?, ?)", (channel_id, channel_name))
        conn.commit()
        await message.answer(f"Канал {channel_name} успешно добавлен.")
    except Exception as e:
        logging.error(f"Ошибка при добавлении канала: {e}")
        await message.answer("Не удалось добавить канал. Проверьте ID канала.")

    await state.finish()


# Обработчик новых сообщений в канале
@dp.channel_post_handler()
async def on_new_post(message: types.Message):
    channels = cursor.execute("SELECT channel_id, channel_name FROM channels").fetchall()
    for channel_id, channel_name in channels:
        if message.chat.id == int(channel_id):
            post_link = f"https://t.me/{message.chat.username}/{message.message_id}"

            # Получаем список подписчиков для этого канала
            subscribers = cursor.execute("SELECT user_id FROM subscribers WHERE channel_id = ?",
                                         (channel_id,)).fetchall()
            for subscriber in subscribers:
                user_id = subscriber[0]
                try:
                    await bot.send_message(user_id,
                                           f"Новый пост в канале <b>{channel_name}</b>: <a href=\"{post_link}\">Смотреть</a>")
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

                # Увеличиваем количество баллов пользователя на 5
                cursor.execute("INSERT OR IGNORE INTO users_stat (user_id, points) VALUES (?, ?)", (user_id, 0))
                cursor.execute("UPDATE users_stat SET points = points + 5 WHERE user_id = ?", (user_id,))
                conn.commit()


# Команда /points для отображения баллов пользователя
@dp.message_handler(commands=["p"])
async def points_command(message: types.Message):
    user_id = message.from_user.id
    result = cursor.execute("SELECT points FROM users_stat WHERE user_id = ?", (user_id,)).fetchone()

    if result:
        points = result[0]
        await message.answer(f"У вас {points} баллов.")
    else:
        await message.answer("У вас нет баллов. Начните активно участвовать в канале!")





if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
