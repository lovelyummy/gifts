import asyncio
import logging
import os
import time
import json
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.methods import GetAvailableGifts, CreateNewStickerSet, AddStickerToSet, SendSticker, GetStickerSet
from aiogram.types import Gifts, InputSticker

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
USER_ID = int(os.getenv("USER_ID"))
BOT_USERNAME = os.getenv("BOT_USERNAME")

STICKER_SET_NAME = f"GiftsNotice1_by_{BOT_USERNAME}"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("gift_checker.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

known_gifts = {}

# Загружаем сохраненные ID подарков из файла
def load_known_gifts():
    if os.path.exists("known_gifts.json"):
        with open("known_gifts.json", "r") as f:
            return json.load(f)
    return {}

# Сохраняем подарки в файл
def save_known_gifts():
    with open("known_gifts.json", "w") as f:
        json.dump(known_gifts, f)

async def sticker_set_exists(name):
    """Проверяет существование стикерпака."""
    try:
        await bot(GetStickerSet(name=name))
        return True
    except:
        return False

async def create_sticker_set_from_gifts(gifts):
    """Создаёт стикерпак, если его нет."""
    stickers = [InputSticker(sticker=gift.sticker.file_id, emoji_list=[gift.sticker.emoji], format="static") for gift in gifts]
    try:
        await bot(CreateNewStickerSet(user_id=USER_ID, name=STICKER_SET_NAME, title="Gift Stickers", stickers=stickers, sticker_type="regular"))
        logger.info(f"Стикерпак '{STICKER_SET_NAME}' создан.")
    except Exception as e:
        logger.error(f"Ошибка создания стикерпака: {e}")

async def add_stickers_to_set(gifts):
    """Добавляет новые стикеры в существующий стикерпак."""
    for gift in gifts:
        try:
            sticker = InputSticker(sticker=gift.sticker.file_id, emoji_list=[gift.sticker.emoji], format="static")
            await bot(AddStickerToSet(user_id=USER_ID, name=STICKER_SET_NAME, sticker=sticker))
            logger.info(f"Стикер {gift.sticker.file_id} добавлен в {STICKER_SET_NAME}.")
        except Exception as e:
            logger.error(f"Ошибка добавления стикера {gift.sticker.file_id}: {e}")

async def send_stickers_from_set():
    """Отправляет стикеры из набора."""
    try:
        sticker_set = await bot(GetStickerSet(name=STICKER_SET_NAME))
        for sticker in sticker_set.stickers:
            await bot(SendSticker(chat_id=CHANNEL_ID, sticker=sticker.file_id))
            logger.info(f"Отправлен стикер {sticker.file_id}.")
    except Exception as e:
        logger.error(f"Ошибка отправки стикеров: {e}")

async def send_notification(message: str):
    """Отправляет текстовое уведомление в канал и возвращает объект сообщения."""
    try:
        # Отправляем сообщение с использованием HTML-разметки, но без тега <br>
        post_message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message.replace('<br>', '\n'),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info("Отправлено текстовое сообщение.")
        return post_message  # Возвращаем объект сообщения
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        return None


async def check_for_upgrades():
    """Проверка апгрейдов."""
    try:
        # Здесь можно добавить логику для проверки апгрейдов, например, изменения команд бота
        upgrades = await bot.get_my_commands()  # Пример проверки команд
        if upgrades:
            logger.info("Обнаружены апгрейды.")
            # Формируем сообщение об апгрейде
            await send_notification(f"<b>🚀 Обнаружены апгрейды:</b> <i>{', '.join([cmd.command for cmd in upgrades])}</i>")
        else:
            logger.info("Апгрейдов нет.")
    except Exception as e:
        logger.error(f"Ошибка при проверке апгрейдов: {e}")

async def check_new_gifts():
    global known_gifts
    current_gifts = await bot(GetAvailableGifts())
    new_gifts = [gift for gift in current_gifts.gifts if gift.id not in known_gifts]

    # Обновляем список известных подарков
    known_gifts.update({gift.id: time.time() for gift in new_gifts})

    # Сохраняем обновленные данные
    save_known_gifts()

    if new_gifts:
        logger.info(f"Обнаружены новые подарки.")

        # Формируем текстовое сообщение о новых подарках без emoji и ID
        gift_info = "\n\n".join(
            f"<b>Новый подарок:</b> {gift.title if hasattr(gift, 'title') else 'Без названия'}\n"
            f"<b>Звезды:</b> {gift.star_count}\n"
            f"<b>Осталось:</b> {gift.remaining_count if gift.remaining_count else '∞'}" for gift in new_gifts
        )

        # Отправляем текстовое сообщение и получаем объект сообщения
        post_message = await send_notification(f"<b>🎉 Новые подарки:</b><br>{gift_info}")

        if post_message is not None:
            # Получаем ID поста с подарками
            post_message_id = post_message.message_id

            # Отправляем стикеры в комментариях к посту
            await send_stickers_in_comments(post_message_id)

            if not await sticker_set_exists(STICKER_SET_NAME):
                await create_sticker_set_from_gifts(new_gifts)
            else:
                await add_stickers_to_set(new_gifts)

            await send_stickers_from_set()
        else:
            logger.error("Не удалось отправить сообщение с новыми подарками.")
    else:
        logger.info("Новых подарков нет.")


async def send_stickers_in_comments(post_message_id):
    """Отправляет стикеры в комментариях к посту."""
    try:
        sticker_set = await bot(GetStickerSet(name=STICKER_SET_NAME))  # Получаем стикерпак
        for sticker in sticker_set.stickers:  # Проходим по всем стикерам в паке
            # Отправляем стикер как комментарий к посту, используя reply_to_message_id
            await bot(SendSticker(
                chat_id=CHANNEL_ID,
                sticker=sticker.file_id,
                reply_to_message_id=post_message_id  # Указываем ID сообщения, к которому будет комментарий
            ))
            logger.info(f"Отправлен стикер {sticker.file_id} в комментарий к посту с ID {post_message_id}.")
    except Exception as e:
        logger.error(f"Ошибка отправки стикеров в комментарии: {e}")

async def main():
    global known_gifts
    logger.info("Запуск бота...")

    # Загружаем подарки из файла при запуске бота
    known_gifts = load_known_gifts()

    while True:
        await check_new_gifts()  # Проверка новых подарков
        await check_for_upgrades()  # Проверка апгрейдов
        await asyncio.sleep(10)  # Пауза между проверками

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
