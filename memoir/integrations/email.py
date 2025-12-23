# =============================================================================
# Email Delivery Integration (AWS SES)
# =============================================================================
#
# Setup:
#   1. Verify your sending email in AWS SES console
#   2. Set env vars:
#      - AWS_SES_FROM_EMAIL=noreply@yourdomain.com
#      - AWS_ACCESS_KEY_ID=...
#      - AWS_SECRET_ACCESS_KEY=...
#      - AWS_REGION=us-east-1
#
# Note: In SES sandbox mode, you can only send to verified emails.
# Request production access when ready to launch.
#
# =============================================================================

import logging
from typing import Any

from memoir.config import get_settings

logger = logging.getLogger(__name__)

# Boto3 is optional - gracefully degrade if not installed
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None


# =============================================================================
# Email Templates
# =============================================================================

TEMPLATES = {
    "welcome": {
        "subject": "Welcome to Memoir!",
        "html": """
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #333;">Welcome to Memoir, {name}!</h1>
            <p>Thank you for signing up. We're excited to help you capture your life story.</p>
            <p>Please verify your email by clicking the button below:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{verify_url}" style="background: #4A90A4; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Verify Email
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">Or copy this link: {verify_url}</p>
            <p style="color: #666; font-size: 14px;">This link expires in 24 hours.</p>
        </body>
        </html>
        """,
        "text": """
Welcome to Memoir, {name}!

Thank you for signing up. Please verify your email by visiting:
{verify_url}

This link expires in 24 hours.
        """,
    },
    
    "password_reset": {
        "subject": "Reset your Memoir password",
        "html": """
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #333;">Reset Your Password</h1>
            <p>We received a request to reset your password. Click the button below to choose a new one:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="background: #4A90A4; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Reset Password
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">Or copy this link: {reset_url}</p>
            <p style="color: #666; font-size: 14px;">This link expires in 1 hour.</p>
            <p style="color: #666; font-size: 14px;">If you didn't request this, you can safely ignore this email.</p>
        </body>
        </html>
        """,
        "text": """
Reset Your Password

We received a request to reset your password. Visit this link to choose a new one:
{reset_url}

This link expires in 1 hour.

If you didn't request this, you can safely ignore this email.
        """,
    },
    
    "email_verified": {
        "subject": "Email verified - Welcome to Memoir!",
        "html": """
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #333;">You're all set!</h1>
            <p>Your email has been verified. You now have full access to Memoir.</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{app_url}" style="background: #4A90A4; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Start Your Story
                </a>
            </p>
        </body>
        </html>
        """,
        "text": """
You're all set!

Your email has been verified. You now have full access to Memoir.

Start your story at: {app_url}
        """,
    },
}


# =============================================================================
# Email Service
# =============================================================================

class EmailService:
    """Send emails via AWS SES."""
    
    def __init__(self):
        self.settings = get_settings()
        self._client = None
    
    @property
    def client(self):
        """Lazy-load SES client."""
        if self._client is None and BOTO3_AVAILABLE and self.settings.use_aws:
            self._client = boto3.client(
                'ses',
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
        return self._client
    
    @property
    def is_configured(self) -> bool:
        """Check if email sending is properly configured."""
        return (
            BOTO3_AVAILABLE
            and self.settings.use_aws
            and bool(self.settings.aws_ses_from_email)
        )
    
    async def send(
        self,
        to: str,
        template: str,
        data: dict[str, Any] | None = None,
        subject_override: str | None = None,
    ) -> bool:
        """
        Send an email using a template.
        
        Args:
            to: Recipient email address
            template: Template name (e.g., "welcome", "password_reset")
            data: Template variables to substitute
            subject_override: Override the template's subject
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Email not configured - would send '{template}' to {to}")
            # In dev, log the email content for debugging
            if template in TEMPLATES and data:
                tpl = TEMPLATES[template]
                logger.info(f"Email content: {tpl['text'].format(**data)}")
            return False
        
        if template not in TEMPLATES:
            logger.error(f"Unknown email template: {template}")
            return False
        
        tpl = TEMPLATES[template]
        data = data or {}
        
        try:
            subject = subject_override or tpl["subject"]
            html_body = tpl["html"].format(**data)
            text_body = tpl["text"].format(**data)
            
            response = self.client.send_email(
                Source=self.settings.aws_ses_from_email,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                    },
                },
            )
            
            logger.info(f"Email sent to {to}: {template} (MessageId: {response['MessageId']})")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False
        except KeyError as e:
            logger.error(f"Missing template variable for '{template}': {e}")
            return False
    
    async def send_welcome(self, email: str, name: str, verify_token: str) -> bool:
        """Send welcome email with verification link."""
        verify_url = f"{self.settings.cors_origins_list[0]}/verify-email?token={verify_token}"
        return await self.send(
            to=email,
            template="welcome",
            data={"name": name, "verify_url": verify_url},
        )
    
    async def send_password_reset(self, email: str, reset_token: str) -> bool:
        """Send password reset email."""
        reset_url = f"{self.settings.cors_origins_list[0]}/reset-password?token={reset_token}"
        return await self.send(
            to=email,
            template="password_reset",
            data={"reset_url": reset_url},
        )
    
    async def send_email_verified(self, email: str) -> bool:
        """Send confirmation that email was verified."""
        app_url = self.settings.cors_origins_list[0]
        return await self.send(
            to=email,
            template="email_verified",
            data={"app_url": app_url},
        )


# Global instance
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


# Convenience functions
async def send_email(to: str, template: str, data: dict[str, Any] | None = None) -> bool:
    """Send an email using a template."""
    return await get_email_service().send(to, template, data)


async def send_welcome_email(email: str, name: str, verify_token: str) -> bool:
    """Send welcome email with verification link."""
    return await get_email_service().send_welcome(email, name, verify_token)


async def send_password_reset_email(email: str, reset_token: str) -> bool:
    """Send password reset email."""
    return await get_email_service().send_password_reset(email, reset_token)

