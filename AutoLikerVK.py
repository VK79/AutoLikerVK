import vk_api
import time, datetime
import asyncio
from aiogram import Bot
from aiogram import Dispatcher
from config import token_vk, group_id, telegram_token, chat_id

# Инициализация сессии VK API
vk_session = vk_api.VkApi(token=token_vk)
# Получение экземпляра API
vk = vk_session.get_api()

bot = Bot(token=telegram_token)
#dp = Dispatcher(bot)


async def main():
    # Получение информации о текущем пользователе
    user_id = vk.users.get()[0]['id']
    # Вывод информации о пользователе
    print(user_id)
    print(group_id)
    print(f'Старт... {(datetime.datetime.today()).strftime("%d/%m/%y - %H:%M:%S")}')
    while True:
        try:
            # Получение списка постов в группе с учетом пагинации
            posts = vk.wall.get(owner_id=group_id, count=10)
            # Можно увеличить "count" в зависимости от вашей потребности

            # Счетчик для отслеживания количества поставленных лайков
            likes_count = 0
            commented = False
            liked = True
            commented_text = ''
            liked_text = ''
            # Проходим по всем постам и ставим лайки, если их нет
            for post in posts['items']:
                post_id = post['id']
                commented_text = ''
                liked_text = ''
                #print(post_id)
                comments = vk.wall.getComments(owner_id=group_id, post_id=post_id)['items']
                # Проверяем, есть ли уже лайк на посте
                likes = vk.likes.getList(type='post', owner_id=group_id, item_id=post_id)
                if user_id not in likes['items']:
                    try:
                        vk.likes.add(type='post', owner_id= group_id, item_id=post_id)
                        text = f'Лайк поставлен на пост https://vk.com/wall{group_id}_{post_id}'
                        await bot.send_message(chat_id, text, link_preview=False)
                    except:
                        liked = False
                        liked_text = 'Нужно поставить ЛАЙК\n'
                        print(liked_text)
                    likes_count += 1

                    # Если поставлено 10 лайков, делаем перерыв на 3 секунды
                    if likes_count == 10:
                        print('Поставлено 10 лайков. Делаем перерыв на 3 секунды.')
                        time.sleep(3)
                        likes_count = 0
                else:
                    liked = True
                for comment in comments:
                    # print(comment['from_id'])
                    if user_id == comment['from_id']:
                        commented = True
                        break
                    else:
                        commented_text = f'Нужно оставить КОММЕНТАРИЙ \n'
                        print(commented_text)
                if commented is not True or liked is not True:
                    text = f'{liked_text}{commented_text}на пост https://vk.com/wall{group_id}_{post_id}'
                    await bot.send_message(chat_id, text)

                time.sleep(1)
            # Добавляем задержку на 1 секунду перед следующей проверкой
            print(f'Все лайки проставлены. Ждем новых постов... {(datetime.datetime.today()).strftime("%d/%m/%y - %H:%M:%S")}')
            time.sleep(900)

        except Exception as e:
            print(f"Произошла ошибка: {e}")


if __name__ == '__main__':
    asyncio.run(main())