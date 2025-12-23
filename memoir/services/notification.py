"""
Notification Service.

Handles sending notifications via email, SMS, push, etc.
Triggered by phase unlocks, reminders, and other events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from memoir.core.events import Event
from memoir.core.registry import get_registry
from memoir.services.base import Service


@dataclass
class NotificationRequest:
    """A request to send a notification."""
    
    channel: str  # email, sms, push
    recipient_id: str  # contributor_id or user_id
    recipient_email: str | None = None
    recipient_phone: str | None = None
    
    template: str = ""
    subject: str = ""
    body: str = ""
    
    # Template variables
    context: dict[str, Any] | None = None
    
    # Scheduling
    send_at: datetime | None = None  # None = send immediately
    
    # Tracking
    event_trigger: str = ""  # What event triggered this


class NotificationService(Service):
    """
    Service that sends notifications.
    
    This is a stub implementation - in production you would:
    - Integrate with SendGrid, AWS SES, Twilio, etc.
    - Implement email templates (Jinja2, MJML, etc.)
    - Add retry logic and delivery tracking
    - Queue notifications for scheduled delivery
    """
    
    @property
    def service_id(self) -> str:
        return "notification"
    
    @property
    def subscribes_to(self) -> list[str]:
        return [
            "phase.unlocked",
            "phase.scheduled",
            "notification.send",
            "notification.schedule",
        ]
    
    def __init__(self):
        self.registry = get_registry()
        # Queue for scheduled notifications
        self._scheduled: list[NotificationRequest] = []
        # Log of sent notifications (for testing/debugging)
        self._sent_log: list[dict[str, Any]] = []
    
    async def handle(self, event: Event) -> list[Event]:
        """Handle notification-related events."""
        if event.event_type == "phase.unlocked":
            return await self._handle_phase_unlocked(event)
        elif event.event_type == "phase.scheduled":
            return await self._handle_phase_scheduled(event)
        elif event.event_type == "notification.send":
            return await self._handle_send(event)
        elif event.event_type == "notification.schedule":
            return await self._handle_schedule(event)
        
        return []
    
    async def _handle_phase_unlocked(self, event: Event) -> list[Event]:
        """Send notification when a phase is unlocked."""
        phase_id = event.payload.get("phase_id")
        contributor_id = event.contributor_id
        
        if not contributor_id:
            return []
        
        # In production, look up contributor email and product notification config
        # For now, just log it
        notification = NotificationRequest(
            channel="email",
            recipient_id=contributor_id,
            template="phase_invitation",
            subject=f"Your next chapter awaits",
            context={
                "phase_id": phase_id,
                "project_id": event.project_id,
            },
            event_trigger="phase.unlocked",
        )
        
        await self._send_notification(notification)
        
        return [Event(
            event_type="notification.sent",
            project_id=event.project_id,
            contributor_id=contributor_id,
            payload={
                "channel": "email",
                "template": "phase_invitation",
                "phase_id": phase_id,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    async def _handle_phase_scheduled(self, event: Event) -> list[Event]:
        """Schedule notification for when a phase will unlock."""
        phase_id = event.payload.get("phase_id")
        scheduled_for = event.payload.get("scheduled_for")
        contributor_id = event.contributor_id
        
        if not contributor_id or not scheduled_for:
            return []
        
        # Parse the scheduled time
        try:
            send_at = datetime.fromisoformat(scheduled_for)
        except (ValueError, TypeError):
            return []
        
        # Schedule the notification
        notification = NotificationRequest(
            channel="email",
            recipient_id=contributor_id,
            template="phase_upcoming",
            subject="A new chapter is coming soon",
            context={
                "phase_id": phase_id,
                "project_id": event.project_id,
                "unlock_date": scheduled_for,
            },
            send_at=send_at,
            event_trigger="phase.scheduled",
        )
        
        self._scheduled.append(notification)
        
        return [Event(
            event_type="notification.scheduled",
            project_id=event.project_id,
            contributor_id=contributor_id,
            payload={
                "channel": "email",
                "template": "phase_upcoming",
                "send_at": scheduled_for,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    async def _handle_send(self, event: Event) -> list[Event]:
        """Handle explicit notification send request."""
        notification = NotificationRequest(
            channel=event.payload.get("channel", "email"),
            recipient_id=event.contributor_id or event.payload.get("recipient_id", ""),
            recipient_email=event.payload.get("email"),
            template=event.payload.get("template", ""),
            subject=event.payload.get("subject", ""),
            body=event.payload.get("body", ""),
            context=event.payload.get("context"),
            event_trigger="notification.send",
        )
        
        await self._send_notification(notification)
        
        return [Event(
            event_type="notification.sent",
            project_id=event.project_id,
            contributor_id=event.contributor_id,
            payload={
                "channel": notification.channel,
                "template": notification.template,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    async def _handle_schedule(self, event: Event) -> list[Event]:
        """Handle notification scheduling request."""
        send_at_str = event.payload.get("send_at")
        if not send_at_str:
            return []
        
        try:
            send_at = datetime.fromisoformat(send_at_str)
        except (ValueError, TypeError):
            return []
        
        notification = NotificationRequest(
            channel=event.payload.get("channel", "email"),
            recipient_id=event.contributor_id or event.payload.get("recipient_id", ""),
            recipient_email=event.payload.get("email"),
            template=event.payload.get("template", ""),
            subject=event.payload.get("subject", ""),
            context=event.payload.get("context"),
            send_at=send_at,
            event_trigger="notification.schedule",
        )
        
        self._scheduled.append(notification)
        
        return [Event(
            event_type="notification.scheduled",
            project_id=event.project_id,
            contributor_id=event.contributor_id,
            payload={
                "channel": notification.channel,
                "send_at": send_at_str,
            },
            correlation_id=event.correlation_id,
            causation_id=event.id,
        )]
    
    async def _send_notification(self, notification: NotificationRequest) -> bool:
        """
        Send a notification.
        
        This is a stub - replace with actual email/SMS sending logic.
        """
        # Log the notification
        log_entry = {
            "channel": notification.channel,
            "recipient_id": notification.recipient_id,
            "recipient_email": notification.recipient_email,
            "template": notification.template,
            "subject": notification.subject,
            "context": notification.context,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "event_trigger": notification.event_trigger,
        }
        self._sent_log.append(log_entry)
        
        # In production, this would:
        # if notification.channel == "email":
        #     await self.email_provider.send(
        #         to=notification.recipient_email,
        #         template=notification.template,
        #         subject=notification.subject,
        #         context=notification.context,
        #     )
        
        print(f"[NotificationService] Sent {notification.channel} to {notification.recipient_id}")
        print(f"  Template: {notification.template}")
        print(f"  Subject: {notification.subject}")
        
        return True
    
    async def process_scheduled(self) -> list[Event]:
        """
        Process scheduled notifications that are due.
        
        Call this from a cron job or scheduler.
        """
        now = datetime.now(timezone.utc)
        events = []
        remaining = []
        
        for notification in self._scheduled:
            if notification.send_at and notification.send_at <= now:
                await self._send_notification(notification)
                events.append(Event(
                    event_type="notification.sent",
                    project_id="",  # Would need to store this
                    contributor_id=notification.recipient_id,
                    payload={
                        "channel": notification.channel,
                        "template": notification.template,
                        "was_scheduled": True,
                    },
                ))
            else:
                remaining.append(notification)
        
        self._scheduled = remaining
        return events
    
    def get_sent_log(self) -> list[dict[str, Any]]:
        """Get log of sent notifications (for testing)."""
        return self._sent_log.copy()
    
    def get_scheduled(self) -> list[NotificationRequest]:
        """Get pending scheduled notifications."""
        return self._scheduled.copy()
    
    def clear_log(self) -> None:
        """Clear the sent log (for testing)."""
        self._sent_log.clear()


# =============================================================================
# Email Templates (stubs)
# =============================================================================

EMAIL_TEMPLATES = {
    "phase_invitation": {
        "subject": "Your next chapter awaits: {phase_name}",
        "body": """
Hi {contributor_name},

Great news! The next phase of your life story journey is now available.

Phase: {phase_name}
{phase_description}

Click here to continue your story: {continue_url}

We're excited to hear more of your story!

Best,
The Memoir Team
""",
    },
    "phase_upcoming": {
        "subject": "Coming soon: {phase_name}",
        "body": """
Hi {contributor_name},

Your next chapter will be available on {unlock_date}.

Phase: {phase_name}

We'll send you another email when it's ready!

Best,
The Memoir Team
""",
    },
    "phase_reminder": {
        "subject": "Don't forget: {phase_name} is waiting for you",
        "body": """
Hi {contributor_name},

Just a gentle reminder that {phase_name} is available and waiting for you.

You've already made great progress on your life story. Ready to continue?

Click here: {continue_url}

Best,
The Memoir Team
""",
    },
    "phase_complete": {
        "subject": "Congratulations on completing {phase_name}!",
        "body": """
Hi {contributor_name},

You've completed {phase_name}! 🎉

{next_phase_message}

Thank you for sharing your story with us.

Best,
The Memoir Team
""",
    },
}

