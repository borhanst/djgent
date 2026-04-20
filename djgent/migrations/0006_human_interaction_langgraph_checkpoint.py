import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djgent", "0005_auditlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LangGraphCheckpoint",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("thread_id", models.CharField(db_index=True, max_length=255)),
                (
                    "checkpoint_ns",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("checkpoint_id", models.CharField(db_index=True, max_length=255)),
                (
                    "parent_checkpoint_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("config", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("checkpoint", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "djgent_langgraph_checkpoint",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="HumanInteractionRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("resumed", "Resumed"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("agent_name", models.CharField(db_index=True, max_length=255)),
                ("thread_id", models.CharField(db_index=True, max_length=255)),
                ("site_owner_emails", models.JSONField(blank=True, default=list)),
                ("action_requests", models.JSONField(blank=True, default=list)),
                ("review_configs", models.JSONField(blank=True, default=list)),
                ("decisions", models.JSONField(blank=True, default=list)),
                ("output", models.TextField(blank=True, default="")),
                ("error", models.TextField(blank=True, default="")),
                ("notification_error", models.TextField(blank=True, default="")),
                ("emailed_at", models.DateTimeField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("resumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="human_interaction_requests",
                        to="djgent.conversation",
                    ),
                ),
                (
                    "requesting_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="djgent_human_interaction_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "djgent_human_interaction_request",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="LangGraphCheckpointWrite",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("thread_id", models.CharField(db_index=True, max_length=255)),
                (
                    "checkpoint_ns",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("checkpoint_id", models.CharField(db_index=True, max_length=255)),
                ("task_id", models.CharField(db_index=True, max_length=255)),
                ("idx", models.IntegerField()),
                ("channel", models.CharField(max_length=255)),
                ("value", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "djgent_langgraph_checkpoint_write",
                "ordering": ["idx"],
            },
        ),
        migrations.AddIndex(
            model_name="langgraphcheckpoint",
            index=models.Index(
                fields=["thread_id", "checkpoint_ns", "-created_at"],
                name="djgent_lg_ckpt_thread_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="langgraphcheckpoint",
            constraint=models.UniqueConstraint(
                fields=("thread_id", "checkpoint_ns", "checkpoint_id"),
                name="djgent_lg_checkpoint_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="humaninteractionrequest",
            index=models.Index(fields=["status", "-created_at"], name="djgent_hum_status_7a4e91_idx"),
        ),
        migrations.AddIndex(
            model_name="humaninteractionrequest",
            index=models.Index(fields=["agent_name", "status"], name="djgent_hum_agent_n_5b95a2_idx"),
        ),
        migrations.AddIndex(
            model_name="humaninteractionrequest",
            index=models.Index(fields=["thread_id", "status"], name="djgent_hum_thread__1370d2_idx"),
        ),
        migrations.AddIndex(
            model_name="langgraphcheckpointwrite",
            index=models.Index(
                fields=["thread_id", "checkpoint_ns", "checkpoint_id"],
                name="djgent_lg_write_ckpt_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="langgraphcheckpointwrite",
            constraint=models.UniqueConstraint(
                fields=(
                    "thread_id",
                    "checkpoint_ns",
                    "checkpoint_id",
                    "task_id",
                    "idx",
                ),
                name="djgent_lg_write_unique",
            ),
        ),
    ]
