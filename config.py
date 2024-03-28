URL = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
RETRY_PERIOD = 600


def gettoken(practicum_token):
    return {'Authorization': f'OAuth {practicum_token}'}
