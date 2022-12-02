from cli import console


def standard_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:  # noqa
            console.error(str(e))

    return wrapper
