from aiogram.types import InlineKeyboardMarkup


def empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])
