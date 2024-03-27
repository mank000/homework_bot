class EnvironmentVariableError(Exception):
    """Исключение, связанное с переменными окружения."""
    pass


class RequestError(Exception):
    pass


class ResponseError(Exception):
    pass


class ParseError(Exception):
    pass


class SendMessageError(Exception):
    pass
