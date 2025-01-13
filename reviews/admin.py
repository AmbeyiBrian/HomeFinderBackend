from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'property', 'user', 'rating', 'created_at', 'updated_at')
    list_filter = ('property', 'rating', 'created_at')
    search_fields = ('property__title', 'user__username', 'rating')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
