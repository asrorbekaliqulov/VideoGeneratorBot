from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from apps.Bot.models.TelegramBot import VideoOrder   # o'zingdagi model nomiga moslashtir

async def my_videos(update, context):
    chat_id = update.message.chat_id
    await send_user_orders(chat_id, context, page=1)

async def send_user_orders(chat_id, context, page: int = 1):
    PAGE_SIZE = 10

    orders = await sync_to_async(list)(
        VideoOrder.objects.filter(user__user_id=chat_id).order_by("-id")
    )

    total = len(orders)

    if total == 0:
        await context.bot.send_message(chat_id, "❗ Sizda hali video zakazlar mavjud emas.")
        return

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_orders = orders[start:end]

    kb = []
    row = []

    # === HAR QATORDA 5 TA TUGMA ===
    for idx, order in enumerate(page_orders, start=1):
        row.append(
            InlineKeyboardButton(
                f"#{order.id}",
                callback_data=f"order_view:{order.id}:{page}"
            )
        )

        if idx % 5 == 0:  # har 5 ta tugmadan keyin yangi qator
            kb.append(row)
            row = []

    if row:
        kb.append(row)

    # Pagination
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"orders_page:{page-1}"))
    if end < total:
        nav_row.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"orders_page:{page+1}"))
    if nav_row:
        kb.append(nav_row)

    # Orqaga va Menu
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_menu")])
    kb.append([InlineKeyboardButton("🏠 Asosiy menu", callback_data="MainMenu")])

    await context.bot.send_message(
        chat_id,
        f"📄 Sizning videolaringiz ro‘yxati (Jami: {total} ta)\n"
        f"📑 Sahifa: {page}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def paginate_orders(update, context):
    query = update.callback_query
    await query.answer()

    page = int(query.data.split(":")[1])

    # eski xabarni o'chiramiz
    try:
        await query.message.delete()
    except:
        pass

    await send_user_orders(query.message.chat_id, context, page)


from telegram import InputMediaPhoto, InputMediaVideo

async def order_view(update, context):
    query = update.callback_query
    await query.answer()

    _, order_id, page = query.data.split(":")
    page = int(page)

    # 🟢 Orderni olish
    order = await sync_to_async(VideoOrder.objects.select_related("order_type").get)(id=order_id)

    # 🟢 ForeignKey obyektni async bilan olish
    if order.order_type_id:
        order_type = await sync_to_async(lambda: order.order_type.name)()
    else:
        order_type = "—"

    # Xabarni o‘chirish
    try:
        await query.message.delete()
    except:
        pass

    # Media yuborish
    media = []
    if order.image_file_id:
        media.append(InputMediaPhoto(order.image_file_id))
    if order.video_file_id:
        media.append(InputMediaVideo(order.video_file_id))

    if media:
        await context.bot.send_media_group(chat_id=query.message.chat_id, media=media)

    # Matn
    text = (
        f"🎬 *Zakaz ID:* {order.id}\n"
        f"📅 Sana: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"📌 Holat: {order.get_status_display()}\n"
        f"💰 Narx: {order.amount} so'm\n"
        f"📝 Buyurtma turi: {order_type}\n"
        f"⏳ Tugagan vaqt: {order.finished_at.strftime('%Y-%m-%d %H:%M') if order.finished_at else '—'}\n\n"
        f"ℹ️: {order.cancel_reason or '—'}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"orders_page:{page}")],
        [InlineKeyboardButton("🏠 Asosiy menu", callback_data="MainMenu")]
    ])

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=kb
    )
