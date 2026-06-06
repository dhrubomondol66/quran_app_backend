from django.conf import settings
from django.db import models
from django.utils import timezone
import stripe

class Subscription(models.Model):
    class Plan(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=False)
    plan = models.CharField(
        max_length=20,
        choices=Plan.choices,
        default=Plan.MONTHLY,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "subscription"
        verbose_name_plural = "subscriptions"

    def __str__(self):
        return f"{self.user} — {self.plan} ({'active' if self.is_valid() else 'inactive'})"

    def is_valid(self):
        if not self.is_active:
            return False
        # if self.expires_at and self.expires_at < timezone.now():
        #     return False
        return True
