from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djgent", "0002_runtime_memory_and_retrieval"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="estimated_cost",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=18),
        ),
        migrations.AddField(
            model_name="conversation",
            name="input_tokens",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="conversation",
            name="output_tokens",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="conversation",
            name="total_tokens",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="message",
            name="estimated_cost",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=18),
        ),
        migrations.AddField(
            model_name="message",
            name="input_tokens",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="message",
            name="output_tokens",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="message",
            name="total_tokens",
            field=models.BigIntegerField(default=0),
        ),
    ]
