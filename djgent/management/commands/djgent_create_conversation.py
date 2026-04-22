"""Management command to create a new conversation."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    """
    Create a new conversation for an agent.

    Example:
        python manage.py djgent_create_conversation --agent=assistant --user=admin
        python manage.py djgent_create_conversation --agent=assistant --name="My Chat"
    """

    help = "Create a new conversation for an agent"

    def add_arguments(self, parser):
        parser.add_argument("--agent", type=str, required=True, help="Name of the agent")
        parser.add_argument(
            "--name", type=str, default="", help="Optional name for the conversation"
        )
        parser.add_argument("--user", type=str, help="Username to associate with the conversation")
        parser.add_argument(
            "--metadata", type=str, default="{}", help="JSON metadata for the conversation"
        )

    def handle(self, *args, **options):
        import json

        from djgent.models import Conversation

        agent_name = options["agent"]
        name = options["name"]
        username = options["user"]
        metadata_str = options["metadata"]

        # Parse metadata
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON metadata: {e}")

        # Get user if specified
        user = None
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' not found")

        # Create conversation
        conversation = Conversation.objects.create(
            agent_name=agent_name,
            name=name,
            user=user,
            metadata=metadata,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created conversation!\n"
                f"  ID: {conversation.id}\n"
                f"  Agent: {conversation.agent_name}\n"
                f"  Name: {conversation.name or '(none)'}\n"
                f"  User: {user.username if user else '(none)'}\n"
                f"  Created: {conversation.created_at}"
            )
        )
