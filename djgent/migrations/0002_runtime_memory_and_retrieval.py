from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("djgent", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(default="default", max_length=255)),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("source", models.CharField(blank=True, default="", max_length=512)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "djgent_knowledge_document",
                "ordering": ["title", "-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="MemoryFact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(default="user", max_length=32)),
                ("key", models.CharField(max_length=255)),
                ("value", models.TextField()),
                ("agent_name", models.CharField(blank=True, default="", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="memory_facts", to="djgent.conversation")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="djgent_memory_facts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "djgent_memory_fact",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="knowledgedocument",
            index=models.Index(fields=["namespace"], name="djgent_know_namespace_fcc6de_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgedocument",
            index=models.Index(fields=["title"], name="djgent_know_title_3529b8_idx"),
        ),
        migrations.AddIndex(
            model_name="memoryfact",
            index=models.Index(fields=["scope", "key"], name="djgent_memo_scope_70b590_idx"),
        ),
        migrations.AddIndex(
            model_name="memoryfact",
            index=models.Index(fields=["agent_name"], name="djgent_memo_agent_n_1e63ec_idx"),
        ),
    ]
