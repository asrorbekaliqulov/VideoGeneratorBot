from django.contrib import admin
from ..models.TelegramBot import TelegramUser, Channel, Referral, Guide, Appeal, Payment, OrderType, VideoOrder
from django.contrib import admin
from unfold.admin import ModelAdmin


@admin.register(TelegramUser)
class UserAdmin(ModelAdmin):
    list_display = ("user_id", "first_name", "username", "is_active", "is_admin", "date_joined", "last_active")
    list_filter = ("is_active", "is_admin")
    search_fields = ("username", "first_name")
    ordering = ("user_id",)
    list_editable = ("is_active", "is_admin")


@admin.register(Channel)
class ChannelAdmin(ModelAdmin):
    list_display = ('name', 'type', 'url', 'channel_id')  # Jadval ustunlari
    list_filter = ('type',)  # Filtrlash uchun ustunlar
    search_fields = ('name', 'channel_id')  # Qidiruv uchun ustunlar


@admin.register(Referral)
class ReferralAdmin(ModelAdmin):
    list_display = ('referrer', 'referred_user', 'created_at')  # Jadval ustunlari
    search_fields = ('referrer__username', 'referred_user__username')  # Qidiruv uchun ustunlar

@admin.register(Guide)
class GuideAdmin(ModelAdmin):
    list_display = ('title', 'status', 'created_at')
    search_fields = ('title', 'content')

@admin.register(Appeal)
class AppealAdmin(ModelAdmin):
    list_display = ('user', 'message', 'created_at')
    search_fields = ('user__username', 'message')
    list_filter = ('created_at',)



# ==========================
#  PAYMENT ADMIN
# ==========================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'status', 'created_at', 'confirmed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'id')
    ordering = ('-created_at',)

    readonly_fields = ('created_at', 'confirmed_at')

    # Admin ichida statusni tez o'zgartirish
    actions = ['mark_as_success', 'mark_as_rejected']

    def mark_as_success(self, request, queryset):
        updated = queryset.update(status='success')
        self.message_user(request, f"{updated} ta to'lov tasdiqlandi.")

    mark_as_success.short_description = "Tanlangan to'lovlarni SUCCESS qilish"

    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f"{updated} ta to'lov bekor qilindi.")

    mark_as_rejected.short_description = "Tanlangan to'lovlarni REJECT qilish"


# ==========================
#  ORDER TYPE ADMIN
# ==========================

@admin.register(OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    ordering = ('-created_at',)

    readonly_fields = ('created_at', 'updated_at')

    prepopulated_fields = {"slug": ("name",)}



# ==========================
#  VIDEO ORDER ADMIN
# ==========================

@admin.register(VideoOrder)
class VideoOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order_type', 'status', 'amount', 'created_at', 'finished_at')
    list_filter = ('status', 'order_type', 'created_at')
    search_fields = ('user__username', 'id')
    ordering = ('-created_at',)

    readonly_fields = ('created_at', 'finished_at')

    actions = ['mark_done', 'mark_canceled']

    def mark_done(self, request, queryset):
        updated = queryset.update(status='done')
        self.message_user(request, f"{updated} ta zakaz DONE bo‘ldi.")

    mark_done.short_description = "Tanlangan zakazlarni DONE qilish"

    def mark_canceled(self, request, queryset):
        updated = queryset.update(status='canceled')
        self.message_user(request, f"{updated} ta zakaz CANCELED qilindi.")

    mark_canceled.short_description = "Tanlangan zakazlarni CANCELED qilish"

