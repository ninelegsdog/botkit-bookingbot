from aiogram.types import Message


def is_command(text: str | None) -> bool:
    return bool(text) and text is not None and text.startswith("/")


def text_not_command(message: Message) -> bool:
    return not is_command(message.text)
