import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import vk_api
from aiogram import Bot


class VKActivityChecker:
    def __init__(self, config: Dict):
        self.vk_session = vk_api.VkApi(token=config['vk']['access_token'])
        self.vk_api = self.vk_session.get_api()
        self.group_id = config['vk']['group_id']
        self.users = config['users']
        self.bot = Bot(token=config['telegram']['bot_token'])

    def get_previous_week(self) -> Tuple[datetime, datetime]:
        """Получает понедельник и воскресенье предыдущей недели."""
        today = datetime.now()
        days_to_monday = today.weekday()  # 0=понедельник
        prev_monday = today - timedelta(days=days_to_monday + 7)
        prev_sunday = prev_monday + timedelta(days=6)
        # return prev_monday.replace(hour=0, minute=0, second=0, microsecond=0), \
        #     prev_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return prev_monday.replace(hour=0, minute=0, second=0, microsecond=0), \
            today.replace(hour=23, minute=59, second=59, microsecond=999999)

    def get_week_posts(self, start_time: int, end_time: int) -> List[Dict]:
        """Получает посты группы за неделю."""
        posts = []
        offset = 0
        count = 100
        while True:
            res = self.vk_api.wall.get(owner_id=self.group_id, offset=offset, count=count)
            if not res['items']:
                break
            for post in res['items']:
                if post['date'] >= start_time:
                    if start_time <= post['date'] <= end_time:
                        posts.append(post)
                else:
                    return posts  # Посты отсортированы по дате
            offset += count
        return posts

    def has_like(self, user_id: int, post: Dict) -> bool:
        """Проверяет лайк пользователя на посте."""
        try:
            likes = self.vk_api.likes.getList(type='post', owner_id=post['owner_id'],
                                              item_id=post['id'], count=1000)
            return user_id in likes['items']
        except:
            return False

    def has_comment(self, user_id: int, post: Dict) -> bool:
        """Проверяет комментарий пользователя."""
        try:
            comments = self.vk_api.wall.getComments(owner_id=post['owner_id'],
                                                    post_id=post['id'], count=1000)
            user_comments = [c for c in comments['items'] if c.get('from_id') == user_id]
            return bool(user_comments)
        except:
            return False

    async def check_user_activity(self, name: str, vk_id: int, tg_id: int, posts: List[Dict]):
        """Проверяет активность и отправляет уведомление."""
        missing = []
        for post in posts:
            has_l, has_c = False, False
            link = f"https://vk.com/wall{post['owner_id']}_{post['id']}"
            has_l = self.has_like(vk_id, post)
            has_c = self.has_comment(vk_id, post)
            print(post['id'], link, has_l, has_c)
            if (has_l is False or has_c is False):
                what = []
                if has_l is False:
                    what.append("👍лайк")
                if has_c is False:
                    what.append("💬коммент")
                missing.append(f"{', '.join(what)} на пост {link}")
                # print(missing)
        if missing:
            msg = f"Вы забыли поставить\n{',\n'.join(missing)}"
            await self.bot.send_message(tg_id, msg, disable_web_page_preview=True)
            print(f"Уведомление отправлено {name}")

    async def run_check(self):
        """Запуск проверки за предыдущую неделю."""
        start, end = self.get_previous_week()
        start_ts, end_ts = int(start.timestamp()), int(end.timestamp())
        posts = self.get_week_posts(start_ts, end_ts)
        print(f"Найдено {len(posts)} постов с {start.strftime('%d.%m %H:%M:%S')} по {end.strftime('%d.%m %H:%M:%S')}")

        for name, data in self.users.items():
            await self.check_user_activity(name, data['vk_id'], data['tg_id'], posts)

        await self.bot.session.close()


if __name__ == "__main__":
    import asyncio

    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    checker = VKActivityChecker(config)
    asyncio.run(checker.run_check())
