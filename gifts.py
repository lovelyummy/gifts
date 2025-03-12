import asyncio
import logging
import os
import time
import random
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.methods import GetAvailableGifts, CreateNewStickerSet, SendSticker
from aiogram.types import Gifts, InputFile, InputSticker

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
USER_ID = int(os.getenv("USER_ID"))  # ID пользователя, который будет владельцем набора стикеров
BOT_USERNAME = os.getenv("BOT_USERNAME")  # Имя вашего бота (без @)

if not BOT_TOKEN or not CHANNEL_ID or not USER_ID or not BOT_USERNAME:
    logging.error("Не удалось загрузить токен, ID канала, USER_ID или BOT_USERNAME из .env файла.")
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


async def create_sticker_set_from_gifts(gifts):
    """
    Создает набор стикеров из подарков.
    """
    try:
        stickers = []
        for gift in gifts:
            # Определяем формат стикера
            sticker_format = "animated" if gift.sticker.is_animated else "static"

            # Создаем объект InputSticker
            stickers.append(InputSticker(
                sticker=gift.sticker.file_id,  # Используем file_id стикера
                emoji_list=[gift.sticker.emoji],  # Используем эмодзи стикера
                format=sticker_format  # Указываем формат стикера
            ))

        # Генерируем уникальное имя набора стикеров
        random_suffix = random.randint(1000, 9999)  # Добавляем случайное число
        sticker_set_name = f"test2423ksj_{random_suffix}_by_{BOT_USERNAME}"  # Уникальное имя набора

        # Создаем набор стикеров
        await bot(CreateNewStickerSet(
            user_id=USER_ID,
            name=sticker_set_name,  # Имя набора стикеров
            title="Gift Stickers",  # Заголовок набора
            stickers=stickers,  # Список стикеров
            sticker_type="regular"  # Тип набора (обычные стикеры)
        ))
        logger.info(f"Набор стикеров '{sticker_set_name}' успешно создан.")
        return sticker_set_name
    except Exception as e:
        logger.error(f"Ошибка при создании набора стикеров: {e}")
        return None


async def send_stickers_from_set(sticker_set_name):
    """
    Отправляет стикеры из набора в указанный чат.
    """
    try:
        # Получаем информацию о наборе стикеров
        sticker_set = await bot.get_sticker_set(name=sticker_set_name)

        # Отправляем каждый стикер в чат
        for sticker in sticker_set.stickers:
            await bot(SendSticker(chat_id=CHANNEL_ID, sticker=sticker.file_id))
            logger.info(f"Стикер {sticker.file_id} отправлен в чат {CHANNEL_ID}.")
    except Exception as e:
        logger.error(f"Ошибка при отправке стикеров: {e}")


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

        # Создаем набор стикеров из всех доступных подарков
        sticker_set_name = await create_sticker_set_from_gifts(new_gifts)
        if sticker_set_name:
            await send_stickers_from_set(sticker_set_name)
    elif new_gifts:
        await asyncio.gather(*(send_gift_info(gift) for gift in new_gifts))
        logger.info(f"Обнаружены новые подарки: {[gift.id for gift in new_gifts]}")

        # Создаем набор стикеров из новых подарков
        sticker_set_name = await create_sticker_set_from_gifts(new_gifts)
        if sticker_set_name:
            await send_stickers_from_set(sticker_set_name)
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
