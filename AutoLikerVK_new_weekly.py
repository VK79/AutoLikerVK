import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import vk_api
from vk_api.utils import get_random_id
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO)



class VKActivityChecker:
    def __init__(self, config: Dict):
        self.vk_session = vk_api.VkApi(token=config['vk']['access_token'])
        self.vk_api = self.vk_session.get_api()
        self.group_id = config['vk']['group_id']
        self.users = config['users']
        self.bot = Bot(token=config['telegram']['bot_token'])
        self.scheduler = AsyncIOScheduler()

    def get_previous_week(self) -> Tuple[datetime, datetime]:
        """Получает понедельник и воскресенье предыдущей недели."""
        today = datetime.now()
        days_to_monday = today.weekday()  # 0=понедельник
        prev_monday = today - timedelta(days=days_to_monday + 7)
        prev_sunday = prev_monday + timedelta(days=6)
        return prev_monday.replace(hour=0, minute=0, second=0, microsecond=0), \
            prev_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

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
            return user_id in likes['users']
        except:
            return False

    def has_comment(self, user_id: int, post: Dict) -> bool:
        """Проверяет комментарий пользователя (простая проверка авторов)."""
        try:
            comments = self.vk_api.wall.getComments(owner_id=post['owner_id'],
                                                    post_id=post['id'], count=1000)
            user_comments = [c for c in comments['items'] if c.get('from_id') == user_id]
            return bool(user_comments)
        except:
            return False

    async def check_user_activity(self, name: str, vk_id: int, tg_id: int, posts: List[Dict]):
        """Проверяет активность пользователя и собирает проблемные посты."""
        missing = []
        for post in posts:
            link = f"https://vk.com/wall{post['owner_id']}_{post['id']}"
            has_l = self.has_like(vk_id, post)
            has_c = self.has_comment(vk_id, post)
            if not (has_l or has_c):
                what = []
                if not has_l:
                    what.append("лайк")
                if not has_c:
                    what.append("комментарий")
                missing.append(f"{', '.join(what)} на пост {link}")
        if missing:
            msg = f"Вы забыли {' или '.join(missing)}"
            await self.bot.send_message(tg_id, msg)
            logging.info(f"Уведомление отправлено {name}")

    async def weekly_report(self):
        """Основная функция отчета."""
        start, end = self.get_previous_week()
        start_ts, end_ts = int(start.timestamp()), int(end.timestamp())
        posts = self.get_week_posts(start_ts, end_ts)
        logging.info(f"Найдено {len(posts)} постов за неделю")

        for name, data in self.users.items():
            await self.check_user_activity(name, data['vk_id'], data['tg_id'], posts)

    async def run(self):
        """Запуск бота и планировщика."""
        # Планируем задачу на каждый понедельник 08:15
        trigger = CronTrigger(day_of_week='mon', hour=8, minute=15)
        self.scheduler.add_job(self.weekly_report, trigger)
        self.scheduler.start()
        logging.info("Планировщик запущен. Отчеты по понедельникам в 08:15")

        # Держим в работе
        while True:
            await asyncio.sleep(3600)  # Проверка каждый час


if __name__ == "__main__":
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    checker = VKActivityChecker(config)
    asyncio.run(checker.run())
