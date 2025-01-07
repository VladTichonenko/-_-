from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
import sqlite3
import logging
import random
import qrcode
from io import BytesIO

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
API_TOKEN =  "7835080263:AAGS8x3VbbVwxK46ddM0RglJIS2lUXAo8y4"
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

# Подключение к базе данных
conn = sqlite3.connect("bot_database.db")
cursor = conn.cursor()

# Создаем таблицы, если они не существуют
# Изменяем создание таблицы, чтобы добавить столбец для URL
cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL UNIQUE,
    channel_name TEXT NOT NULL,
    channel_url TEXT NOT NULL
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
    points INTEGER DEFAULT 0,
    ref_code TEXT UNIQUE,
    referrals TEXT DEFAULT ''
)
""")
conn.commit()



def generate_ref_code():
    """Генерация уникального 4-значного реферального кода."""
    return str(random.randint(1000, 9999))

def add_user_to_db(user_id):
    """Добавление пользователя в базу данных, если его там нет."""
    cursor.execute("SELECT * FROM users_stat WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        ref_code = generate_ref_code()
        while cursor.execute("SELECT * FROM users_stat WHERE ref_code = ?", (ref_code,)).fetchone():
            ref_code = generate_ref_code()
        cursor.execute("INSERT INTO users_stat (user_id, ref_code) VALUES (?, ?)", (user_id, ref_code))
        conn.commit()

def get_user_data(user_id):
    """Получение данных пользователя из базы."""
    cursor.execute("SELECT * FROM users_stat WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def add_referral(referrer_id, referral_id):
    """Обработка добавления реферала."""
    referrer_data = get_user_data(referrer_id)
    if referrer_data:
        referrals = referrer_data[3].split(',') if referrer_data[3] else []
        if str(referral_id) not in referrals:
            referrals.append(str(referral_id))
            cursor.execute(
                "UPDATE users_stat SET points = points + 15, referrals = ? WHERE user_id = ?",
                (','.join(referrals), referrer_id)
            )
            conn.commit()

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    channels = cursor.execute("SELECT channel_id, channel_name FROM channels").fetchall()

    add_user_to_db(user_id)
    args = message.get_args()
    if args:
        try:
            referrer_id = cursor.execute("SELECT user_id FROM users_stat WHERE ref_code = ?", (args,)).fetchone()
            if referrer_id and referrer_id[0] != user_id:
                add_referral(referrer_id[0], user_id)
                await bot.send_message(referrer_id[0], f"Вы пригласили нового пользователя: {message.from_user.full_name}!")
        except Exception as e:
            logging.error(f"Ошибка обработки реферала: {e}")

    if not channels:
        await message.answer("Пока нет доступных каналов для подписки.")
        return

    keyboard = types.InlineKeyboardMarkup()
    for channel_id, channel_name in channels:
        keyboard.add(
            types.InlineKeyboardButton(f"Подписаться на {channel_name}", callback_data=f"subscribe_{channel_id}"))

    await message.answer("Выберите канал для подписки:", reply_markup=keyboard)

@dp.message_handler(commands=['prof'])
async def show_profile(message: types.Message):
    """Обработка команды /prof для отображения профиля пользователя."""
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    if user_data:
        ref_code = user_data[2]
        points = user_data[1]
        referrals = user_data[3]
        referral_list = referrals.split(',') if referrals else []
        referral_names = []
        for ref_id in referral_list:
            user = await bot.get_chat(ref_id)
            referral_names.append(user.full_name)

        referral_names_str = '\n'.join(referral_names) if referral_names else "Нет рефералов"

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Получить QR-код", callback_data="get_qr"))

        await message.answer(
            f"👾 Ваш профиль:\n\n"
            f"Проверочный код: {ref_code}\n"
            f"Баллы 💸: {points}\n"
            f"____________________________\n"
            f"Реферальная ссылка: https://t.me/{(await bot.get_me()).username}?start={ref_code}\n"
            f"Ваши рефералы:\n{referral_names_str}",
            reply_markup=keyboard
        )
    else:
        await message.answer("Ваш профиль не найден.")

@dp.callback_query_handler(lambda c: c.data == "get_qr")
async def generate_qr_code(callback_query: types.CallbackQuery):
    """Генерация QR-кода для реферальной ссылки."""
    user_id = callback_query.from_user.id
    user_data = get_user_data(user_id)

    if user_data:
        ref_code = user_data[2]
        bot_username = (await bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={ref_code}"

        # Генерация QR-кода
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(referral_link)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)

        # Отправка QR-кода пользователю
        await bot.send_photo(
            callback_query.message.chat.id,
            photo=bio,
            caption=f"Ваш реферальный QR-код:\nСсылка: {referral_link}"
        )
    else:
        await callback_query.answer("Ваш профиль не найден. Используйте /start для регистрации.", show_alert=True)

# Состояния для админ-команды
class AdminStates(StatesGroup):
    waiting_for_channel_id = State()  # Ожидание ID канала
    waiting_for_channel_url = State()  # Ожидание ссылки канала

# Проверка, является ли пользователь админом
ADMINS = [6850731097]  # Укажите ID администраторов

def is_admin(user_id):
    return user_id in ADMINS

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
async def add_channel_id(message: types.Message, state: FSMContext):
    channel_id = message.text

    try:
        # Проверим, существует ли канал с таким ID
        chat = await bot.get_chat(channel_id)
        channel_name = chat.title

        # Спросим ссылку на канал
        await state.update_data(channel_id=channel_id, channel_name=channel_name)
        await message.answer(f"Канал <b>{channel_name}</b> найден. Теперь отправьте ссылку на канал:")
        await AdminStates.waiting_for_channel_url.set()
    except Exception as e:
        logging.error(f"Ошибка при добавлении канала: {e}")
        await message.answer("Не удалось найти канал. Проверьте ID канала.")


# Обработка ссылки канала от админа
@dp.message_handler(state=AdminStates.waiting_for_channel_url)
async def add_channel_url(message: types.Message, state: FSMContext):
    channel_url = message.text
    data = await state.get_data()

    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    try:
        # Сохраняем канал в базу данных вместе с URL
        cursor.execute(
            "INSERT INTO channels (channel_id, channel_name, channel_url) VALUES (?, ?, ?)",
            (channel_id, channel_name, channel_url)
        )
        conn.commit()

        await message.answer(f"Канал <b>{channel_name}</b> с URL {channel_url} успешно добавлен.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении канала: {e}")
        await message.answer("Не удалось добавить канал в базу данных.")

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

            # Инициализируем список уведомленных пользователей для поста
            if message.chat.id not in notified_users:
                notified_users[message.chat.id] = {}
            notified_users[message.chat.id][message.message_id] = []

            for subscriber in subscribers:
                user_id = subscriber[0]
                try:
                    await bot.send_message(
                        user_id,
                        f"Новый пост в канале <b>{channel_name}</b>: <a href=\"{post_link}\">Смотреть</a>\n"
                        f"Оставьте комментарий под этим постом, чтобы получить 5 баллов!"
                    )
                    # Добавляем пользователя в список для поста
                    notified_users[message.chat.id][message.message_id].append(user_id)
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    logging.info(f"Обновлен notified_users: {notified_users}")

# Команда /points для отображения баллов пользователя
@dp.message_handler(commands=["points"])
async def points_command(message: types.Message):
    user_id = message.from_user.id
    result = cursor.execute("SELECT points FROM users_stat WHERE user_id = ?", (user_id,)).fetchone()

    if result:
        points = result[0]
        await message.answer(f"У вас {points} баллов.")
    else:
        await message.answer("У вас нет баллов. Начните активно участвовать в канале!")


# Список уведомленных пользователей для конкретных постов
notified_users = {}
logging.info(f"notified_users: {notified_users}")


# Список запрещенных слов
bad_words = [
    "мат", "сука", "пизда", "ебать", "хуй", "пиздец", "сучка", "ебаный", "хер", "жопа",
    "шлюха", "блядь", "ебло", "отпиздить", "мудила", "педик", "пошел нахуй", "гандон",
    "придурок", "дурак", "урод", "ебать", "петух", "бля", "залупа", "засранец", "ублюдок",
    "мразь", "осел", "козел", "долбоеб", "свинья", "сучара", "пидарас", "тварь", "гандон",
    "хрен", "соса", "писька", "суки", "потаскать", "идиот", "отморозок", "говно", "дерьмо",
    "падло", "тупой", "задрот", "хрень", "мутант", "лошара"
]




@dp.message_handler()
async def on_user_comment(message: types.Message):
    """Начисление баллов только тем пользователям, которые есть в базе, и проверка на запрещенные слова."""
    user_id = message.from_user.id
    comment = message.text.lower()  # Приводим текст комментария к нижнему регистру

    # Проверка на наличие запрещенных слов
    if any(bad_word in comment for bad_word in bad_words):
        # Удаляем комментарий
        await message.delete()
        await message.answer( "Ваш комментарий содержит запрещенные слова и был удален.")
        return

    # Проверяем, есть ли пользователь в базе
    cursor.execute("SELECT 1 FROM users_stat WHERE user_id = ?", (user_id,))
    if cursor.fetchone():  # Если пользователь найден
        # Начисляем баллы
        cursor.execute("UPDATE users_stat SET points = points + 5 WHERE user_id = ?", (user_id,))
        conn.commit()
    else:
        await message.reply("Ваш комментарий не подходит для начисления баллов. Вы не зарегистрированы в системе.")



if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
