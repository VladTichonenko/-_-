import sqlite3
import random
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telethon.sync import TelegramClient
from telethon import functions, types as telethon_types

API_TOKEN = '7820864726:AAGWQGBnqHxmtc-R-uO9KYhOtf3jslggPzI'
api_id = "20211195"
api_hash = "900a88063d66744450d23f6ddd52af6e"
phone = "+375295332073"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

client = TelegramClient(phone, api_id, api_hash)



def get_all_user_ids(channel_id):
    try:
        conn = sqlite3.connect('bot_database.db')  # Подключаемся к базе данных
        cursor = conn.cursor()

        cursor.execute('SELECT user_id FROM subscribers WHERE channel_id = ?', (channel_id,))  # Извлекаем все user_id для данного channel_id
        rows = cursor.fetchall()

        user_ids = [row[0] for row in rows]  # Преобразуем результат в список user_id
        return user_ids

    except sqlite3.Error as e:
        print(f"Ошибка при подключении к базе данных: {e}")
        return []

    finally:
        if conn:
            conn.close()  # Закрываем соединение с базой данных


def update_user_score(user_id, points):
    try:
        conn = sqlite3.connect('bot_database.db')  # Подключаемся к базе данных
        cursor = conn.cursor()

        # Проверяем, существует ли запись для данного user_id
        cursor.execute('SELECT points FROM user_stat WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

        if row:
            # Обновляем количество баллов для существующего пользователя
            new_points = row[0] + points
            cursor.execute('UPDATE user_stat SET points = ? WHERE user_id = ?', (new_points, user_id))
        else:
            # Создаем новую запись для нового пользователя
            cursor.execute('INSERT INTO user_stat (user_id, points) VALUES (?, ?)', (user_id, points))

        conn.commit()  # Сохраняем изменения
        print(f"Баллы пользователя {user_id} успешно обновлены.")

    except sqlite3.Error as e:
        print(f"Ошибка при обновлении баллов пользователя: {e}")

    finally:
        if conn:
            conn.close()  # Закрываем соединение с базой данных



def get_random_user_id(channel_id):
    try:
        conn = sqlite3.connect('bot_database.db')  # Подключаемся к базе данных
        cursor = conn.cursor()

        cursor.execute('SELECT user_id FROM subscribers WHERE channel_id = ?', (channel_id,))  # Извлекаем все user_id для данного channel_id
        rows = cursor.fetchall()

        if rows:
            random_user = random.choice(rows)  # Выбираем случайный user_id
            return random_user[0]
        else:
            print(f"Нет подписчиков для канала с id {channel_id}.")
            return None

    except sqlite3.Error as e:
        print(f"Ошибка при подключении к базе данных: {e}")
        return None

    finally:
        if conn:
            conn.close()  # Закрываем соединение с базой данных


# Пример базы данных каналов
channels_db = []

def load_channels_from_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT channel_id, channel_name, channel_url FROM channels')
    rows = cursor.fetchall()

    for row in rows:
        channel = {
            'id': row[0],
            'name': row[1],
            'channel_link': row[2]
        }
        channels_db.append(channel)

    conn.close()

load_channels_from_db()

# Словарь для хранения последнего сообщения в каждом канале
last_message_id = {}

# Очередь для обработки сообщений
message_queue = asyncio.Queue()

async def get_previous_message_reactions(channel):
    async with client:
        messages = await client.get_messages(channel, limit=2)  # Получаем два последних сообщения

        if len(messages) > 1:
            previous_msg_id = messages[1].id  # Получаем ID предыдущего сообщения
            print(f"Используемый previous_msg_id: {previous_msg_id}")

            # Получение списка реакций
            result = await client(functions.messages.GetMessagesReactionsRequest(
                peer=channel,
                id=[previous_msg_id]
            ))

            # Подсчет общего количества реакций
            total_reactions = 0
            for update in result.updates:
                if isinstance(update, telethon_types.UpdateMessageReactions):
                    total_reactions += sum(reaction.count for reaction in update.reactions.results)
            print(f"Общее количество реакций на предыдущем сообщении: {total_reactions}")

            return total_reactions
        else:
            print("Нет предыдущего сообщения.")
            return None


async def get_total_reactions(channel):
    async with client:
        messages = await client.get_messages(channel, limit=1)

        if messages:
            msg_id = messages[0].id
            print(f"Используемый msg_id: {msg_id}")

            # Проверка на новое сообщение
            if channel not in last_message_id or msg_id != last_message_id[channel]:
                last_message_id[channel] = msg_id

                # Получение списка реакций
                result = await client(functions.messages.GetMessagesReactionsRequest(
                    peer=channel,
                    id=[msg_id]
                ))

                # Подсчет общего количества реакций
                total_reactions = 0
                for update in result.updates:
                    if isinstance(update, telethon_types.UpdateMessageReactions):
                        total_reactions += sum(reaction.count for reaction in update.reactions.results)
                print(f"Общее количество реакций: {total_reactions}")

                return total_reactions
            else:
                print("Сообщение не новое.")
                return None

@dp.channel_post_handler()
async def channel_message(message: types.Message):
    await message_queue.put(message)

async def process_queue():
    while not message_queue.empty():
        message = await message_queue.get()
        chat_id = message.chat.id
        message_id = message.message_id

        if chat_id not in last_message_id or message_id != last_message_id[chat_id]:
            last_message_id[chat_id] = message_id
            print(f"Новый пост в {message.chat.title}: {message.text}")
            reactions = await get_previous_message_reactions(chat_id)
            if reactions is not None:
                print(f"Общее количество реакций на последнем сообщении: {reactions}")

            user_id1 = get_random_user_id(chat_id)  # Получаем случайный user_id для данного chat_id
            if user_id1:
                try:
                    await bot.send_message(user_id1, f"Вы выиграли {reactions * 50} баллов!")
                    update_user_score(user_id1,reactions*5)
                except Exception as e:
                    print(f"Не удалось отправить сообщение пользователю {user_id1}: {e}")

            # Получаем ссылку на канал из базы данных
            channel_link = next((channel['channel_link'] for channel in channels_db if channel['id'] == chat_id), None)
            if channel_link is None:
                print(f"Канал с идентификатором {chat_id} не найден в базе данных.")
                continue

            post_url = channel_link
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Перейти к посту", url=post_url),
                InlineKeyboardButton("Получить баллы", callback_data=f"goto_post:{message_id}")
            )

            user_ids = get_all_user_ids(chat_id)
            for user_id in user_ids:
                try:
                    await bot.send_message(user_id, "Новый пост в канале!", reply_markup=keyboard)
                    await asyncio.sleep(40)  # Пауза в 40 секунд между отправкой сообщений
                except Exception as e:
                    print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

        message_queue.task_done()



@dp.callback_query_handler(lambda c: c.data and c.data.startswith('goto_post'))
async def process_goto_post(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    channel_id = int(callback_query.data.split(':')[1])

    initial_reactions = await get_total_reactions(channel_id)

    await asyncio.sleep(10)  # Ждем 10 секунд

    final_reactions = await get_total_reactions(channel_id)

    try:
        if final_reactions > initial_reactions:
            update_user_score(user_id, 50)
            await bot.answer_callback_query(callback_query.id, "Вы получили 50 баллов!")
            await bot.send_message(callback_query.message.chat.id, f"Пользователь {callback_query.from_user.username} получил 50 баллов!")
        else:
            await bot.answer_callback_query(callback_query.id, "Количество реакций не изменилось.")
            await bot.send_message(callback_query.message.chat.id, "Количество реакций не изменилось.")
    except Exception as e:
        print(f"Ошибка при обработке callback_query: {e}")


if __name__ == '__main__':
    load_channels_from_db()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(process_queue())
    executor.start_polling(dp, skip_updates=True)







    
