from click import ClickException


def standard_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:  # noqa
            ce = ClickException(message=str(e))
            raise ce

    return wrapper
