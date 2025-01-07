document.querySelectorAll('.password-input').forEach((input, index) => {
    input.addEventListener('input', (e) => {
        // Переход к следующему полю ввода
        if (index < 3 && input.value.length === 1) {
            document.querySelector(`#input${index + 2}`).focus();
        }

        // Когда все поля заполнены, собираем пароль и отправляем форму
        if (Array.from(document.querySelectorAll('.password-input')).every(input => input.value.length === 1)) {
            // Собираем пароль, соединяя значения из всех полей
            let password = Array.from(document.querySelectorAll('.password-input'))
                                 .map(input => input.value)  // Получаем все введенные символы
                                 .join('');  // Объединяем их в одну строку

            // Отправляем собранный пароль на сервер
            fetch('/check_password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',  // Указываем, что данные в формате формы
                },
                body: `password=${password}`  // Отправляем строку пароля
            })
            .then(response => {
                if (response.ok) {
                    // Если авторизация успешна, перенаправляем на страницу preloader
                    window.location.href = "/preloader";
                } else {
                    // Если ошибка (неправильный пароль), выводим сообщение
                    alert('Неверный пароль');
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
            });
        }
    });
});
