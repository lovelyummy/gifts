import os
import json
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.methods import GetAvailableGifts, CreateNewStickerSet, AddStickerToSet, SendSticker, GetStickerSet
from aiogram.types import Gifts, InputSticker

# Загружаем переменные из .env
from dotenv import load_dotenv

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
sent_stickers = set()  # Множество для отслеживания отправленных стикеров
existing_stickers = set()  # Множество для отслеживания стикеров, которые уже добавлены в стикерпак


# Загружаем сохраненные ID подарков из файла
def load_known_gifts():
    """Загружает данные о подарках из known_gifts.json."""
    if os.path.exists("known_gifts.json"):
        with open("known_gifts.json", "r") as f:
            return json.load(f)
    return {}


# Сохраняем подарки в файл
def save_known_gifts():
    """Сохраняет данные о подарках в known_gifts.json."""
    with open("known_gifts.json", "w") as f:
        json.dump(known_gifts, f)


# Загружаем данные о подарках из gifts.json
def load_gifts_from_json():
    """Загружает данные о подарках из gifts.json."""
    if os.path.exists("gifts.json"):
        with open("gifts.json", "r") as f:
            return json.load(f)
    return {}


# Сохраняем подарки в gifts.json
def save_gifts_to_json(gifts):
    """Сохраняет подарки в файл gifts.json."""
    gifts_data = {}
    if os.path.exists("gifts.json"):
        with open("gifts.json", "r") as f:
            gifts_data = json.load(f)

    for gift in gifts:
        gifts_data[gift.id] = {
            "emoji": gift.sticker.emoji,  # Используем emoji вместо name
            "star_count": gift.star_count,
            "total_count": gift.total_count,
            "remaining_count": gift.remaining_count,
            "sticker_id": gift.sticker.file_id
        }

    with open("gifts.json", "w") as f:
        json.dump(gifts_data, f, indent=4)


# Загружаем данные о подарках, для которых уже отправлены уведомления
def load_notified_gifts():
    """Загружает данные о подарках, для которых уже отправлены уведомления."""
    if not os.path.exists("notified_gifts.json"):
        # Если файл не существует, создаём пустой файл
        with open("notified_gifts.json", "w") as f:
            json.dump({}, f)
        return {}

    with open("notified_gifts.json", "r") as f:
        return json.load(f)


# Сохраняем данные о подарках, для которых отправлены уведомления
def save_notified_gifts(notified_gifts):
    """Сохраняет данные о подарках, для которых отправлены уведомления."""
    with open("notified_gifts.json", "w") as f:
        json.dump(notified_gifts, f, indent=4)


# Проверяем существование стикерпака
async def sticker_set_exists(name):
    """Проверяет существование стикерпака."""
    try:
        await bot(GetStickerSet(name=name))
        return True
    except:
        return False


# Создаём стикерпак, если его нет
async def create_sticker_set_from_gifts(gifts):
    """Создаёт стикерпак, если его нет."""
    stickers = [InputSticker(sticker=gift.sticker.file_id, emoji_list=[gift.sticker.emoji], format="static") for gift in
                gifts]
    try:
        await bot(CreateNewStickerSet(user_id=USER_ID, name=STICKER_SET_NAME, title="Gift Stickers", stickers=stickers,
                                      sticker_type="regular"))
        logger.info(f"Стикерпак '{STICKER_SET_NAME}' создан.")
        # Добавляем все новые стикеры в список существующих
        for gift in gifts:
            existing_stickers.add(gift.sticker.file_id)
    except Exception as e:
        logger.error(f"Ошибка создания стикерпака: {e}")


# Добавляем новые стикеры в существующий стикерпак
async def add_stickers_to_set(gifts):
    """Добавляет новые стикеры в существующий стикерпак."""
    for gift in gifts:
        if gift.sticker.file_id not in existing_stickers:
            try:
                sticker = InputSticker(sticker=gift.sticker.file_id, emoji_list=[gift.sticker.emoji], format="static")
                await bot(AddStickerToSet(user_id=USER_ID, name=STICKER_SET_NAME, sticker=sticker))
                existing_stickers.add(gift.sticker.file_id)  # Добавляем стикер в множество существующих
                sent_stickers.add(gift.sticker.file_id)  # Добавляем стикер в множество отправленных
                logger.info(f"Стикер {gift.sticker.file_id} добавлен в {STICKER_SET_NAME} и помечен как отправленный.")
            except Exception as e:
                logger.error(f"Ошибка добавления стикера {gift.sticker.file_id}: {e}")


# Отправляем стикеры из набора в канал
async def send_stickers_from_set():
    """Отправляет стикеры из набора в канал."""
    try:
        sticker_set = await bot(GetStickerSet(name=STICKER_SET_NAME))
        for sticker in sticker_set.stickers:
            if sticker.file_id not in sent_stickers:  # Проверка на уникальность
                await bot(SendSticker(chat_id=CHANNEL_ID, sticker=sticker.file_id))
                sent_stickers.add(sticker.file_id)  # Добавляем в множество отправленных стикеров
                logger.info(f"Отправлен стикер {sticker.file_id} в канал.")
    except Exception as e:
        logger.error(f"Ошибка при отправке стикеров: {e}")


# Отправляем текстовое уведомление в канал
async def send_notification(message: str):
    """Отправляет текстовое уведомление в канал."""
    try:
        post_message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message.replace('<br>', '\n'),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info("Отправлено текстовое сообщение.")
        return post_message
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        return None


