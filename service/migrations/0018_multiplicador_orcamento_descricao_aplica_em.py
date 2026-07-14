from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0017_userprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="multiplicadororcamento",
            name="aplica_em",
            field=models.CharField(
                blank=True,
                choices=[("total", "Total"), ("servicos", "Serviços")],
                default="total",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="multiplicadororcamento",
            name="descricao",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
    ]
