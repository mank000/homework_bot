import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
URL = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

RETRY_PERIOD = 600
# При периодических запросах к API можно использовать значение,
# полученное в ответе под ключом current_date, в качестве
# параметра from_date в следующем запросе.
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logging.basicConfig(
    level=logging.DEBUG,
    encoding='windows-1251',
    filename='program.log',
    format='%(asctime)s - [%(levelname)s] - %(message)s',
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяем доступность переменных окружения."""
    if (PRACTICUM_TOKEN is None
            and TELEGRAM_TOKEN is None
            and TELEGRAM_CHAT_ID is None):
        logger.critical('Отсутствие обязательных переменных'
                        ' окружения во время запуска бота')
        raise ValueError('Что-то с'
                         ' переменными окружения.')


def send_message(bot, message):
    """Отправляет сообщение от бота."""
    try:
        sended_message = bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Удачная отправка сообщения: {sended_message}')
    except Exception as e:
        logger.error(f'Ошибка отправки сообщения: {e}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(URL, headers=HEADERS, params=payload)

        if response.status_code != HTTPStatus.OK:
            logger.error('Недоступность эндпоинта Яндекса.')
            raise requests.RequestException(f'Статус ошибки: '
                                            f'{response.status_code}')

    except requests.ConnectionError:
        logger.error('Ошибка подключения к сети.')
        raise ConnectionAbortedError('Ошибка подключения к сети.')

    except requests.Timeout as t:
        logger.error(f'Timed-out. {t}')
        raise TimeoutError(f'Timed-out. {t}')

    except requests.RequestException:
        logger.error('Неизвестная ошибка')
        raise exceptions.RequestError('Неизвестная ошибка.')
    logger.debug('Бот успешно получил ответ.')
    return response.json()


def check_response(response):
    """Проверяет API Практикума на соответствие с документацией."""
    if type(response) != dict:
        logger.error('Входящие данные переданы не в виде словаря.')
        raise TypeError('Входящие данные переданы не в виде словаря.')

    if type(response.get('homeworks')) != list:
        logger.error('Входящие данные переданы не в виде списка.')
        raise TypeError('Входящие данные переданы не в виде списка.')


def parse_status(homework):
    """Извлекает статус о переданной домашней работе."""
    try:
        homework_name = homework.get('homework_name')

        if type(homework_name) != str:
            raise TypeError('Ошибка извлечения'
                            ' информации о домашней работе.')

        if homework.get('status') not in list(HOMEWORK_VERDICTS.keys()):
            raise KeyError('Домашняя работа получена'
                           ' без статуса.')

        verdict = HOMEWORK_VERDICTS[homework.get('status')]

        return (f'Изменился статус проверки'
                f' работы "{homework_name}". {verdict}')
    except Exception as e:
        logger.error('Ошибка извлечения информации'
                     ' о домашней работе.' + str(e))
        raise exceptions.ParseError('Ошибка извлечения информации о'
                                    ' домашней работе.' + str(e))


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    errors = set()
    answers = set()

    while True:
        try:
            logger.debug('Бот начал свою работу.')
            # Получаем ответ от API
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            timestamp = response.get('current_date')

            # Формируем сообщение, записываем статус последней дз,
            # Последней потому что если их несколько,
            # то программа выдаст ошибку.
            message = parse_status(response.get('homeworks')[0])
            answer = homeworks[0].get('status')
            print(parse_status(response.get('homeworks')[0]))

            # Если нет в моей коллекции ответа,
            # то можем отправить сообщение.
            if answer not in answers:
                try:
                    send_message(bot, message)
                except telegram.error.TelegramError:
                    pass
                answers.add(answer)
            else:
                logger.debug('В ответе нет новых результатов.')

            # Смотрим: если ответ это 'approved' или 'reviewing',
            # то обнуляем список.
            if answer in list(HOMEWORK_VERDICTS.keys())[:2]:
                answers.clear()
                errors.clear()
                answers.add(answer)

        except Exception as error:
            # Записываем ошибку для того, чтобы она не повторялась в сообщении.

            if str(error) not in errors:
                message = f'Сбой в работе программы: {str(error)}'
                try:
                    send_message(bot, message)
                except telegram.error.TelegramError:
                    pass
                errors.add(str(error))

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
