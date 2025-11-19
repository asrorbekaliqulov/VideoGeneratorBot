from django.db.models import Sum
from telegram import Update
from telegram.constants import ParseMode
from asgiref.sync import sync_to_async
from telegram.ext import ContextTypes

from apps.Bot.models.TelegramBot import TelegramUser, VideoOrder, Payment


async def profil_korish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # === 1. User maʼlumotlarini olish ===
    user = await sync_to_async(TelegramUser.objects.get)(user_id=user_id)

    # === 2. Video statistika ===
    total_videos = await sync_to_async(VideoOrder.objects.filter(user=user).count)()
    success_videos = await sync_to_async(VideoOrder.objects.filter(user=user, status="done").count)()
    canceled_videos = await sync_to_async(VideoOrder.objects.filter(user=user, status="canceled").count)()

    # === 3. To'lov statistika ===
    total_payments = await sync_to_async(Payment.objects.filter(user=user, status="success").count)()
    total_amount = await sync_to_async(
        lambda: Payment.objects.filter(user=user, status="success").aggregate(Sum("amount"))["amount__sum"]
    )()
    total_amount = total_amount or 0  # None bo‘lsa 0 bo‘lsin

    # === 4. Profil xabarini yig‘ish ===
    text = (
        f"🧾 <b>Profilingiz</b>\n\n"
        f"👤 <b>Ism:</b> {user.first_name or 'Nomaʼlum'}\n"
        f"🔗 <b>Username:</b> @{user.username if user.username else 'yo‘q'}\n"
        f"🆔 <b>User ID:</b> <code>{user.user_id}</code>\n\n"

        f"📅 <b>Botga qo‘shilgan:</b> {user.date_joined.strftime('%Y-%m-%d %H:%M')}\n"
        f"🕒 <b>Oxirgi aktivlik:</b> {user.last_active.strftime('%Y-%m-%d %H:%M')}\n\n"

        f"🎞 <b>Videolar statistika:</b>\n"
        f"    • Jami: <b>{total_videos}</b>\n"
        f"    • Muvaffaqiyatli: <b>{success_videos}</b>\n"
        f"    • Bekor qilingan: <b>{canceled_videos}</b>\n\n"

        f"💳 <b>To‘lovlar:</b>\n"
        f"    • Muvaffaqiyatli to‘lovlar soni: <b>{total_payments}</b>\n"
        f"    • Jami to‘langan summa: <b>{total_amount:,} so‘m</b>\n\n"

        f"💰 <b>Balansingiz:</b> <b>{user.balance:,} so‘m</b>\n"
    )

    # === 5. Xabarni yuborish ===
    await context.bot.send_video(
        video="https://t.me/Hobbiy_bots/5",
        chat_id=user_id,
        caption=text,
        parse_mode="HTML"
    )
