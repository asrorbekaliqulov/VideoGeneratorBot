from mimetypes import read_mime_types

from asgiref.sync import sync_to_async
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler,
    filters, CallbackQueryHandler
)
from ..BotCommands.StartCommand import get_user_keyboard
from apps.Bot.models.TelegramBot import TelegramUser, Payment
import os

from ..MandatoryChannel.Add_channel import reply_markup

ENTER_AMOUNT, UPLOAD_SCREENSHOT = range(2)

payment_channel = os.getenv("PAYMENT_CHANNEL_ID")
ADMIN_CHANNEL_ID = payment_channel


# --- INLINE BUTTONS ---
def amount_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_amount")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]
    ])

def screenshot_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_screenshot")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]
    ])


# ---------------------------
# START
# ---------------------------
async def topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rm_keyb = ReplyKeyboardRemove()
    await update.message.reply_text(
        "💰 Hisobni to‘ldirmoqchi bo‘lgan summani kiriting.\n",
        reply_markup=rm_keyb
    )
    await update.message.reply_text(
        "Minimal: 10000 so‘m\n"
        "<i>Faqat raqam kiriting</i>",
        parse_mode="HTML",
        reply_markup=amount_buttons()
    )

    return ENTER_AMOUNT


# ---------------------------
# ENTER AMOUNT
# ---------------------------
async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Faqat raqam kiriting!",
            reply_markup=amount_buttons()
        )
        return ENTER_AMOUNT

    amount = int(text)

    if amount < 10000:
        await update.message.reply_text(
            "❌ Minimal summa 10 000 so‘m!",
            reply_markup=amount_buttons()
        )
        return ENTER_AMOUNT

    context.user_data["amount"] = amount

    await update.message.reply_text(
        f"<b>💳 To‘lov summasi: {amount} so‘m</b>\n\n"
        "To‘lovni shu kartaga qiling:\n"
        "<code>9860 0801 4716 9256</code>\n"
        "Chexroz Urazboyeva\n\n"
        "📸 Keyin screenshot yuboring!",
        parse_mode="HTML",
        reply_markup=screenshot_buttons()
    )

    return UPLOAD_SCREENSHOT


# ---------------------------
# UPLOAD SCREENSHOT
# ---------------------------
async def upload_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.photo:
        await update.message.reply_text(
            "❌ Faqat screenshot yuboring!",
            reply_markup=screenshot_buttons()
        )
        return UPLOAD_SCREENSHOT

    file_id = update.message.photo[-1].file_id
    amount = context.user_data.get("amount")
    tg_user = update.message.from_user

    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=tg_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Siz ro‘yxatdan o‘tmagansiz. /start")
        return ConversationHandler.END

    payment = await sync_to_async(Payment.objects.create)(
        user=user,
        amount=amount,
        screenshot_file_id=file_id,
        status="pending"
    )

    # --- ADMINGA YUBORILADI ---
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok_{payment.id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_no_{payment.id}")
        ]
    ])

    await context.bot.send_photo(
        chat_id=ADMIN_CHANNEL_ID,
        photo=file_id,
        caption=(
            f"🆕 *Yangi To‘lov Tekshiruvi*\n"
            f"👤 User: @{tg_user.username}\n"
            f"🆔 TG ID: {tg_user.id}\n"
            f"💰 Summa: {amount} so‘m\n"
            f"📝 Payment ID: {payment.id}"
        ),
        parse_mode="Markdown",
        reply_markup=buttons
    )
    keybord = await get_user_keyboard()
    await update.message.reply_text(
        "📤 Screenshot qabul qilindi!\n🔎 Admin tekshiradi.",
        reply_markup=keybord
    )

    return ConversationHandler.END


# ---------------------------
# CALLBACK HANDLERS (INLINE)
# ---------------------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    main_keyb = await get_user_keyboard()
    action = query.data

    # ❌ BEKOR QILISH
    if action == "cancel":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="❌ Jarayon bekor qilindi.",
            reply_markup=main_keyb
        )
        return ConversationHandler.END

    # ⬅️ ORQAGA (amount bosqichiga qaytish)
    if action == "back_amount":
        await query.message.edit_text(
            "💰 Yangi summa kiriting:",
            reply_markup=amount_buttons()
        )
        return ENTER_AMOUNT

    # ⬅️ ORQAGA (screenshot bosqichiga qaytish)
    if action == "back_screenshot":
        amount = context.user_data.get("amount")

        await query.message.edit_text(
            f"💳 To‘lov summasi: {amount} so‘m\n"
            "📸 Endi screenshot yuboring.",
            reply_markup=screenshot_buttons()
        )
        return UPLOAD_SCREENSHOT


# ---------------------------
# FALLBACK – har qanday noto‘g‘ri input
# ---------------------------
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboardd = await get_user_keyboard()
    await update.message.reply_text(
        "❌ Xato malumot yubordingiz jarayon bekor qilindi.",
        reply_markup=keyboardd
    )
    return ConversationHandler.END


# ---------------------------
# CONVERSATION HANDLER
# ---------------------------
payment_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex(r"^💰 Hisоbni tо'ldirish$"), topup_start)
    ],
    states={

        ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount),
            CallbackQueryHandler(callback_handler)
        ],

        UPLOAD_SCREENSHOT: [
            MessageHandler(filters.PHOTO, upload_screenshot),
            CallbackQueryHandler(callback_handler),
            MessageHandler(filters.TEXT, fallback),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(callback_handler),
        MessageHandler(filters.ALL, fallback),
        CommandHandler('start', fallback)
    ],
)
