from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0011_tecnico_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="cliente",
            field=models.ForeignKey(
                to="service.cliente",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="lead_origem",
            ),
        ),
    ]
