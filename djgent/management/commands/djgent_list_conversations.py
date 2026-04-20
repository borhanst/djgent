"""Management command to list conversations."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    """
    List conversations.

    Example:
        python manage.py djgent_list_conversations
        python manage.py djgent_list_conversations --user=admin
        python manage.py djgent_list_conversations --agent=assistant --limit=10
    """

    help = "List conversations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="Filter by username"
        )
        parser.add_argument(
            "--agent",
            type=str,
            help="Filter by agent name"
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum number of conversations to show"
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information"
        )

    def handle(self, *args, **options):
        from djgent.models import Conversation

        username = options["user"]
        agent_name = options["agent"]
        limit = options["limit"]
        verbose = options["verbose"]

        # Build queryset
        queryset = Conversation.objects.all()

        if username:
            try:
                user = User.objects.get(username=username)
                queryset = queryset.filter(user=user)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"User '{username}' not found"))
                return

        if agent_name:
            queryset = queryset.filter(agent_name=agent_name)

        # Get count before limiting
        total_count = queryset.count()
        conversations = queryset[:limit]

        if not conversations:
            self.stdout.write(self.style.WARNING("No conversations found"))
            return

        # Display results
        self.stdout.write(f"\nShowing {len(conversations)} of {total_count} conversations:\n")
        self.stdout.write("-" * 80)

        for conv in conversations:
            user_str = conv.user.username if conv.user else "(none)"
            name_str = conv.name or f"Conversation {str(conv.id)[:8]}"
            msg_count = conv.messages.count()

            self.stdout.write(f"ID: {conv.id}")
            self.stdout.write(f"  Name: {name_str}")
            self.stdout.write(f"  Agent: {conv.agent_name}")
            self.stdout.write(f"  User: {user_str}")
            self.stdout.write(f"  Messages: {msg_count}")
            self.stdout.write(f"  Created: {conv.created_at.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"  Updated: {conv.updated_at.strftime('%Y-%m-%d %H:%M')}")

            if verbose and conv.metadata:
                self.stdout.write(f"  Metadata: {conv.metadata}")

            self.stdout.write("-" * 80)

        if total_count > limit:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{total_count - limit} more conversations. Use --limit to see more."
                )
            )
