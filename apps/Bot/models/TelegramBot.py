from django.db import models
from django.utils.timezone import now
from django.db.models import Count
from asgiref.sync import sync_to_async
from django.utils.text import slugify


# Create your models here.

class TelegramUser(models.Model):

    user_id = models.BigIntegerField(null=False, unique=True, verbose_name="Telegram User ID")
    first_name = models.CharField(max_length=256, blank=True, null=True, verbose_name="First Name")
    username = models.CharField(max_length=256, blank=True, null=True, verbose_name="Username")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Date Joined")
    last_active = models.DateTimeField(auto_now=True, verbose_name="Last Active")
    is_admin = models.BooleanField(default=False, verbose_name="Is Admin")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    balance = models.IntegerField(default=0)

    
    class Meta:
        verbose_name = "Telegram User"
        verbose_name_plural = "Telegram Users"
        ordering = ['-last_active']

    def __str__(self):
        return f"{self.first_name} (@{self.username})" if self.username else f"{self.user_id}"


    @classmethod
    async def get_admin_ids(cls):
        """
        Admin bo'lgan userlarning IDlarini qaytaradi.
        """
        return await sync_to_async(
            lambda: list(cls.objects.filter(is_admin=True).values_list('user_id', flat=True))
        )()

    @classmethod
    async def get_today_new_users(cls):
        """
        Bugungi yangi foydalanuvchilarni qaytaradi.
        """
        today = now().date()
        return await sync_to_async(lambda: list(cls.objects.filter(date_joined__date=today)))()

    @classmethod
    async def get_daily_new_users(cls):
        """
        Har bir kun uchun yangi foydalanuvchilar sonini qaytaradi.
        """
        return await sync_to_async(
            lambda: list(cls.objects.values('date_joined__date').annotate(count=Count('id')).order_by('-date_joined__date'))
        )()

    @classmethod
    async def get_total_users(cls):
        """
        Umumiy foydalanuvchilar sonini qaytaradi.
        """
        return await sync_to_async(cls.objects.count)()

    @classmethod
    async def count_admin_users(cls):
        """
        Admin bo'lgan foydalanuvchilar sonini qaytaradi.
        """
        return await sync_to_async(lambda: cls.objects.filter(is_admin=True).count())()



    @classmethod
    async def find_inactive_users(cls, bot_token):
        """
        Nofaol foydalanuvchilarni aniqlaydi.
        :param bot_token: Telegram bot tokeni
        :return: Bloklangan foydalanuvchilar soni
        """
        from telegram import Bot
        from telegram.error import TelegramError

        bot = Bot(token=bot_token)
        blocked_users_count = 0

        # SyncToAsync faqat Django ORM bilan ishlashda kerak
        users = await sync_to_async(lambda: list(cls.objects.all()))()

        for user in users:
            try:
                await bot.send_chat_action(chat_id=user.user_id, action="typing")
            except TelegramError:
                blocked_users_count += 1

        return blocked_users_count

    @classmethod
    async def make_admin(cls, user_id):
        """
        Userni admin qiladi.
        :param user_id: Admin qilinadigan foydalanuvchining Telegram user_id-si
        :return: Yangilangan user obyekti yoki None (user topilmasa)
        """
        try:
            user = await sync_to_async(cls.objects.get)(user_id=user_id)
            user.is_admin = True
            await sync_to_async(user.save)(update_fields=['is_admin'])
            return user
        except cls.DoesNotExist:
            print(f"User with ID {user_id} does not exist.")
            return None

    @classmethod
    async def remove_admin(cls, user_id):
        """
        Userni adminlikdan chiqaradi.
        :param user_id: Adminlikdan chiqariladigan foydalanuvchining Telegram user_id-si
        :return: Yangilangan user obyekti yoki None (user topilmasa)
        """
        try:
            user = await sync_to_async(cls.objects.get)(user_id=user_id)
            user.is_admin = False
            await sync_to_async(user.save)(update_fields=['is_admin'])
            return user
        except cls.DoesNotExist:
            print(f"User with ID {user_id} does not exist.")
            return None

    @property
    def accuracy_rate(self):
        """Aniqlik darajasini foizlarda qaytaradi"""
        if self.total_questions_answered == 0:
            return 0
        return round((self.correct_answers / self.total_questions_answered) * 100, 2)

    @classmethod
    async def update_quiz_stats(cls, user_id, is_correct, points=1):
        """
        O'yin statistikasini yangilash
        :param user_id: Foydalanuvchi ID si
        :param is_correct: Javob to'g'ri yoki noto'g'ri ekanligi
        :param points: Qo'shiladigan ballar (default=1)
        """
        try:
            user = await sync_to_async(cls.objects.select_for_update().get)(user_id=user_id)
            
            # Umumiy statistikani yangilash
            user.total_questions_answered += 1
            user.total_points += points if is_correct else 0
            
            if is_correct:
                user.correct_answers += 1
                user.current_streak += 1
                user.best_streak = max(user.current_streak, user.best_streak)
            else:
                user.wrong_answers += 1
                user.current_streak = 0
            
            user.last_quiz_date = now()
            
            await sync_to_async(user.save)()
            return user
            
        except cls.DoesNotExist:
            return None

    @classmethod
    async def update_highest_score(cls, user_id, score):
        """
        Eng yuqori natijani yangilash
        :param user_id: Foydalanuvchi ID si
        :param score: Yangi natija
        """
        try:
            user = await sync_to_async(cls.objects.get)(user_id=user_id)
            if score > user.highest_score:
                user.highest_score = score
                await sync_to_async(user.save)(update_fields=['highest_score'])
            return user
        except cls.DoesNotExist:
            return None

    @classmethod
    async def get_top_players(cls, limit=10):
        """
        Eng ko'p ball to'plagan o'yinchilar ro'yxatini qaytaradi
        :param limit: Qaytariladigan o'yinchilar soni
        """
        return await sync_to_async(
            lambda: list(cls.objects.order_by('-total_points')[:limit])
        )()



