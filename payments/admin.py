from django.contrib import admin
from .models import MpesaTransaction

@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_reference', 'reservation', 'amount', 'phone_number', 
                   'status', 'transaction_date', 'mpesa_receipt_number')
    list_filter = ('status', 'transaction_type', 'transaction_date')
    search_fields = ('transaction_reference', 'phone_number', 'mpesa_receipt_number')
    readonly_fields = ('transaction_reference', 'transaction_date', 'mpesa_receipt_number', 
                      'result_code', 'result_description')
    ordering = ('-transaction_date',)
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_reference', 'reservation', 'transaction_type', 
                      'amount', 'phone_number', 'status')
        }),
        ('M-Pesa Response', {
            'fields': ('mpesa_receipt_number', 'result_code', 'result_description'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('transaction_date',),
        }),
    )