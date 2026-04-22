"""Management command to clear old conversations."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    """
    Clear conversations older than specified days.

    Example:
        python manage.py djgent_clear_conversations --days=30
        python manage.py djgent_clear_conversations --days=90 --user=admin
        python manage.py djgent_clear_conversations --days=30 --dry-run
    """

    help = "Clear conversations older than specified days"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete conversations older than this many days (default: 30)",
        )
        parser.add_argument("--user", type=str, help="Filter by username")
        parser.add_argument("--agent", type=str, help="Filter by agent name")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        from datetime import timedelta

        from django.utils import timezone

        from djgent.models import Conversation

        days = options["days"]
        username = options["user"]
        agent_name = options["agent"]
        dry_run = options["dry_run"]

        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)

        # Build queryset
        queryset = Conversation.objects.filter(updated_at__lt=cutoff_date)

        if username:
            try:
                user = User.objects.get(username=username)
                queryset = queryset.filter(user=user)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"User '{username}' not found"))
                return

        if agent_name:
            queryset = queryset.filter(agent_name=agent_name)

        count = queryset.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"No conversations found older than {days} days"))
            return

        # Display what will be done
        action = "Would delete" if dry_run else "Deleting"
        self.stdout.write(
            self.style.WARNING(
                f"\n{action} {count} conversations older than {days} days"
                f" (before {cutoff_date.strftime('%Y-%m-%d')})"
            )
        )

        if not dry_run:
            # Confirm deletion
            self.stdout.write("\nThis action cannot be undone.")

        # Perform deletion
        if not dry_run:
            queryset.delete()
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully deleted {count} conversations"))
        else:
            # Show what would be deleted
            self.stdout.write("\nConversations that would be deleted:")
            for conv in queryset[:10]:
                name = conv.name or f"Conversation {str(conv.id)[:8]}"
                self.stdout.write(
                    f"  - {name} ({conv.agent_name}) - {conv.updated_at.strftime('%Y-%m-%d')}"
                )

            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
