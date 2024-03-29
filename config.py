RETRY_PERIOD = 600


def get_token(practicum_token):
    return {'Authorization': f'OAuth {practicum_token}'}
