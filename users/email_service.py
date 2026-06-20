"""EmailJS service for sending password reset emails securely."""

import requests
import json
from django.conf import settings


class EmailJSService:
    """Service to send emails via EmailJS API from backend (secure)."""
    
    EMAILJS_API_URL = "https://api.emailjs.com/api/v1.0/email/send"
    
    @staticmethod
    def send_password_reset_email(user_email, reset_token, reset_url):
        """
        Send password reset email via EmailJS.
        
        Args:
            user_email: Email address of the user
            reset_token: Password reset token
            reset_url: Full URL for password reset link (with token/email)
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            payload = {
                "service_id": settings.EMAILJS_SERVICE_ID,
                "template_id": settings.EMAILJS_TEMPLATE_ID,
                "user_id": settings.EMAILJS_PUBLIC_KEY,
                "accessToken": settings.EMAILJS_PRIVATE_KEY,
                "template_params": {
                    "to_email": user_email,
                    "from_name": "Quran App",
                    "reset_token": reset_token,
                    "link": reset_url,
                    "user_email": user_email,
                }
            }
            print(f"DEBUG - payload: {payload}")
            
            headers = {
                "Content-Type": "application/json",
            }
            
            response = requests.post(
                EmailJSService.EMAILJS_API_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            
            # EmailJS returns 200 on success
            if response.status_code == 200:
                return True
            else:
                print(f"EmailJS Error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending email via EmailJS: {str(e)}")
            return False

    @staticmethod
    def send_payment_success_email(user_email, user_name, plan_name, amount, transaction_id, payment_method, payment_date):
        """
        Send payment success email via EmailJS.
        """
        try:
            payment_template_id = getattr(settings, "EMAILJS_PAYMENT_TEMPLATE_ID", "template_ue69xmd")
            payload = {
                "service_id": settings.EMAILJS_SERVICE_ID,
                "template_id": payment_template_id,
                "user_id": settings.EMAILJS_PUBLIC_KEY,
                "accessToken": settings.EMAILJS_PRIVATE_KEY,
                "template_params": {
                    "to_email": user_email,
                    "from_name": "Quran App",
                    "user_name": user_name,
                    "plan_name": plan_name,
                    "amount": amount,
                    "transaction_id": transaction_id,
                    "payment_method": payment_method,
                    "payment_date": payment_date,
                }
            }
            print(f"DEBUG - payment success payload: {payload}")
            
            headers = {
                "Content-Type": "application/json",
            }
            
            response = requests.post(
                EmailJSService.EMAILJS_API_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"EmailJS Error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending payment success email via EmailJS: {str(e)}")
            return False


def send_password_reset_email(user, reset_token, frontend_url="http://localhost:3000"):
    """
    Helper function to send password reset email.
    
    Args:
        user: User object
        reset_token: Password reset token from Django
        frontend_url: Frontend URL for reset link
    
    Returns:
        bool: True if successful
    """
    print(f"DEBUG - user: {user}")
    print(f"DEBUG - user.email: '{user.email}'")
    # Construct the full reset URL that frontend will use
    reset_link = f"{frontend_url}/reset-password?email={user.email}&token={reset_token}"
    
    return EmailJSService.send_password_reset_email(
        user_email=user.email,
        reset_token=reset_token,
        reset_url=reset_link
    )


def send_payment_success_email_helper(user, plan_name, amount, transaction_id, payment_method, payment_date=None):
    """
    Helper function to send payment success email.
    """
    if not payment_date:
        from django.utils import timezone
        payment_date = timezone.now().strftime("%B %d, %Y")
    
    # Format amount if it is numeric
    if isinstance(amount, (int, float)):
        amount = f"${amount:.2f}"
    
    return EmailJSService.send_payment_success_email(
        user_email=user.email,
        user_name=user.username,
        plan_name=plan_name.capitalize() if plan_name else "Premium Subscription",
        amount=amount,
        transaction_id=transaction_id,
        payment_method=payment_method,
        payment_date=payment_date
    )
