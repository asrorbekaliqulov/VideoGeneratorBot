from click import Context
from apps.Bot.models.TelegramBot import TelegramUser, VideoOrder, OrderType
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from asgiref.sync import sync_to_async
from ..BotCommands.StartCommand import get_user_keyboard
import os

ADMIN_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID")

WAIT_CHOOSE_TYPE, WAIT_IMAGE, WAIT_DESCRIPTION, WAIT_CONFIRM = range(4)


def strike(text: str) -> str:
    return "".join(char + "\u0336" for char in text)


def order_accept_button(order_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Qabul qilish", callback_data=f"order_accept:{order_id}")]
    ])


# ⬅️ ORQAGA tugmasi generatori
def back_button(cb_data="back"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data=cb_data)]
    ])


async def start_video_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.message.from_user
    keyboard_rm = ReplyKeyboardRemove()

    await context.bot.send_video(
        chat_id=tg_user.id,
        video="https://t.me/Hobbiy_bots/4",
        reply_markup=keyboard_rm,
    )

    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=tg_user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Siz ro‘yxatdan o‘tmagansiz!")
        return ConversationHandler.END

    context.user_data["user"] = user

    return await show_order_types(update, context)


async def show_order_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_types = await sync_to_async(list)(
        OrderType.objects.all().order_by('-is_active', 'price')
    )

    if not order_types:
        await update.message.reply_text("⚠️ Bu bo‘limda texnik ishlar olib borilmoqda.")
        return ConversationHandler.END

    buttons = []
    for t in order_types:
        text = f"{t.name} — {t.price} so‘m" if t.is_active else strike(f"{t.name} — {t.price} so‘m")
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"order_type_{t.id}")])
    buttons.append([InlineKeyboardButton(text="Bekor qilish", callback_data="cancel")])
    kb = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("📌 *Zakaz turini tanlang:*", reply_markup=kb, parse_mode="Markdown")
    return WAIT_CHOOSE_TYPE


async def select_order_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_main":
        return await show_order_types(query, context)

    type_id = int(query.data.split("_")[2])
    order_type = await sync_to_async(OrderType.objects.get)(id=type_id)

    if not order_type.is_active:
        await query.answer("⏳ Bu funksiya tez orada faol bo‘ladi!", show_alert=True)
        return WAIT_CHOOSE_TYPE

    context.user_data["order_type"] = order_type

    await query.message.reply_text(
        f"🖼 Rasm yuboring\nTanlangan tarif: *{order_type.name}* ({order_type.price} so‘m)",
        parse_mode="Markdown",
        reply_markup=back_button("back_main")
    )

    return WAIT_IMAGE


async def receive_order_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Faqat rasm yuboring!")
        return WAIT_IMAGE

    context.user_data["image_file_id"] = update.message.photo[-1].file_id

    await update.message.reply_text(
        "✍️ Endi tavsif kiriting (nima qilinsin?)",
        reply_markup=back_button("back_image")
    )

    return WAIT_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["user_description"] = text

    order_type = context.user_data["order_type"]

    confirm_btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ha", callback_data="confirm_yes"),
         InlineKeyboardButton("❌ Yo‘q", callback_data="confirm_no")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_description")]
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

    # ⬅️ ORQAGA bosilsa → tavsif bosqichiga qaytish
    if query.data == "back_description":
        await query.message.reply_text(
            "✍️ Tavsifni qayta kiriting:",
            reply_markup=back_button("back_image")
        )
        return WAIT_DESCRIPTION

    if query.data == "confirm_no":
        await query.message.reply_text("❌ Bekor qilindi.")
        return ConversationHandler.END

    user = context.user_data["user"]
    order_type = context.user_data["order_type"]
    user_desc = context.user_data["user_description"]

    if user.balance < order_type.price:
        await query.message.reply_text("❌ Balansingizda mablag‘ yetarli emas!")
        return ConversationHandler.END

    user.balance -= order_type.price
    await sync_to_async(user.save)()

    order = await sync_to_async(VideoOrder.objects.create)(
        user=user,
        image_file_id=context.user_data["image_file_id"],
        amount=order_type.price,
        order_type=order_type,
        status="waiting",
        cancel_reason=user_desc
    )

    await context.bot.send_photo(
        chat_id=ADMIN_CHANNEL_ID,
        photo=context.user_data["image_file_id"],
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
        reply_markup=order_accept_button(order.id)
    )

    await query.message.reply_text("✅ Zakaz qabul qilindi. Jarayon boshlandi!")
    return ConversationHandler.END


# 🔥 Universal fallback
async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="❌ Xato ma’lumot kiritildi. Qaytadan boshlang: *🎞 Video yaratish*",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboardd = await get_user_keyboard()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="*Amal bekor qilindi*",
        reply_markup=keyboardd,
        parse_mode="Markdown"
    )
    return ConversationHandler.END


video_order_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(r"^🎞 Video yaratish$"), start_video_order)],
    states={
        WAIT_CHOOSE_TYPE: [
            CallbackQueryHandler(select_order_type, pattern=r"^order_type_\d+$")
        ],
        WAIT_IMAGE: [
            MessageHandler(filters.PHOTO, receive_order_image),
            CallbackQueryHandler(select_order_type, pattern="^back_main$")
        ],
        WAIT_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description),
            CallbackQueryHandler(receive_order_image, pattern="^back_image$")
        ],
        WAIT_CONFIRM: [
            CallbackQueryHandler(confirm_order, pattern=r"^(confirm_yes|confirm_no|back_description)$")
        ],
    },
    fallbacks=[MessageHandler(filters.ALL, fallback_handler),
               CallbackQueryHandler(cancel_order)]
)
