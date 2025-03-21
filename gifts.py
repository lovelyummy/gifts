import os
import json
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.methods import GetAvailableGifts, CreateNewStickerSet, AddStickerToSet, SendSticker, GetStickerSet
from aiogram.types import Gifts, InputSticker, Message, StickerSet
from aiogram.exceptions import TelegramAPIError

# Загружаем переменные из .env
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
USER_ID = int(os.getenv("USER_ID"))
BOT_USERNAME = os.getenv("BOT_USERNAME")

STICKER_SET_NAME = f"GiftsNoticenew_by_{BOT_USERNAME}"  # Название стикерпака
STICKERS_FILE = "stickers.json"  # Файл для хранения информации о стикерах
KNOWN_GIFTS_FILE = "known_gifts.json"  # Файл для хранения информации о подарках
NOTIFIED_GIFTS_FILE = "notified_gifts.json"  # Файл для хранения информации об уведомлениях
GIFTS_STATE_FILE = "gifts_state.json"  # Файл для хранения текущего состояния подарков

# Задержка между сообщениями
DELAY_BETWEEN_MESSAGES = 2  # Задержка в 2 секунды

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
stickers_data = {}  # Словарь для хранения информации о стикерах
notified_gifts = {"threshold": {}, "sold_out": {}}  # Словарь для хранения информации об уведомлениях

# Инициализация файла для уведомлений
def initialize_notified_gifts():
    """Инициализирует файл для хранения уведомлений, если он не существует."""
    if not os.path.exists(NOTIFIED_GIFTS_FILE):
        with open(NOTIFIED_GIFTS_FILE, "w") as f:
            json.dump({"threshold": {}, "sold_out": {}}, f)  # Создаём файл с пустой структурой

# Загружаем данные о подарках из файла
def load_known_gifts():
    """Загружает данные о подарках из known_gifts.json."""
    if os.path.exists(KNOWN_GIFTS_FILE):
        with open(KNOWN_GIFTS_FILE, "r") as f:
            return json.load(f)
    return {}

# Сохраняем данные о подарках в файл
def save_known_gifts():
    """Сохраняет данные о подарках в known_gifts.json."""
    with open(KNOWN_GIFTS_FILE, "w") as f:
        json.dump(known_gifts, f, indent=4)

# Загружаем данные о стикерах из файла
def load_stickers_data():
    """Загружает данные о стикерах из stickers.json."""
    if os.path.exists(STICKERS_FILE):
        with open(STICKERS_FILE, "r") as f:
            return json.load(f)
    return {}

# Сохраняем данные о стикерах в файл
def save_stickers_data():
    """Сохраняет данные о стикерах в stickers.json."""
    with open(STICKERS_FILE, "w") as f:
        json.dump(stickers_data, f, indent=4)

# Загружаем данные об уведомлениях из файла
def load_notified_gifts():
    """Загружает данные об уведомлениях из notified_gifts.json."""
    if os.path.exists(NOTIFIED_GIFTS_FILE):
        with open(NOTIFIED_GIFTS_FILE, "r") as f:
            return json.load(f)
    return {"threshold": {}, "sold_out": {}}  # Возвращаем пустую структуру, если файла нет

# Сохраняем данные об уведомлениях в файл
def save_notified_gifts():
    """Сохраняет данные об уведомлениях в notified_gifts.json."""
    with open(NOTIFIED_GIFTS_FILE, "w") as f:
        json.dump(notified_gifts, f, indent=4)

# Загружаем текущее состояние подарков из файла
def load_gifts_state():
    """Загружает текущее состояние подарков из файла."""
    if os.path.exists(GIFTS_STATE_FILE):
        with open(GIFTS_STATE_FILE, "r") as f:
            return json.load(f)
    return {}  # Возвращаем пустой словарь, если файла нет

# Сохраняем текущее состояние подарков в файл
def save_gifts_state(gifts_state):
    """Сохраняет текущее состояние подарков в файл."""
    with open(GIFTS_STATE_FILE, "w") as f:
        json.dump(gifts_state, f, indent=4)

# Проверяем существование стикерпака
async def sticker_set_exists(name):
    """Проверяет существование стикерпака."""
    try:
        await bot(GetStickerSet(name=name))
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке существования стикерпака: {e}")
        return False

# Получаем актуальный file_id стикера из стикерпака
async def get_sticker_file_id(sticker_set_name, sticker_emoji):
    """Получает file_id стикера из стикерпака по emoji."""
    try:
        sticker_set = await bot(GetStickerSet(name=sticker_set_name))
        for sticker in sticker_set.stickers:
            if sticker.emoji == sticker_emoji:
                return sticker.file_id
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении стикерпака: {e}")
        return None