class Channel(models.Model):
    """Kanal yoki guruh haqida ma'lumotlarni saqlash uchun model."""
    CHANNEL_TYPE_CHOICES = [
        ('channel', 'Kanal'),
        ('group', 'Guruh'),
        ('joinrequest', 'JoinRequest'),
    ]

    channel_id = models.CharField(max_length=255, unique=True)  # Kanal ID
    name = models.CharField(max_length=255)  # Kanal nomi
    type = models.CharField(max_length=15, choices=CHANNEL_TYPE_CHOICES)  # Kanal turi
    url = models.URLField(null=True, blank=True)  # Kanalning URL manzili (agar mavjud bo'lsa)

    def __str__(self):
        return self.name



class Referral(models.Model):
    referrer = models.ForeignKey(
        "TelegramUser", on_delete=models.CASCADE, related_name="referred_users", verbose_name="Taklif qiluvchi foydalanuvchi"
    )
    referred_user = models.ForeignKey(
        "TelegramUser", on_delete=models.CASCADE, related_name="referrals", verbose_name="Taklif qilingan foydalanuvchi"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Taklif qilingan sana")
    referral_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Referral narxi", default=0.0
    )

    class Meta:
        verbose_name = "Referral"
        verbose_name_plural = "Referral"

    def __str__(self):
        return f"{self.referrer} → {self.referred_user}"


class Guide(models.Model):
    """
    Foydalanuvchilarga yordam berish uchun qo'llanma
    """
    title = models.CharField(max_length=255, verbose_name="Sarlavha")
    content = models.TextField(verbose_name="Kontent")
    status = models.BooleanField(default=True, verbose_name="Holat")  # True - faol, False - nofaol
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")

    class Meta:
        verbose_name = "Guide"
        verbose_name_plural = "Guides"

    def __str__(self):
        return self.title
    

class Appeal(models.Model):
    """
    Foydalanuvchilarning murojaatlarini saqlash uchun model
    """
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, verbose_name="Foydalanuvchi")
    admin = models.ForeignKey(
        TelegramUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_appeals", verbose_name="Admin"
    )
    message_id = models.BigIntegerField(null=True, blank=True, verbose_name="Murojaat xabar ID")
    message = models.TextField(verbose_name="Murojaat matni")
    status = models.BooleanField(default=False, verbose_name="Holat")  # True - ko'rilgan, False - ko'rilmagan
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    
    class Meta:
        verbose_name = "Appeal"
        verbose_name_plural = "Appeals"
    
    def __str__(self):
        return f"Murojaat: {self.user.first_name} - {self.message[:50]}"

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='payments')
    amount = models.IntegerField()
    screenshot_file_id = models.CharField(max_length=300)  # telegram file_id
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment #{self.id} - {self.user.username} - {self.status}"

class OrderType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    price = models.IntegerField()  # bazaviy narx
    description = models.TextField()  # HTML bilan yozish uchun mos
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.price} so'm)"

class VideoOrder(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='video_orders')
    order_type = models.ForeignKey(OrderType, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="orders")  # YANGI

    image_file_id = models.CharField(max_length=300)  # User yuborgan rasm
    video_file_id = models.CharField(max_length=300, null=True, blank=True)  # Tayyor video

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    amount = models.IntegerField(default=15000)

    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"VideoOrder #{self.id} - {self.user.user_id} - {self.status}"



