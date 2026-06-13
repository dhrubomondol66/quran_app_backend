from django.urls import path
from .views import (
    CreateSubscriptionView,
    MySubscriptionView,
    CancelSubscriptionView,    # ← cancel subscription (calls Stripe)
    SuccessView,
    CancelView,                # ← checkout cancelled landing
    StripeWebhookView,         # ← new webhook class view
    UserSubscriptionPlansView,
    ToggleAutoRenewalView,
    PaymentHistoryView,
    RestoreSubscriptionView,
    ConfirmPaymentView,
)
from .webhook import stripe_webhook

urlpatterns = [
    path("my-subscription/",     MySubscriptionView.as_view()),
    path("create-subscription/", CreateSubscriptionView.as_view()),
    path("cancel-subscription/", CancelSubscriptionView.as_view()),  # ← new
    path("webhook/",             stripe_webhook, name="stripe-webhook"),
    path("webhook/stripe/",      StripeWebhookView.as_view()),      # ← new in-app payment webhook
    path("success/",             SuccessView.as_view()),
    path("cancel/",              CancelView.as_view()),
    path("plans/",               UserSubscriptionPlansView.as_view()),
    path("toggle-auto-renewal/", ToggleAutoRenewalView.as_view()),
    path("payment-history/",     PaymentHistoryView.as_view()),
    path("restore-subscription/", RestoreSubscriptionView.as_view()),
    path("confirm-payment/",     ConfirmPaymentView.as_view()),
]