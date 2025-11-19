from telegram.ext import ConversationHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from apps.Bot.models.TelegramBot import VideoOrder, TelegramUser
from asgiref.sync import sync_to_async
from ..decorators import admin_required

WAITING_VIDEO = 1
WAITING_EXTRA_TEXT = 2
WAITING_CANCEL_REASON = 3
WAITING_REFUND = 4


def admin_action_buttons(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Zakazni qabul qilish", callback_data=f"take:{order_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel:{order_id}")
        ]
    ])


def skip_button(order_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Kerak emas", callback_data=f"skip:{order_id}")]
    ])


def refund_buttons(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Ha", callback_data=f"refund_yes:{order_id}"),
            InlineKeyboardButton("Yo‘q", callback_data=f"refund_no:{order_id}")
        ]
    ])


# ===================================================================================
# ACCEPT ORDER
# ===================================================================================
@admin_required
async def accept_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[1]

    # ORDER with FK user
    order = await sync_to_async(
        lambda: VideoOrder.objects.select_related("user").get(id=order_id)
    )()

    # Kanal post markupni o'zgartirish
    try:
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Qabul qilindi", callback_data="none")]
            ])
        )
    except:
        pass

    admin_id = query.from_user.id
    username = order.user.username

    text = (
        f"📝 Zakaz ID: {order.id}\n"
        f"👤 User: @{username}\n"
        f"💰 Narx: {order.amount} so‘m\n"
        f"📌 Holat: {order.status}\n\n"
        f"Zakazni tasdiqlaysizmi?"
    )

    await context.bot.send_message(
        chat_id=admin_id,
        text=text,
        reply_markup=admin_action_buttons(order_id)
    )


# ===================================================================================
# ADMIN TAKES ORDER → SEND VIDEO
# ===================================================================================

@admin_required
async def take_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[1]
    context.user_data["order_id"] = order_id

    await query.message.reply_text(
        "🎥 Videoni yuboring.\n❗ Faqat video yoki fayl yuboring."
    )

    return WAITING_VIDEO


@admin_required
async def admin_send_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    order_id = context.user_data.get("order_id")

    if not message.video and not message.document:
        await message.reply_text("❗ Faqat video yoki fayl yuboring!")
        return WAITING_VIDEO

    file_id = message.video.file_id if message.video else message.document.file_id

    # async-safe DB update
    await sync_to_async(VideoOrder.objects.filter(id=order_id).update)(
        video_file_id=file_id
    )

    await message.reply_text(
        "➕ Qo‘shimcha matn yubormoqchimisiz?\nYoki tugmani bosing:",
        reply_markup=skip_button(order_id)
    )

    return WAITING_EXTRA_TEXT


# ===================================================================================
# SEND EXTRA TEXT
# ===================================================================================

@admin_required
async def extra_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    order_id = context.user_data.get("order_id")

    order = await sync_to_async(
        lambda: VideoOrder.objects.select_related("user").get(id=order_id)
    )()

    description = (
        f"🎬 Buyurtmangiz tayyor!\n"
        f"Zakaz ID: {order.id}\n\n"
        f"Admin tavsifi:\n{text}"
    )

    await context.bot.send_video(
        chat_id=order.user.user_id,
        video=order.video_file_id,
        caption=description
    )

    await sync_to_async(VideoOrder.objects.filter(id=order.id).update)(
        status="done"
    )

    await update.message.reply_text("✅ Zakaz foydalanuvchiga yuborildi.")
    return ConversationHandler.END


@admin_required
async def skip_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[1]

    order = await sync_to_async(
        lambda: VideoOrder.objects.select_related("user").get(id=order_id)
    )()

    description = f"🎬 Buyurtmangiz tayyor!\nZakaz ID: {order.id}"

    await context.bot.send_video(
        chat_id=order.user.user_id,
        video=order.video_file_id,
        caption=description
    )

    await sync_to_async(VideoOrder.objects.filter(id=order.id).update)(
        status="done"
    )

    await query.message.reply_text("✅ Matn yuborilmadi. Zakaz topshirildi.")
    return ConversationHandler.END


# ===================================================================================
# CANCEL ORDER → REASON
# ===================================================================================
@admin_required
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[1]
    context.user_data["order_id"] = order_id

    await query.message.reply_text("❌ Bekor qilish sababini yuboring:")

    return WAITING_CANCEL_REASON


@admin_required
async def cancel_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    context.user_data["reason"] = reason
    order_id = context.user_data["order_id"]

    await update.message.reply_text(
        "💸 To‘lov qaytarilsinmi?",
        reply_markup=refund_buttons(order_id)
    )

    return WAITING_REFUND


# ===================================================================================
# REFUND "YES"
# ===================================================================================
@admin_required
async def refund_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[1]     # ALWAYS GET FROM CALLBACK
    reason = context.user_data.get("reason")

    # Get order with FK
    order = await sync_to_async(
        lambda: VideoOrder.objects.select_related("user").get(id=order_id)
    )()

    user = order.user

    # refund balance
    user.balance += order.amount
    await sync_to_async(user.save)()

    # update order
    order.status = "canceled"
    order.cancel_reason = reason
    await sync_to_async(order.save)()

    await context.bot.send_message(
        chat_id=user.user_id,
        text=f"❌ Zakazingiz bekor qilindi!\nSabab: {reason}\n💰 {order.amount} so‘m qaytarildi."
    )

    await query.message.reply_text("✅ Bekor qilindi va pul qaytarildi.")
    return ConversationHandler.END


# ===================================================================================
# REFUND "NO"
# ===================================================================================
@admin_required
async def refund_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":")[1]
    reason = context.user_data.get("reason")

    order = await sync_to_async(
        lambda: VideoOrder.objects.select_related("user").get(id=order_id)
    )()

    user = order.user

    order.status = "canceled"
    order.cancel_reason = reason
    await sync_to_async(order.save)()

    await context.bot.send_message(
        chat_id=user.user_id,
        text=f"❌ Zakazingiz bekor qilindi!\nSabab: {reason}"
    )

    await query.message.reply_text("❌ Bekor qilindi. Pul qaytarilmadi.")
    return ConversationHandler.END


async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fallback — foydalanuvchi noto‘g‘ri xabar yuborganda
    text = "❗ Siz noto‘g‘ri amal bajardingiz.\nIltimos, tugmalardan foydalaning."
    await update.message.reply_text(text)
    return ConversationHandler.END

async def fallback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("❗ Ushbu amal mavjud emas. Iltimos, tugmalardan foydalaning.")
    return ConversationHandler.END


# ===================================================================================
# CONVERSATION HANDLER
# ===================================================================================
admin_video_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(take_order, pattern="^take:"),
        CallbackQueryHandler(cancel_order, pattern="^cancel:")
    ],

    states={
        WAITING_VIDEO: [
            MessageHandler(filters.VIDEO | filters.Document.ALL, admin_send_video)
        ],

        WAITING_EXTRA_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, extra_text),
            CallbackQueryHandler(skip_extra, pattern="^skip:")
        ],

        WAITING_CANCEL_REASON: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_reason)
        ],

        WAITING_REFUND: [
            CallbackQueryHandler(refund_yes, pattern="^refund_yes:"),
            CallbackQueryHandler(refund_no, pattern="^refund_no:")
        ]
    },

    fallbacks=[
        MessageHandler(filters.ALL, fallback_handler),
        CallbackQueryHandler(fallback_query)
    ]
)
