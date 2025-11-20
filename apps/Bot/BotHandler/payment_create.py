from asgiref.sync import sync_to_async
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    filters, CallbackContext
)
from apps.Bot.models.TelegramBot import TelegramUser, Payment
import os

ENTER_AMOUNT, UPLOAD_SCREENSHOT = range(2)

payment_channel = os.getenv("PAYMENT_CHANNEL_ID")
ADMIN_CHANNEL_ID = payment_channel

cancel_keyboard = ReplyKeyboardMarkup(
    [["⬅️ Orqaga", "❌ Bekor qilish"]],
    resize_keyboard=True
)

# ---------------------------
# START
# ---------------------------
async def topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "💰 Hisobni to‘ldirmoqchi bo‘lgan summani kiriting.\n"
        "Minimal: 10000 so‘m",
        reply_markup=cancel_keyboard
    )

    return ENTER_AMOUNT


# ---------------------------
# ENTER AMOUNT
# ---------------------------
async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # ❌ Bekor qilish
    if text == "❌ Bekor qilish":
        return await cancel_process(update, context)

    # ⬅️ Orqaga
    if text == "⬅️ Orqaga":
        return await topup_start(update, context)

    clean_text = text.replace(" ", "")

    if not clean_text.isdigit():
        await update.message.reply_text("❌ Faqat raqam kiriting!", reply_markup=cancel_keyboard)
        return ENTER_AMOUNT

    amount = int(clean_text)

    if amount < 10000:
        await update.message.reply_text("❌ Minimal summa 10 000 so‘m!", reply_markup=cancel_keyboard)
        return ENTER_AMOUNT

    context.user_data["amount"] = amount

    await update.message.reply_text(
        f"<b>💳 To‘lov summasi: {amount} so‘m\n\n"
        "Quyidagi karta raqamiga to‘lov qiling:\n\n"
        "<code>9860 0801 4716 9256</code>\n"
        "Chexroz Urazboyeva\n\n"
        "📸 Keyin faqat rasm (screenshot) yuboring!\n"
        "❗ Screenshotda vaqt ko‘rinishi shart!</b>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard
    )

    return UPLOAD_SCREENSHOT


# ---------------------------
# UPLOAD SCREENSHOT
# ---------------------------
async def upload_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text if update.message.text else None

    # ❌ Bekor qilish
    if text == "❌ Bekor qilish":
        return await cancel_process(update, context)

    # ⬅️ Orqaga
    if text == "⬅️ Orqaga":
        return await enter_amount(update, context)

    # Faqat photo qabul qilinsin
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Faqat rasm (screenshot) yuboring!",
            reply_markup=cancel_keyboard
        )
        return UPLOAD_SCREENSHOT

    file_id = update.message.photo[-1].file_id
    amount = context.user_data.get("amount")
    tg_user = update.message.from_user

    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=tg_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Siz ro‘yxatdan o‘tmagansiz.")
        return ConversationHandler.END

    # Payment yaratish
    payment = await sync_to_async(Payment.objects.create)(
        user=user,
        amount=amount,
        screenshot_file_id=file_id,
        status="pending"
    )

    # Admin inline tugmalar
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

    await update.message.reply_text(
        "📤 Screenshot qabul qilindi!\n🔎 Adminlar tez orada tekshiradi.",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


# ---------------------------
# CANCEL FUNCTION
# ---------------------------
async def cancel_process(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "❌ Jarayon bekor qilindi.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ---------------------------
# FALLBACK
# ---------------------------
async def payment_fallback(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "❌ Noto‘g‘ri ma’lumot.\nJarayon tugadi.",
        reply_markup=ReplyKeyboardRemove()
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)
        ],
        UPLOAD_SCREENSHOT: [
            MessageHandler(filters.PHOTO, upload_screenshot),
            MessageHandler(filters.TEXT, upload_screenshot),  # tugmalar uchun!
        ],
    },
    fallbacks=[
        MessageHandler(filters.ALL, payment_fallback)
    ],
)
