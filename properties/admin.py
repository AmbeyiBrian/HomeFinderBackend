from django.contrib import admin
from .models import Property, PropertyType, PropertyImage, Favorite

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
    list_display = ('user', 'property', 'created_at')  # Display user, property, and the creation date
    list_filter = ('user', 'created_at')  # Filter by user and creation date
    search_fields = ('user__username', 'property__title')  # Search by username and property title
    raw_id_fields = ('property',)  # Use a raw ID field for property, which helps with large datasets