# Создаём стикерпак, если его нет
async def create_sticker_set_from_gifts(gifts):
    """Создаёт стикерпак, если его нет."""
    stickers = [InputSticker(sticker=gift.sticker.file_id, emoji_list=[gift.sticker.emoji], format="static") for gift in gifts]
    try:
        await bot(CreateNewStickerSet(
            user_id=USER_ID,
            name=STICKER_SET_NAME,
            title="Gift Stickers",
            stickers=stickers,
            sticker_type="regular"
        ))
        logger.info(f"Стикерпак '{STICKER_SET_NAME}' создан.")

        # Получаем актуальные file_id стикеров из стикерпака
        for gift in gifts:
            file_id = await get_sticker_file_id(STICKER_SET_NAME, gift.sticker.emoji)
            if file_id:
                stickers_data[str(gift.id)] = file_id  # Сохраняем file_id по id подарка
                logger.info(f"Стикер для подарка {gift.id} сохранён с file_id: {file_id}")
            else:
                logger.error(f"Не удалось получить file_id для стикера подарка {gift.id}.")

        save_stickers_data()  # Сохраняем данные в файл
        logger.info(f"Данные о стикерах сохранены в {STICKERS_FILE}.")
    except TelegramAPIError as e:
        if "Too Many Requests" in str(e):
            retry_after = int(e.message.split("retry after ")[1])
            logger.warning(f"Лимит запросов превышен. Ждём {retry_after} секунд...")
            await asyncio.sleep(retry_after)
            await create_sticker_set_from_gifts(gifts)  # Повторяем запрос после паузы
        else:
            logger.error(f"Ошибка создания стикерпака: {e}")
    except Exception as e:
        logger.error(f"Ошибка создания стикерпака: {e}")

# Добавляем новые стикеры в существующий стикерпак
async def add_stickers_to_set(gifts):
    """Добавляет новые стикеры в существующий стикерпак."""
    for gift in gifts:
        gift_id = str(gift.id)  # Получаем ID подарка
        logger.info(f"Обработка подарка с ID: {gift_id}")

        if gift_id not in stickers_data:
            try:
                # Проверяем, существует ли уже стикер с таким file_id
                existing_sticker = next((sticker for sticker in stickers_data.values() if sticker == gift.sticker.file_id), None)
                if existing_sticker:
                    logger.info(f"Стикер для подарка {gift_id} уже существует в стикерпаке.")
                    continue

                logger.info(f"Добавление стикера для подарка {gift_id} с file_id: {gift.sticker.file_id}")
                sticker = InputSticker(sticker=gift.sticker.file_id, emoji_list=[gift.sticker.emoji], format="static")
                await bot(AddStickerToSet(
                    user_id=USER_ID,
                    name=STICKER_SET_NAME,
                    sticker=sticker
                ))
                # Получаем актуальный file_id стикера из стикерпака
                file_id = await get_sticker_file_id(STICKER_SET_NAME, gift.sticker.emoji)
                if file_id:
                    stickers_data[gift_id] = file_id  # Сохраняем file_id по id подарка
                    logger.info(f"Стикер для подарка {gift_id} добавлен с file_id: {file_id}.")
                else:
                    logger.error(f"Не удалось получить file_id для стикера подарка {gift_id}.")
            except TelegramAPIError as e:
                if "Too Many Requests" in str(e):
                    retry_after = int(e.message.split("retry after ")[1])
                    logger.warning(f"Лимит запросов превышен. Ждём {retry_after} секунд...")
                    await asyncio.sleep(retry_after)
                    await add_stickers_to_set([gift])  # Повторяем запрос после паузы
                else:
                    logger.error(f"Ошибка добавления стикера для подарка {gift_id}: {e}")
            except Exception as e:
                logger.error(f"Ошибка добавления стикера для подарка {gift_id}: {e}")
        else:
            logger.info(f"Стикер для подарка {gift_id} уже существует в стикерпаке.")

    save_stickers_data()  # Сохраняем данные в файл
    logger.info(f"Данные о стикерах обновлены в {STICKERS_FILE}.")

# Отправляем стикер и получаем его message_id
async def send_sticker(chat_id, sticker_file_id):
    """Отправляет стикер и возвращает его message_id."""
    try:
        message = await bot(SendSticker(
            chat_id=chat_id,
            sticker=sticker_file_id
        ))
        logger.info(f"Стикер {sticker_file_id} успешно отправлен.")
        return message.message_id  # Возвращаем message_id стикера
    except TelegramAPIError as e:
        if "Too Many Requests" in str(e):
            retry_after = int(e.message.split("retry after ")[1])
            logger.warning(f"Лимит запросов превышен. Ждём {retry_after} секунд...")
            await asyncio.sleep(retry_after)
            return await send_sticker(chat_id, sticker_file_id)  # Повторяем запрос после паузы
        else:
            logger.error(f"Ошибка при отправке стикера {sticker_file_id}: {e}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при отправке стикера {sticker_file_id}: {e}")
        return None

