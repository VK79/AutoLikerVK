from aiogram import Router, F
from aiogram.types import Message

router = Router()
bot =

@router.message(F.text == "/tag")
async def tag_user(message: Message):
    user_id = 1094254475  # ID из БД
    user_name = "Василий"  # Имя из БД

    text = f"Привет, <a href='tg://user?id={user_id}'>{user_name}</a>! 👋"
    await message.answer(text, parse_mode="HTML")
    await message.answer(-1094254475, text, parse_mode="HTML", message_thread_id=1,
                                disable_web_page_preview=True)
