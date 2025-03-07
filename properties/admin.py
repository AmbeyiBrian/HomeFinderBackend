from django.contrib import admin
from .models import Property, PropertyType, PropertyImage, Favorite, Reservation

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'city', 'state', 'status')
    list_filter = ('status', 'property_type', 'city', 'state')
    search_fields = ('title', 'address', 'city', 'state')

@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'is_primary')
    list_filter = ('is_primary',)

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'property', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('user__username', 'property__title')
    raw_id_fields = ('property',)

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'property', 'reservation_price', 'status', 'payment_status', 'total_amount', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('user__username', 'property__title', 'property__address', 'payment_reference')
    raw_id_fields = ('property', 'user')
    readonly_fields = ('booking_fee', 'total_amount', 'payment_reference')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
