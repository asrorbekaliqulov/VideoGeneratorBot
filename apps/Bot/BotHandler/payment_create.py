from asgiref.sync import sync_to_async
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, CallbackContext
)
from django.utils import timezone
from apps.Bot.models.TelegramBot import TelegramUser, Payment
import os

ENTER_AMOUNT, UPLOAD_SCREENSHOT = range(2)

payment_channel = os.getenv("PAYMENT_CHANNEL_ID")
ADMIN_CHANNEL_ID = payment_channel  # admin kanal ID

cancel_button = InlineKeyboardMarkup([[InlineKeyboardButton(text="Bekor qilish", callback_data="cancel")]])


# /topup — hisobni to‘ldirish
async def topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 Hisobni to‘ldirmoqchi bo‘lgan summani kiriting.\n"
        "Minimal: 10000 so‘m\n"
        "<i>faqat raqam kiriting hech qanday bo'sh joylarsiz</i>",
        reply_markup=cancel_button,
        parse_mode="HTML"
    )
    return ENTER_AMOUNT


# ☑ Summani qabul qilish
async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if not text.isdigit():
        await update.message.reply_text("❌ Faqat raqam kiriting!", reply_markup=cancel_button)
        return ENTER_AMOUNT

    amount = int(text)
    if amount < 10000:
        await update.message.reply_text("❌ Minimal summa 10 000 so‘m!", reply_markup=cancel_button)
        return ENTER_AMOUNT

    context.user_data["amount"] = amount

    await update.message.reply_text(
        f"<b>💳 To‘lov summasi: {amount} so‘m\n\n"
        "Quyidagi karta raqamiga to‘lovni amalga oshiring:\n\n"
        "<code>9860 0801 4716 9256 </code>\n"
        "Chexroz Urazboyeva\n\n"
        "📸 So‘ngra <i>faqat rasm formatida</i> to‘lov screenshotini yuboring..\n"
        "<i>❗ Screenshotda vaqt aniq ko‘rinishi shart!</i></b>",
        parse_mode="HTML",
        reply_markup=cancel_button
    )

    return UPLOAD_SCREENSHOT


# 📸 Screenshotni qabul qilish
async def upload_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "❌ To‘lov bekor qilindi!\n"
            "Siz faqat *rasm formatida* screenshot yuborishingiz kerak."
        )
        return ConversationHandler.END

    file_id = update.message.photo[-1].file_id
    amount = context.user_data["amount"]
    tg_user = update.message.from_user

    # Django user olish yoki yaratish
    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=tg_user.id)

    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz yoki bazadan topilmadingiz.")
        return ConversationHandler.END

    # Payment yaratish
    payment = await sync_to_async(Payment.objects.create)(
        user=user,
        amount=amount,
        screenshot_file_id=file_id,
        status="pending"
    )

    # Admin kanalga yuboriladigan tugmalar
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok_{payment.id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_no_{payment.id}"),
        ]
    ])

    # Admin kanalga xabar yuborish
    await context.bot.send_photo(
        chat_id=ADMIN_CHANNEL_ID,
        photo=file_id,
        caption=(
            f"🆕 *Yangi To‘lov Tekshiruvi*\n\n"
            f"👤 User: @{tg_user.username}\n"
            f"🆔 TG ID: {tg_user.id}\n"
            f"💰 Summa: {amount} so‘m\n"
            f"📝 Payment ID: {payment.id}\n"
        ),
        reply_markup=buttons
    )

    # Userga xabar
    await update.message.reply_text(
        "📤 Screenshot qabul qilindi!\n"
        "🔎 To‘lov adminlar tomonidan tez orada tekshiriladi."
    )

    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext):
    await context.bot.send_message(chat_id=update.effective_user.id, text="Bekor qilindi")
    return ConversationHandler.END


payment_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(r"^💰 Hisоbni tо'ldirish$"), topup_start)],
    states={
        ENTER_AMOUNT: [MessageHandler(filters.TEXT, enter_amount)],
        UPLOAD_SCREENSHOT: [MessageHandler(filters.PHOTO, upload_screenshot)],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern=r"^cancel$")],
)