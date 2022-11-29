from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

error_style = Style.from_dict(
    {
        "error": "#FF1820",
    }
)

create_pbar = Style.from_dict(
    {
        "percentage": "bg:#ffff00 #000000",
        "current": "#448844",
        "bar": "",
    }
)


def error(text: str):
    print_formatted_text(
        FormattedText([("class:error", f"Error: {text}")]), style=error_style
    )


def info(text: str):
    print_formatted_text(FormattedText([("class:info", f"{text}")]), style=error_style)