async def check_remaining_count(gift):
    """Проверяет, осталось ли меньше 11% подарков, и отправляет уведомление, если оно ещё не было отправлено."""
    if gift.total_count and gift.remaining_count:
        remaining_percentage = (gift.remaining_count / gift.total_count) * 100
        if remaining_percentage < 11:
            # Загружаем данные о подарках из gifts.json
            gifts_data = load_gifts_from_json()
            if str(gift.id) in gifts_data:
                # Загружаем данные о подарках, для которых уже отправлены уведомления
                notified_gifts = load_notified_gifts()
                if str(gift.id) not in notified_gifts:
                    emoji = gifts_data[str(gift.id)].get("emoji", "")
                    name = gifts_data[str(gift.id)].get("name", "")

                    # Формируем сообщение с названием, если оно есть
                    if name:
                        message = (
                            f"⚠️ <b>Внимание!</b> Подарок <b>{name} {emoji}</b> заканчивается! "
                            f"Осталось <code>{gift.remaining_count}</code> шт. (<code>{remaining_percentage:.2f}%</code>)."
                        )
                    else:
                        message = (
                            f"⚠️ <b>Внимание!</b> Подарок <b>{emoji}</b> заканчивается! "
                            f"Осталось <code>{gift.remaining_count}</code> шт. (<code>{remaining_percentage:.2f}%</code>)."
                        )

                    # Отправляем уведомление
                    await send_notification(message)

                    # Добавляем подарок в список уведомлённых
                    notified_gifts[str(gift.id)] = True
                    save_notified_gifts(notified_gifts)  # Сохраняем обновлённые данные
                    logger.info(f"Отправлено уведомление для подарка {emoji}.")
                else:
                    logger.info(f"Уведомление для подарка {gift.id} уже было отправлено ранее.")
            else:
                logger.warning(f"Подарок с ID {gift.id} не найден в gifts.json.")


async def check_if_gift_is_out_of_stock(gift):
    """Проверяет, закончились ли подарки, и отправляет уведомление, если оно ещё не было отправлено."""
    if gift.remaining_count == 0:
        # Загружаем данные о подарках из gifts.json
        gifts_data = load_gifts_from_json()
        if str(gift.id) in gifts_data:
            # Загружаем данные о подарках, для которых уже отправлены уведомления
            notified_gifts = load_notified_gifts()
            if str(gift.id) not in notified_gifts:
                emoji = gifts_data[str(gift.id)].get("emoji", "")
                name = gifts_data[str(gift.id)].get("name", "")

                # Формируем сообщение с названием, если оно есть
                if name:
                    message = (
                        f"🚨 <b>Подарок закончился!</b> Подарок <b>{name} {emoji}</b> больше недоступен."
                    )
                else:
                    message = (
                        f"🚨 <b>Подарок закончился!</b> Подарок <b>{emoji}</b> больше недоступен."
                    )

                # Отправляем уведомление
                await send_notification(message)

                # Добавляем подарок в список уведомлённых
                notified_gifts[str(gift.id)] = True
                save_notified_gifts(notified_gifts)  # Сохраняем обновлённые данные
                logger.info(f"Отправлено уведомление для подарка {emoji}.")
            else:
                logger.info(f"Уведомление для подарка {gift.id} уже было отправлено ранее.")
        else:
            logger.warning(f"Подарок с ID {gift.id} не найден в gifts.json.")


# Проверяем новые подарки
async def check_new_gifts():
    global known_gifts
    current_gifts = await bot(GetAvailableGifts())
    new_gifts = [gift for gift in current_gifts.gifts if gift.id not in known_gifts]

    known_gifts.update({gift.id: time.time() for gift in new_gifts})
    save_known_gifts()

    if new_gifts:
        logger.info(f"NEW GIFTS ALERT.")
        gift_info = "\n\n".join(
            f" <b>new gift:</b> \n"
            f"<b>price:</b> <code>{gift.star_count}</code>★\n"
            f"<b>supply:</b> <code>{gift.total_count if gift.total_count else '∞'}</code>" for gift in new_gifts
        )

        post_message = await send_notification(f"<b>🎉 New Gifts:</b><br>{gift_info}")

        if post_message is not None:
            post_message_id = post_message.message_id
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

    # Сохраняем подарки в gifts.json
    save_gifts_to_json(current_gifts.gifts)

    # Проверяем оставшееся количество подарков
    for gift in current_gifts.gifts:
        await check_remaining_count(gift)
        await check_if_gift_is_out_of_stock(gift)


# Отправляем стикеры в комментарии к посту
async def send_stickers_in_comments(post_message_id):
    """Отправляет стикеры в комментарии к посту, избегая повторной отправки и добавления в стикерпак."""
    try:
        sticker_set = await bot(GetStickerSet(name=STICKER_SET_NAME))  # Получаем стикерпак
        for sticker in sticker_set.stickers:
            if sticker.file_id not in sent_stickers:  # Проверяем, был ли уже отправлен стикер
                await bot(SendSticker(
                    chat_id=CHANNEL_ID,
                    sticker=sticker.file_id,
                    reply_to_message_id=post_message_id  # Отправка в комментарии
                ))
                sent_stickers.add(sticker.file_id)  # Добавляем в множество отправленных стикеров
                logger.info(f"Отправлен стикер {sticker.file_id} в комментарий к посту с ID {post_message_id}.")
            else:
                logger.info(f"Стикер {sticker.file_id} уже был отправлен ранее, пропущен.")
    except Exception as e:
        logger.error(f"Ошибка при отправке стикеров в комментарии: {e}")


# Основная функция
async def main():
    global known_gifts
    logger.info("Запуск бота...")

    known_gifts = load_known_gifts()

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