# Отправляем текст как reply к стикеру
async def send_text_as_reply(chat_id, text, reply_to_message_id):
    """Отправляет текстовое сообщение как reply к указанному message_id."""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            parse_mode="HTML"
        )
        logger.info(f"Текстовое сообщение отправлено как reply к сообщению с ID {reply_to_message_id}.")
    except TelegramAPIError as e:
        if "Too Many Requests" in str(e):
            retry_after = int(e.message.split("retry after ")[1])
            logger.warning(f"Лимит запросов превышен. Ждём {retry_after} секунд...")
            await asyncio.sleep(retry_after)
            await send_text_as_reply(chat_id, text, reply_to_message_id)  # Повторяем запрос после паузы
        else:
            logger.error(f"Ошибка при отправке текстового сообщения: {e}")
    except Exception as e:
        logger.error(f"Ошибка при отправке текстового сообщения: {e}")

# Проверяем, достиг ли подарок порога в 11% или полностью раскуплен
async def check_gift_threshold(gift):
    """Проверяет, достиг ли подарок порога в 11% или полностью раскуплен."""
    gift_id = str(gift.id)
    total_count = gift.total_count
    remaining_count = gift.remaining_count

    # Игнорируем подарки с бесконечным количеством
    if total_count is None or total_count == 0:
        return

    # Проверяем, достиг ли подарок порога в 11%
    threshold = total_count * 0.11  # Порог в 11%
    if remaining_count <= threshold and gift_id not in notified_gifts["threshold"]:
        # Уведомляем о достижении порога
        notification_text = (
            f"⚠️ <b>Gift low supply ALERT!</b>\n"
            f"<b>ID:</b> <code>{gift_id}</code>\n"
            f"<b>Осталось:</b> <code>{remaining_count}/{total_count}</code>"
        )
        # Отправляем уведомление в канал
        sticker_file_id = stickers_data.get(gift_id)
        if sticker_file_id:
            sticker_message_id = await send_sticker(CHANNEL_ID, sticker_file_id)
            if sticker_message_id:
                await send_text_as_reply(CHANNEL_ID, notification_text, sticker_message_id)
        else:
            logger.error(f"Стикер для подарка {gift_id} не найден в stickers.json.")

        # Сохраняем информацию об уведомлении
        notified_gifts["threshold"][gift_id] = True
        save_notified_gifts()
        logger.info(f"Уведомление о пороге 11% для подарка {gift_id} сохранено.")

    # Проверяем, раскуплен ли подарок
    if remaining_count == 0 and gift_id not in notified_gifts["sold_out"]:
        # Уведомляем о том, что подарок раскуплен
        notification_text = (
            f"🛑 <b>Gift SOLD!</b>\n"
            f"<b>ID:</b> <code>{gift_id}</code>"
        )
        # Отправляем уведомление в канал
        sticker_file_id = stickers_data.get(gift_id)
        if sticker_file_id:
            sticker_message_id = await send_sticker(CHANNEL_ID, sticker_file_id)
            if sticker_message_id:
                await send_text_as_reply(CHANNEL_ID, notification_text, sticker_message_id)
        else:
            logger.error(f"Стикер для подарка {gift_id} не найден в stickers.json.")

        # Сохраняем информацию об уведомлении
        notified_gifts["sold_out"][gift_id] = True
        save_notified_gifts()
        logger.info(f"Уведомление о раскупленности для подарка {gift_id} сохранено.")

# Проверяем новые апгрейды
async def check_for_upgrades(current_gifts):
    """Проверяет, есть ли новые апгрейды подарков."""
    gifts_state = load_gifts_state()  # Загружаем текущее состояние
    new_upgrades = []

    for gift in current_gifts.gifts:
        gift_id = str(gift.id)
        if gift_id not in gifts_state:
            # Новый подарок, добавляем в состояние
            gifts_state[gift_id] = {
                "upgrades": gift.upgrades if hasattr(gift, 'upgrades') else [],
                "remaining_count": gift.remaining_count,
                "total_count": gift.total_count
            }
        else:
            # Проверяем, есть ли новые апгрейды
            current_upgrades = gift.upgrades if hasattr(gift, 'upgrades') else []
            previous_upgrades = gifts_state[gift_id].get("upgrades", [])

            # Находим новые апгрейды
            new_upgrades_for_gift = [upgrade for upgrade in current_upgrades if upgrade not in previous_upgrades]
            if new_upgrades_for_gift:
                new_upgrades.append((gift_id, new_upgrades_for_gift))
                # Обновляем состояние
                gifts_state[gift_id]["upgrades"] = current_upgrades

    # Сохраняем обновлённое состояние
    save_gifts_state(gifts_state)

    return new_upgrades

