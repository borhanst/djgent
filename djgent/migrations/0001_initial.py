# Generated migration for djgent models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier for this conversation', primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, default='', help_text='Optional name for this conversation', max_length=255)),
                ('agent_name', models.CharField(help_text='Name of the agent this conversation belongs to', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this conversation was created')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When this conversation was last updated')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional metadata for this conversation')),
                ('user', models.ForeignKey(blank=True, help_text='User associated with this conversation (optional)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='djgent_conversations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Conversation',
                'verbose_name_plural': 'Conversations',
                'db_table': 'djgent_conversation',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('human', 'Human'), ('ai', 'AI'), ('system', 'System')], help_text='The role of the message sender', max_length=20)),
                ('content', models.TextField(help_text='The message content')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this message was created')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional metadata for this message')),
                ('conversation', models.ForeignKey(help_text='The conversation this message belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='djgent.conversation')),
            ],
            options={
                'verbose_name': 'Message',
                'verbose_name_plural': 'Messages',
                'db_table': 'djgent_message',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['conversation', '-created_at'], name='djgent_mess_convers_6c0c4f_idx'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['role'], name='djgent_mess_role_382203_idx'),
        ),
    ]
