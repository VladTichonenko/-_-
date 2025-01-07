import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Для хранения временных данных в сессии

# Функция для подключения к базе данных
def get_db_connection():
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    return conn


# Главная страница
@app.route('/')
def index():
    return render_template('index.html')


# Проверка пароля
@app.route('/check_password', methods=['POST'])
def check_password():
    password = request.form['password']
    print(f"Полученный пароль: {password}")

    # Подключаемся к базе данных
    conn = get_db_connection()
    cursor = conn.cursor()

    # Пытаемся найти ref_code в таблице users_stat
    cursor.execute("SELECT user_id, points FROM users_stat WHERE ref_code = ?", (password,))
    user = cursor.fetchone()

    if user:
        user_id = user['user_id']
        points = user['points']
        print(f"Пароль найден. user_id: {user_id}, points: {points}")

        # Получаем каналы, на которые подписан пользователь
        cursor.execute("""
            SELECT c.channel_name 
            FROM channels c
            JOIN subscribers s ON c.channel_id = s.channel_id
            WHERE s.user_id = ?
        """, (user_id,))
        channels = cursor.fetchall()

        # Сохраняем данные в сессии
        session['user_id'] = user_id
        session['points'] = points
        session['channels'] = [channel['channel_name'] for channel in channels]  # Сохраняем список каналов

        conn.close()

        # Перенаправляем на страницу preloader
        return redirect(url_for('preloader'))

    else:
        print("Пароль не найден.")
        conn.close()
        return redirect(url_for('index'))  # Если пароль неверный, вернемся на главную


# Страница preloader
@app.route('/preloader')
def preloader():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    # После 3 секунд автоматически переходим на glav
    return render_template('preloader.html')


# Страница главная (glav)
@app.route('/glav')
def glav():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session.get('user_id')
    points = session.get('points')
    channels = session.get('channels', [])

    return render_template('glav.html', user_id=user_id, points=points, channels=channels)


if __name__ == '__main__':
    app.run(debug=True)
