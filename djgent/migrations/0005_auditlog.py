"""Migration for AuditLog model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djgent', '0004_rename_djgent_know_namespace_fcc6de_idx_djgent_know_namespa_a74548_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(db_index=True, max_length=36, unique=True)),
                ('event_type', models.CharField(db_index=True, max_length=50)),
                ('level', models.CharField(max_length=20)),
                ('agent_name', models.CharField(blank=True, db_index=True, max_length=100, null=True)),
                ('thread_id', models.CharField(blank=True, db_index=True, max_length=100, null=True)),
                ('user_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('session_id', models.CharField(blank=True, max_length=100, null=True)),
                ('conversation_id', models.CharField(blank=True, db_index=True, max_length=100, null=True)),
                ('tool_name', models.CharField(blank=True, max_length=100, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('error', models.TextField(blank=True, null=True)),
                ('duration_ms', models.FloatField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['agent_name', 'timestamp'], name='djgent_audit_agent_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user_id', 'timestamp'], name='djgent_audit_user_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['conversation_id', 'timestamp'], name='djgent_audit_conv_ts_idx'),
        ),
    ]
