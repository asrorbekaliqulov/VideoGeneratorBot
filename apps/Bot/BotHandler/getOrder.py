from click import Context

from apps.Bot.models.TelegramBot import TelegramUser, VideoOrder, OrderType
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from asgiref.sync import sync_to_async
import os

ADMIN_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID")


WAIT_CHOOSE_TYPE, WAIT_IMAGE, WAIT_DESCRIPTION, WAIT_CONFIRM = range(4)


def strike(text: str) -> str:
    result = ""
    for char in text:
        result += char + "\u0336"
    return result

def order_accept_button(order_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"📩 Qabul qilish", callback_data=f"order_accept:{order_id}")
    ]])

async def start_video_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.message.from_user

    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=tg_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Siz ro‘yxatdan o‘tmagansiz!")
        return ConversationHandler.END

    context.user_data["user"] = user

    # Barcha zakaz turlarini olish
    order_types = await sync_to_async(list)(
        OrderType.objects.all().order_by('-is_active', 'price')
    )

    # ⚠️ AGAR BAZADA HECH QANDAY ZAKAZ TURI YO‘Q BO’LSA
    if not order_types:
        await update.message.reply_text(
            "⚠️ Bu bo‘limda texnik ishlar olib borilmoqda.\n"
            "Tez orada faol bo‘ladi!"
        )
        return ConversationHandler.END

    buttons = []
    for t in order_types:
        if t.is_active:
            text = f"{t.name} — {t.price} so‘m"
        else:
            text = strike(f"{t.name} — {t.price} so‘m")

        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"order_type_{t.id}"
            )
        ])

    kb = InlineKeyboardMarkup(buttons)

    await update.message.reply_video(
        video="https://t.me/Hobbiy_bots/4",
        caption="📌 *Zakaz turini tanlang:*",
        reply_markup=kb,
        parse_mode="Markdown"
    )

    return WAIT_CHOOSE_TYPE


async def select_order_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    type_id = int(query.data.split("_")[2])
    order_type = await sync_to_async(OrderType.objects.get)(id=type_id)

    if not order_type.is_active:
        await query.answer("⏳ Bu funksiya tez orada faol bo‘ladi!", show_alert=True)
        return WAIT_CHOOSE_TYPE

    context.user_data["order_type"] = order_type

    await query.message.reply_text(
        f"🖼 Rasm yuboring\n"
        f"Tanlangan tarif: *{order_type.name}* ({order_type.price} so‘m)",
        parse_mode="Markdown"
    )

    return WAIT_IMAGE

async def receive_order_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Faqat rasm yuboring!")
        return WAIT_IMAGE

    file_id = update.message.photo[-1].file_id
    context.user_data["image_file_id"] = file_id

    await update.message.reply_text("✍️ Endi tavsif kiriting (nima qilinsin?)")

    return WAIT_DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["user_description"] = text

    order_type = context.user_data["order_type"]

    confirm_btns = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ha", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Yo‘q", callback_data="confirm_no")
        ]
    ])

    await update.message.reply_photo(
        photo=context.user_data["image_file_id"],
        caption=(
            "📌 *Tasdiqlaysizmi?*\n\n"
            f"🧾 Tarif: *{order_type.name}*\n"
            f"💰 Narx: *{order_type.price} so‘m*\n"
            f"📝 Tavsif: {text}"
        ),
        parse_mode="Markdown",
        reply_markup=confirm_btns
    )

    return WAIT_CONFIRM

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.message.reply_text("❌ Bekor qilindi.")
        return ConversationHandler.END

    user = context.user_data["user"]
    order_type = context.user_data["order_type"]
    image_file_id = context.user_data["image_file_id"]
    user_desc = context.user_data["user_description"]

    # Balansni tekshirish
    if user.balance < order_type.price:
        await query.message.reply_text("❌ Balansingizda mablag‘ yetarli emas!")
        return ConversationHandler.END

    # Balansdan yechish
    user.balance -= order_type.price
    await sync_to_async(user.save)()

    # Order yaratish
    order = await sync_to_async(VideoOrder.objects.create)(
        user=user,
        image_file_id=image_file_id,
        amount=order_type.price,
        order_type=order_type,
        status="waiting",
        cancel_reason=user_desc
    )
    reply_markup = order_accept_button(order.id)

    # Admin kanalga yuborish
    await context.bot.send_photo(
        chat_id=ADMIN_CHANNEL_ID,
        photo=image_file_id,
        caption=(
            f"🎬 *Yangi Zakaz*\n\n"
            f"👤 User: @{user.username}\n"
            f"🆔 TG ID: {user.user_id}\n"
            f"📦 Tarif: {order_type.name}\n"
            f"💰 Narx: {order_type.price} so‘m\n"
            f"📝 Tavsif: {user_desc}\n"
            f"📌 Zakaz ID: {order.id}"
        ),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    await query.message.reply_text("✅ Zakaz qabul qilindi. Jarayon boshlandi!")

    return ConversationHandler.END


video_order_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(r"^🎞 Video yaratish$"), start_video_order)],
    states={
        WAIT_CHOOSE_TYPE: [CallbackQueryHandler(select_order_type, pattern=r"^order_type_\d+$")],
        WAIT_IMAGE: [MessageHandler(filters.PHOTO, receive_order_image)],
        WAIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
        WAIT_CONFIRM: [CallbackQueryHandler(confirm_order, pattern=r"^confirm_(yes|no)$")],
    },
    fallbacks=[]
)
