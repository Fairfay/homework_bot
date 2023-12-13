import json
import logging
import os
import sys
import time

import requests
import telegram

from dotenv import load_dotenv


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(level=logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)

file_handler = logging.FileHandler('logfile.log')
file_handler.setLevel(logging.DEBUG)

logging.getLogger().addHandler(stream_handler)
logging.getLogger().addHandler(file_handler)


def check_tokens():
    """Проверка токенов на наличие.
    Если токен не найден, завершаем программу с критической ошибкой.
    """
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет текстовое сообщение в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено.')
    except telegram.TelegramError:
        logging.error('Сообщение не было отправлено.')


def get_api_answer(timestamp):
    """Запрос к API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()
        if response.status_code == 200:
            try:
                return response.json()
            except json.decoder.JSONDecodeError:
                logging.error('Ошибка преобразования типов данных.')
        else:
            logging.error(f'Нет доступа к ENDPOINT: {ENDPOINT}.'
                          f'Код ответа API: {response.status_code}.')
            raise AssertionError
    except requests.exceptions:
        logging.exception(f'Запрос не осуществлен {ENDPOINT}.')


def check_response(response):
    """Проверка ответа от API."""
    if not isinstance(response, dict):
        logging.error('Вернулся не словарь.')
        raise TypeError
    if 'current_date' in response and 'homeworks' in response:
        if not isinstance(response['homeworks'], list):
            logging.error('API не соответствует.')
            raise TypeError
        homeworks = response.get('homeworks')
        return homeworks
    else:
        logging.error("Некорректный ответ API.")
        raise KeyError


def parse_status(homework):
    """Извлекает информацию о статусе д/р из словаря."""
    if homework:
        homework_name = homework.get('homework_name')
        if not homework_name:
            logging.error(f'Пустой ответ: {homework_name}')
            raise KeyError
        homework_status = homework.get('status')
        if homework_status not in HOMEWORK_VERDICTS:
            logging.error(f'Неизвестный статус: {homework_status}.')
            raise KeyError
        verdict = HOMEWORK_VERDICTS[homework_status]
        return (f'Изменился статус проверки работы "{homework_name}"'
                f' - {verdict}')
    else:
        logging.error('Словарь пуст')
        raise KeyError


def main():
    """Основная логика работы."""
    if not check_tokens():
        logging.critical('Нет переменной')
        sys.exit(1)
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logging.debug('Нет новых статусов.')
                timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
