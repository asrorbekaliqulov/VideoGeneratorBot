from django.utils import timezone
from apps.Bot.models.TelegramBot import Payment
from asgiref.sync import sync_to_async


async def payment_callback(update, context):
    query = update.callback_query
    data = query.data

    if data.startswith("pay_ok_"):
        await query.answer("Tasdiqlanmoqda")

        payment_id = int(data.replace("pay_ok_", ""))

        # Payment va userni olish (select_related bilan query optimallashtirish)
        payment = await sync_to_async(Payment.objects.select_related("user").get)(id=payment_id)

        # --- DB update --- #
        async def update_payment_and_balance():
            payment.status = "success"
            payment.confirmed_at = timezone.now()
            # User balansini oshirish
            payment.user.balance += payment.amount
            # Save user va payment
            await sync_to_async(payment.user.save)()
            await sync_to_async(payment.save)()

        await update_payment_and_balance()

        # Admin kanal xabarini yangilash
        await query.edit_message_caption(
            caption=(
                f"✅ TO‘LOV TASDIQLANDI!\n\n"
                f"Payment ID: {payment.id}\n"
                f"User: @{payment.user.username}\n"
                f"Summa: {payment.amount} so‘m\n"
                f"Yangi balans: {payment.user.balance} so‘m"
            )
        )

        # Userga xabar yuborish
        await context.bot.send_message(
            chat_id=payment.user.user_id,
            text=(
                f"🎉 To‘lovingiz tasdiqlandi!\n"
                f"Hisobingizga {payment.amount} so‘m tushdi.\n"
                f"Yangi balans: {payment.user.balance} so‘m"
            )
        )

    elif data.startswith("pay_no_"):
        await query.answer("Bekor qilinmoqda")

        payment_id = int(data.replace("pay_no_", ""))

        payment = await sync_to_async(Payment.objects.select_related("user").get)(id=payment_id)

        # Payment statusni yangilash
        async def reject_payment():
            payment.status = "rejected"
            await sync_to_async(payment.save)()

        await reject_payment()

        await query.edit_message_caption(
            caption=(
                f"❌ TO‘LOV RAD ETILDI!\n\n"
                f"Payment ID: {payment.id}\n"
                f"User: @{payment.user.username}"
            )
        )

        await context.bot.send_message(
            chat_id=payment.user.user_id,
            text="❌ To‘lovingiz rad etildi. Iltimos qayta urinib ko‘ring."
        )


