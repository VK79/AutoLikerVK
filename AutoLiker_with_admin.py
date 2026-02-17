import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any

import vk_api
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AddUserStates(StatesGroup):
    waiting_vk_id = State()
    waiting_tg_id = State()
    waiting_name = State()


class VKActivityChecker:
    def __init__(self, config: Dict):
        self.config_file = 'config.json'
        self.config = self._load_config()
        self.vk_session = vk_api.VkApi(token=self.config['vk']['access_token'])
        self.vk_api = self.vk_session.get_api()
        self.group_id = self.config['vk']['group_id']
        self.admin_tg_id = self.config['admin_tg_id']
        self.group_tg_id = self.config['group_tg_id']
        self.topic_tg_id = self.config['topic_tg_id']
        self.users = self.config['users']
        self.bot = Bot(token=self.config['telegram']['bot_token'])
        self.dp = Dispatcher(storage=MemoryStorage())
        self.router = Router()
        self.dp.include_router(self.router)
        self.scheduler = AsyncIOScheduler()
        self._setup_handlers()
        self._setup_scheduler()  # ✅ Планировщик по понедельникам

    def _load_config(self) -> Dict:
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_config(self):
        config = self._load_config()
        config['users'] = self.users
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    # def _setup_scheduler(self):
    #     """Добавляет задачу, но НЕ запускает (будет в run_bot)"""
    #     trigger = CronTrigger(day_of_week='mon', hour=8, minute=5, timezone='Europe/Moscow')
    #     self.scheduler.add_job(self._run_check, trigger)
    #     logger.info("📅 Задача добавлена: понедельник 08:05 MSK")


    def _setup_handlers(self):
        @self.router.message(Command('admin'), F.from_user.id == self.admin_tg_id)
        async def admin_panel(message: Message):
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="add_user")],
                [InlineKeyboardButton(text="📋 Список пользователей", callback_data="list_users")],
                [InlineKeyboardButton(text="🔍 Проверить неделю (СЕЙЧАС)", callback_data="check_week")],
                [InlineKeyboardButton(text="📅 Следующая проверка", callback_data="next_check")],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_admin")]
            ])
            await message.answer("🔧 Админ-панель\n📅 Авто: по понедельникам 08:05", reply_markup=kb)

    def _setup_scheduler(self):
        """Добавляет задачу с ИМЕНИМ"""
        trigger = CronTrigger(day_of_week='mon', hour=8, minute=5, timezone='Europe/Moscow')
        self.scheduler.add_job(
            self._run_check,
            trigger,
            id="weekly_vk_check",  # ✅ Уникальный ID
            replace_existing=True
        )
        logger.info("📅 Задача 'weekly_vk_check' добавлена")

        @self.router.callback_query(F.data == "next_check")
        async def next_check(call: CallbackQuery):
            try:
                job = self.scheduler.get_job("weekly_vk_check")  # По ID
                if job and job.next_run_time:
                    time_str = job.next_run_time.strftime("%d.%m.%Y %H:%M")
                    await call.message.answer(f"⏰ Понедельник: {time_str}")
                elif job:
                    await call.message.answer("⏰ Задача активна")
                else:
                    await call.message.answer("📅 Задача не найдена")
            except Exception:
                await call.message.answer("⏰ Планировщик не запущен")
            await call.answer()


        @self.router.callback_query(F.data == "add_user", F.from_user.id == self.admin_tg_id)
        async def start_add_user(call: CallbackQuery, state: FSMContext):
            await call.message.edit_text("👤 Введите VK ID пользователя:")
            await state.set_state(AddUserStates.waiting_vk_id)
            await call.answer()

        @self.router.message(AddUserStates.waiting_vk_id, F.from_user.id == self.admin_tg_id)
        async def process_vk_id(message: Message, state: FSMContext):
            await state.update_data(vk_id=int(message.text))
            await message.answer("📱 Введите TG ID пользователя:")
            await state.set_state(AddUserStates.waiting_tg_id)

        @self.router.message(AddUserStates.waiting_tg_id, F.from_user.id == self.admin_tg_id)
        async def process_tg_id(message: Message, state: FSMContext):
            await state.update_data(tg_id=int(message.text))
            await message.answer("📝 Введите имя пользователя:")
            await state.set_state(AddUserStates.waiting_name)

        @self.router.message(AddUserStates.waiting_name, F.from_user.id == self.admin_tg_id)
        async def process_name(message: Message, state: FSMContext):
            data = await state.get_data()
            vk_id = data['vk_id']
            tg_id = data['tg_id']
            name = message.text.strip()

            self.users[name] = {'vk_id': vk_id, 'tg_id': tg_id}
            self._save_config()

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{name}")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
            ])
            await message.answer(f"Подтвердите добавление:\n👤 {name}\nVK: {vk_id}\nTG: {tg_id}", reply_markup=kb)
            await state.clear()

        @self.router.callback_query(F.data.startswith("confirm_"))
        async def confirm_user(call: CallbackQuery):
            name = call.data.split("_", 1)[1]
            await call.answer(f"✅ Пользователь {name} добавлен!")
            await call.message.edit_text(f"✅ {name} добавлен в список.")

        @self.router.callback_query(F.data == "list_users")
        async def list_users(call: CallbackQuery):
            if not self.users:
                text = "📋 Список пуст"
            else:
                text = "📋 Пользователи:\n" + "\n".join(
                    [f"👤 {n}: VK{data['vk_id']} TG{data['tg_id']}" for n, data in self.users.items()])
            await call.message.edit_text(text)
            await call.answer()

        @self.router.callback_query(F.data == "check_week")
        async def trigger_check(call: CallbackQuery):
            await call.answer("🔍 Запуск проверки СЕЙЧАС...")
            asyncio.create_task(self._run_check())
            await call.message.edit_text("✅ Проверка запущена!\n📅 Авто: по понедельникам 08:05")

        @self.router.callback_query(F.data == "close_admin")
        async def close_admin(call: CallbackQuery):
            await call.message.delete()
            await call.answer()

    # Методы проверки (без изменений)
    def get_previous_week(self) -> Tuple[datetime, datetime]:
        today = datetime.now()
        days_to_monday = today.weekday()
        prev_monday = today - timedelta(days=days_to_monday + 7)
        prev_sunday = prev_monday + timedelta(days=6)
        return prev_monday.replace(hour=0, minute=0, second=0, microsecond=0), \
            today.replace(hour=23, minute=59, second=59, microsecond=999999)

    def get_week_posts(self, start_time: int, end_time: int) -> List[Dict]:
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
                    return posts
            offset += count
        return posts

    def has_like(self, user_id: int, post: Dict) -> bool:
        try:
            likes = self.vk_api.likes.getList(type='post', owner_id=post['owner_id'], item_id=post['id'], count=1000)
            return user_id in likes['users']
        except:
            return False

    def has_comment(self, user_id: int, post: Dict) -> bool:
        try:
            comments = self.vk_api.wall.getComments(owner_id=post['owner_id'], post_id=post['id'], count=1000)
            user_comments = [c for c in comments['items'] if c.get('from_id') == user_id]
            return bool(user_comments)
        except:
            return False

    async def check_user_activity(self, name: str, vk_id: int, tg_id: int, posts: List[Dict]):
        missing = []
        for post in posts:
            link = f"https://vk.com/wall{abs(post['owner_id'])}_{post['id']}"
            has_l = self.has_like(vk_id, post)
            has_c = self.has_comment(vk_id, post)
            if not (has_l or has_c):
                what = []
                if not has_l: what.append("👍 лайк")
                if not has_c: what.append("💬 комментарий")
                missing.append(f"{', '.join(what)} на пост {link}")

        if missing:
            tag_user = f'<a href="tg://user?id={tg_id}">{name}</a>'
            msg = f"{tag_user}\n❌ Вы забыли поставить:\n" + "\n".join(missing)
            try:
                await self.bot.send_message(
                    self.group_tg_id, msg,
                    parse_mode="HTML",
                    message_thread_id=self.topic_tg_id,
                    disable_web_page_preview=True
                )
                logger.info(f"✅ Уведомление {name}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки {name}: {e}")


    async def _run_check(self):
        try:
            start, end = self.get_previous_week()
            start_ts, end_ts = int(start.timestamp()), int(end.timestamp())
            posts = self.get_week_posts(start_ts, end_ts)
            logger.info(f"📊 Найдено {len(posts)} постов за неделю")

            for name, data in self.users.items():
                await self.check_user_activity(name, data['vk_id'], data['tg_id'], posts)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки: {e}")

    async def run_bot(self):
        """Запуск бота + scheduler"""
        try:
            self._setup_scheduler()  # ✅ ДО start()
            self.scheduler.start()  # ✅ Scheduler активен
            logger.info("🤖 Бот + планировщик запущены")
            await self.dp.start_polling(self.bot)
        finally:
            await self.bot.session.close()
            self.scheduler.shutdown()


if __name__ == "__main__":
    # pip install apscheduler
    checker = VKActivityChecker({})
    asyncio.run(checker.run_bot())