# Отправляем уведомление о новых апгрейдах
async def send_upgrade_notification(gift_id, upgrades):
    """Отправляет уведомление о новых апгрейдах подарка."""
    notification_text = (
        f"🎁 <b>UPGRADE AVAILABLE!</b>\n"
        f"<b>ID:</b> <code>{gift_id}</code>\n"
        f"<b>Upgrades:</b>\n"
    )
    for upgrade in upgrades:
        notification_text += f"- {upgrade}\n"

    # Отправляем уведомление в канал
    sticker_file_id = stickers_data.get(gift_id)
    if sticker_file_id:
        sticker_message_id = await send_sticker(CHANNEL_ID, sticker_file_id)
        if sticker_message_id:
            await send_text_as_reply(CHANNEL_ID, notification_text, sticker_message_id)
    else:
        logger.error(f"Стикер для подарка {gift_id} не найден в stickers.json.")

# Проверяем новые подарки
async def check_new_gifts():
    global known_gifts
    try:
        # Получаем все доступные подарки
        current_gifts = await bot(GetAvailableGifts())

        # Проверяем новые подарки
        new_gifts = [gift for gift in current_gifts.gifts if str(gift.id) not in known_gifts]

        if new_gifts:
            logger.info(f"NEW GIFTS ALERT. Найдено новых подарков: {len(new_gifts)}")
            for gift in new_gifts:
                gift_id = str(gift.id)
                known_gifts[gift_id] = {
                    "emoji": gift.sticker.emoji,
                    "name": gift.sticker.name if hasattr(gift.sticker, 'name') else "",
                    "star_count": gift.star_count,
                    "total_count": gift.total_count,
                    "remaining_count": gift.remaining_count
                }

                # Если стикерпак не существует, создаём его
                if not await sticker_set_exists(STICKER_SET_NAME):
                    await create_sticker_set_from_gifts([gift])
                else:
                    await add_stickers_to_set([gift])

                # Отправляем стикер и получаем его message_id
                if gift_id in stickers_data:
                    sticker_file_id = stickers_data[gift_id]  # Получаем file_id стикера из stickers.json
                    sticker_message_id = await send_sticker(CHANNEL_ID, sticker_file_id)

                    if sticker_message_id:
                        # Формируем текст для reply
                        gift_info = (
                            f" <b>☝️🔺NEW GIFT AVAILABLE🔺☝️</b>\n"
                            f" \n"
                            f"<b>ID:</b> <code>{gift_id}</code>\n"
                            f"<b>Price:</b> <code>{gift.star_count}</code>★\n"
                            f"<b>Supply:</b> <code>{gift.total_count if gift.total_count else '∞'}</code>"
                        )

                        # Отправляем текст как reply к стикеру
                        await send_text_as_reply(CHANNEL_ID, gift_info, sticker_message_id)
                    else:
                        logger.error(f"Не удалось отправить стикер для подарка {gift_id}.")
                else:
                    logger.error(f"Стикер для подарка {gift_id} не найден в stickers.json.")

            save_known_gifts()
        else:
            logger.info("Новых подарков нет.")

        # Проверяем все подарки на порог 11%
        for gift in current_gifts.gifts:
            await check_gift_threshold(gift)

        # Проверяем новые апгрейды
        new_upgrades = await check_for_upgrades(current_gifts)
        if new_upgrades:
            for gift_id, upgrades in new_upgrades:
                await send_upgrade_notification(gift_id, upgrades)

    except TelegramAPIError as e:
        if "Too Many Requests" in str(e):
            retry_after = int(e.message.split("retry after ")[1])
            logger.warning(f"Лимит запросов превышен. Ждём {retry_after} секунд...")
            await asyncio.sleep(retry_after)
            await check_new_gifts()  # Повторяем запрос после паузы
        else:
            logger.error(f"Ошибка при проверке новых подарков: {e}")

# Основная функция
async def main():
    global known_gifts, stickers_data, notified_gifts
    logger.info("Запуск бота...")

    # Инициализируем файл для уведомлений
    initialize_notified_gifts()

    # Загружаем данные о подарках и стикерах
    known_gifts = load_known_gifts()
    stickers_data = load_stickers_data()
    notified_gifts = load_notified_gifts()

    try:
        while True:
            await check_new_gifts()
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную.")
    finally:
        await bot.session.close()  # Закрываем сессию бота

if __name__ == '__main__':
    asyncio.run(main())