from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transfers", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="transfer",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "processing",
                        "completed",
                        "failed",
                        "cancelled",
                    ]
                ),
                name="transfers_transfer_status_valid",
            ),
        ),
    ]
