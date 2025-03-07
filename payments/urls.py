from django.urls import path
from .views import InitiateMpesaPaymentView, MpesaCallbackView, CheckPaymentStatusView

urlpatterns = [
    path('initiate/', InitiateMpesaPaymentView.as_view(), name='initiate-payment'),
    path('callback/', MpesaCallbackView.as_view(), name='mpesa-callback'),
    path('status/<str:transaction_ref>/', CheckPaymentStatusView.as_view(), name='check-payment-status'),
]