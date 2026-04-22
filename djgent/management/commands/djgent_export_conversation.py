"""Management command to export a conversation."""

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    Export a conversation to JSON.

    Example:
        python manage.py djgent_export_conversation --id=<uuid>
        python manage.py djgent_export_conversation --id=<uuid> --output=conversation.json
    """

    help = "Export a conversation to JSON"

    def add_arguments(self, parser):
        parser.add_argument("--id", type=str, required=True, help="Conversation UUID")
        parser.add_argument("--output", type=str, help="Output file path (default: stdout)")
        parser.add_argument(
            "--include-messages",
            action="store_true",
            default=True,
            help="Include messages in export (default: True)",
        )

    def handle(self, *args, **options):
        from djgent.models import Conversation

        conv_id = options["id"]
        output_file = options["output"]
        include_messages = options["include_messages"]

        # Get conversation
        try:
            conversation = Conversation.objects.get(id=conv_id)
        except Conversation.DoesNotExist:
            raise CommandError(f"Conversation '{conv_id}' not found")

        # Build export data
        data = {
            "conversation": conversation.to_dict(),
        }

        if include_messages:
            messages = []
            for msg in conversation.messages.all():
                messages.append(msg.to_dict())
            data["messages"] = messages

        # Output
        json_output = json.dumps(data, indent=2, default=str)

        if output_file:
            with open(output_file, "w") as f:
                f.write(json_output)
            self.stdout.write(self.style.SUCCESS(f"Conversation exported to {output_file}"))
        else:
            self.stdout.write(json_output)
