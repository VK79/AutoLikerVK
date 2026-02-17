import asyncio
from aiogram import Bot
from aiogram.types import Message

bot = Bot(token="6820629702:AAH-k48b43iZzgdhvwLhoT3Zb9_KkMjDqr0")



# ID чата (группа) и ID темы (message_thread_id)
chat_id = -1002097610688  # ID супергруппы
topic_id = 44  # ID темы (узнать: правой кнопкой на теме → ID темы)

mention = "["+'Марина'+"](tg://user?id="+str(1042944064)+")"

async def send_mess():
    # await bot.session.close()
    await bot.send_message(
        chat_id=chat_id,

        text=f"Сообщение в теме {mention}",
        parse_mode="Markdown",
        message_thread_id=topic_id  # Ключевой параметр!
    )
    await bot.session.close()

asyncio.run(send_mess())