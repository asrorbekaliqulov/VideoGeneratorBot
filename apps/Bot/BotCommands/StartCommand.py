from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from ..utils import save_user_to_db
from ..models.TelegramBot import TelegramUser
from ..decorators import typing_action, mandatory_channel_required
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


async def get_user_keyboard():
    """Bot uchun inline keyboardni dinamik yaratish."""
    # Asinxron holda guide ma'lumotini olish
    # Asosiy keyboard tugmalari
    users_keyboards = [
        [
            KeyboardButton(text="🎞 Video yaratish"),
            KeyboardButton(text="🗃 Buyurtmаlаrim")
        ],
        [
            KeyboardButton(text="💰 Hisоbni tо'ldirish"),
            KeyboardButton(text="💼 Profilim")
        ],
        [
            KeyboardButton(text="ℹ️ Qo'llаnma"),
            KeyboardButton(text="📞 Murojаat")
        ]
    ]

    return ReplyKeyboardMarkup(users_keyboards, resize_keyboard=True)




@typing_action
@mandatory_channel_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Botni ishga tushirish uchun komanda.
    """
    remove = ReplyKeyboardRemove()

    data = update.effective_user
    if update.callback_query:
        await update.callback_query.answer("Asosiy menyu")
        await update.callback_query.delete_message()

    reply_markup = await get_user_keyboard()
    is_save = await save_user_to_db(data)
    admin_id = await TelegramUser.get_admin_ids()

    # === start video path ===
    from django.conf import settings
    import os

    video_path = os.path.join(settings.BASE_DIR, "assets", "static", "videos", "start_video.mp4")

    # === ADMIN uchun alohida xabar ===
    if update.effective_user.id in admin_id:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="<b>Main Menu 🖥\n<tg-spoiler>/admin_panel</tg-spoiler></b>",
            reply_markup=remove,
            parse_mode="html"
        )

    # === START VIDEO YUBORISH ===
    try:
        await context.bot.send_video(
            chat_id=update.effective_user.id,
            video="https://t.me/Hobbiy_bots/3",
            caption="<b>🎬 Eski fotosuratni qayta ishlash namunasi</b>",
            parse_mode="html"
        )
    except Exception as e:
        print("Xato {}".format(e))

    # === ASOSIY MENYU ===
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=("""
👋 Salom!

✨ Ushbu bot mumkin bo‘lmagan narsalarni hadya qilishi mumkin…
📷 Uning yordamida yoningda yo‘q bo‘lgan odamning tabassumini yana ko‘rishing mumkin.
        """
        ),
        parse_mode="html",
        reply_markup=reply_markup
    )

    return ConversationHandler.END


    