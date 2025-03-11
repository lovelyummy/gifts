import asyncio
import logging
import os
import time
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.methods import GetAvailableGifts
from aiogram.types import Gifts, InputFile

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    logging.error("Не удалось загрузить токен или ID канала из .env файла.")
    exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("gift_checker.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словарь для хранения известных подарков
known_gifts = {}
first_run = True


async def get_available_gifts():
    try:
        result: Gifts = await bot(GetAvailableGifts())
        logger.info(f"Запрос подарков: получено {len(result.gifts)} штук.")
        return result.gifts
    except Exception as e:
        logger.error(f"Ошибка при получении подарков: {e}")
        return []


async def send_notification(message: str):
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
    except Exception as e:
        if 'retry after' in str(e).lower():
            retry_seconds = int(str(e).split('retry after ')[-1].split()[0])
            logger.warning(f"Flood control exceeded, retrying in {retry_seconds} seconds...")
            await asyncio.sleep(retry_seconds)
            await send_notification(message)
        else:
            logger.error(f"Ошибка при отправке уведомления: {e}")


async def send_gift_info(gift):
    try:
        gift_info = (
            f"🎁 Новый Подарок 🔴: {gift.title if hasattr(gift, 'title') else 'Без названия'}\n"
            f"  Эмодзи: {gift.sticker.emoji}\n"
            f"  Звезд: {gift.star_count}\n"
            f"  Осталось: {gift.remaining_count if gift.remaining_count else '∞'}\n"
            f"ID: {gift.id}\n"
        )
        await send_notification(gift_info)

        if gift.sticker and hasattr(gift.sticker, 'file_id'):
            await bot.send_sticker(chat_id=CHANNEL_ID, sticker=gift.sticker.file_id)
        elif gift.sticker and hasattr(gift.sticker, 'file_path'):
            await bot.send_sticker(chat_id=CHANNEL_ID, sticker=InputFile(gift.sticker.file_path))
    except Exception as e:
        logger.error(f"Ошибка при отправке информации о подарке: {e}")


async def check_new_gifts():
    global known_gifts, first_run
    current_gifts = await get_available_gifts()
    current_gift_ids = {gift.id for gift in current_gifts}

    new_gifts = [gift for gift in current_gifts if gift.id not in known_gifts]
    known_gifts.update({gift.id: time.time() for gift in new_gifts})

    if first_run and new_gifts:
        first_run = False
        all_gifts_info = "🎉 Доступные подарки:\n\n" + "\n\n".join(
            f"🎁 {gift.title if hasattr(gift, 'title') else 'Без названия'}\n"
            f"  Эмодзи: {gift.sticker.emoji}\n"
            f"  Звезд: {gift.star_count}\n"
            f"  Осталось: {gift.remaining_count if gift.remaining_count else '∞'}\n"
            f"ID: {gift.id}"
            for gift in new_gifts
        )
        await send_notification(all_gifts_info)
        logger.info("Первый запуск: отправлены все доступные подарки.")
    elif new_gifts:
        await asyncio.gather(*(send_gift_info(gift) for gift in new_gifts))
        logger.info(f"Обнаружены новые подарки: {[gift.id for gift in new_gifts]}")
    else:
        logger.info("Новых подарков нет.")


async def main():
    logger.info("Запуск бота...")
    while True:
        await check_new_gifts()
        await asyncio.sleep(10)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
