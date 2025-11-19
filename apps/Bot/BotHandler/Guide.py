from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from ..models.TelegramBot import Guide
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from ..decorators import mandatory_channel_required, admin_required
from asgiref.sync import sync_to_async
from telegram.ext import ConversationHandler

@mandatory_channel_required
async def guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Sends a guide message to the user when they request help.
    """
    # Faqat status=True bo'lganlarni olish va id bo'yicha tartiblash
    guides = await sync_to_async(lambda: list(Guide.objects.filter(status=True).order_by('id')))()
    if len(guides) >= 2:
        guide_content = ""
        for guide in guides:
            guide_content += f"<b>{guide.title}</b>\n\n{guide.content}\n〰️〰️〰️〰️\n"
    elif guides:
        guide = guides[0]
        guide_content = f"<b>{guide.title}</b>\n\n{guide.content}"
    else:
        guide_content = "Qo'llanma mavjud emas"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=guide_content,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back to Main Menu", callback_data="Main_Menu")]
            ])
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=guide_content,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back to Main Menu", callback_data="Main_Menu")]
            ])
        )


CREATE_TITLE, CREATE_CONTENT, UPDATE_SELECT, UPDATE_TITLE, UPDATE_CONTENT, DELETE_SELECT = range(6)

cancel_button = InlineKeyboardButton("Bekor qilish", callback_data='cancel')


@admin_required
async def start_create_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Yangi qo'llanma sarlavhasini kiriting:", reply_markup=InlineKeyboardMarkup([[cancel_button]]))
    return CREATE_TITLE

async def create_guide_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['guide_title'] = update.message.text
    await update.message.reply_text("Qo'llanma matnini kiriting:", reply_markup=InlineKeyboardMarkup([[cancel_button]]))
    return CREATE_CONTENT

async def create_guide_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = context.user_data['guide_title']
    content = update.message.text_html
    await sync_to_async(Guide.objects.create)(title=title, content=content, status=True)
    await update.message.reply_text("Qo'llanma muvaffaqiyatli yaratildi.")
    return ConversationHandler.END

@admin_required
async def start_update_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guides = await sync_to_async(lambda: list(Guide.objects.filter(status=True).order_by('id')))()
    if not guides:
        await update.message.reply_text("Hech qanday qo'llanma mavjud emas.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(g.title, callback_data=str(g.id))] for g in guides]
    keyboard.append([cancel_button])
    await update.message.reply_text("O'zgartirmoqchi bo'lgan qo'llanmani tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    return UPDATE_SELECT

async def update_guide_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    guide_id = int(query.data)
    context.user_data['update_guide_id'] = guide_id
    guide = await sync_to_async(Guide.objects.get)(id=guide_id)
    await query.edit_message_text(f"Hozirgi sarlavha: {guide.title}\nYangi sarlavhani kiriting (yoki eski sarlavhani qayta kiriting):", reply_markup=InlineKeyboardMarkup([[cancel_button]]))
    return UPDATE_TITLE

async def update_guide_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['update_guide_title'] = update.message.text
    await update.message.reply_text("Yangi matnni kiriting (yoki eski matnni qayta kiriting):", reply_markup=InlineKeyboardMarkup([[cancel_button]]))
    return UPDATE_CONTENT

async def update_guide_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guide_id = context.user_data['update_guide_id']
    title = context.user_data['update_guide_title']
    content = update.message.text_html
    await sync_to_async(Guide.objects.filter(id=guide_id).update)(title=title, content=content)
    await update.message.reply_text("Qo'llanma muvaffaqiyatli o'zgartirildi.")
    return ConversationHandler.END

@admin_required
async def start_delete_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guides = await sync_to_async(lambda: list(Guide.objects.filter(status=True).order_by('id')))()
    if not guides:
        await update.message.reply_text("Hech qanday qo'llanma mavjud emas.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(g.title, callback_data=str(g.id))] for g in guides]
    keyboard.append([cancel_button])
    await update.message.reply_text("O'chirmoqchi bo'lgan qo'llanmani tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DELETE_SELECT

async def delete_guide_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    guide_id = int(query.data)
    await sync_to_async(Guide.objects.filter(id=guide_id).update)(status=False)
    await query.edit_message_text("Qo'llanma muvaffaqiyatli o'chirildi.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Amal bekor qilindi.")
    return ConversationHandler.END

guide_create_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^Yangi qo\'llanma yaratish$'), start_create_guide)],
    states={
        CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_guide_title)],
        CREATE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_guide_content)],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')],  # Add cancel fallback
    allow_reentry=True  # Allow re-entry into the conversation
)

guide_update_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^Qo\'llanmani yangilash$'), start_update_guide)],
    states={
        UPDATE_SELECT: [CallbackQueryHandler(update_guide_select)],
        UPDATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_guide_title)],
        UPDATE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_guide_content)],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')],  # Add cancel fallback
    allow_reentry=True  # Allow re-entry into the conversation
)

guide_delete_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^Qo\'llanmani o\'chirish$'), start_delete_guide)],
    states={
        DELETE_SELECT: [CallbackQueryHandler(delete_guide_select)],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')],  # Add cancel fallback
    allow_reentry=True  # Allow re-entry into the conversation
)

async def AdminGuide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin uchun qo'llanma boshqarish menyusi.
    """
    await update.callback_query.answer("Admin Qo'llanma Boshqarish")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Admin Qo'llanma Boshqarish menyusi:",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("Yangi qo'llanma yaratish"), KeyboardButton("Qo'llanmani yangilash")],
            [KeyboardButton("Qo'llanmani o'chirish")]
        ], resize_keyboard=True, one_time_keyboard=True)
    )