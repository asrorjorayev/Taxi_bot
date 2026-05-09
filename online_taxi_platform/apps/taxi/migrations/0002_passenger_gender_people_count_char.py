from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("taxi", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="announcement",
            name="people_count",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="announcement",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "Erkak"), ("female", "Ayol")],
                max_length=10,
                null=True,
            ),
        ),
    ]
