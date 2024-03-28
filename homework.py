import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import config
import exceptions


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
URL = config.URL

RETRY_PERIOD = config.RETRY_PERIOD
ENDPOINT = config.ENDPOINT
HEADERS = config.gettoken(PRACTICUM_TOKEN)

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
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Отсутствие обязательных переменных'
                        ' окружения во время запуска бота')
        raise exceptions.TokensError('Что-то с'
                                     ' переменными окружения.')


def send_message(bot, message):
    """Отправляет сообщение от бота."""
    try:
        sended_message = bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Удачная отправка сообщения: {sended_message}')
    except telegram.error.TelegramError as e:
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
    if not isinstance(response, dict):
        logger.error('Входящие данные переданы не в виде словаря.')
        raise TypeError('Входящие данные переданы не в виде словаря.')

    if not isinstance(response.get('homeworks'), list):
        logger.error('Входящие данные переданы не в виде списка.')
        raise TypeError('Входящие данные переданы не в виде списка.')


def parse_status(homework):
    """Извлекает статус о переданной домашней работе."""
    homework_name = homework.get('homework_name')

    if not isinstance(homework_name, str):
        raise TypeError('Ошибка извлечения'
                        ' информации о домашней работе.')

    if homework.get('status') not in HOMEWORK_VERDICTS:
        raise KeyError('Домашняя работа получена'
                       ' без статуса.')

    verdict = HOMEWORK_VERDICTS[homework.get('status')]

    return (f'Изменился статус проверки'
            f' работы "{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logger.debug('Бот начал свою работу.')
    timestamp = int(time.time())

    errors = ''
    answers = ''

    while True:
        try:

            # Получаем ответ от API
            response = get_api_answer(timestamp)
            check_response(response)
            timestamp = response.get('current_date', timestamp)

            if len(response.get('homeworks')) > 0:

                # Формируем сообщение, записываем статус последней дз,
                # Последней потому что если их несколько,
                # то программа выдаст ошибку.
                homework = response.get('homeworks')[0]
                message = parse_status(homework)
                answer = homework.get('status')

                # Если нет в моей коллекции ответа,
                # то можем отправить сообщение.
                if answer != answers:
                    send_message(bot, message)
                    answers = answer
                else:
                    logger.debug('В ответе нет новых результатов.')

                # Смотрим: если ответ это 'approved' или 'reviewing',
                # то обнуляем список.
                if answer in list(HOMEWORK_VERDICTS.keys())[:2]:
                    answers = answer
                    errors = ''
            else:
                logger.debug('Новые ДЗ не отправлены.'
                             ' Вернулся пустой список с ДЗ')

        except Exception as error:

            # Записываем ошибку для того, чтобы она не повторялась в сообщении.
            if str(error) != errors:
                message = f'Сбой в работе программы: {str(error)}'
                send_message(bot, message)
                errors = str(error)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':

    # Ctrl + C обработка
    try:
        main()
    except KeyboardInterrupt:
        print('Бот выключен.')
