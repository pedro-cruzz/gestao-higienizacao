from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("service", "0015_adicional_orcamento"),
    ]

    operations = [
        migrations.CreateModel(
            name="MultiplicadorOrcamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("fator", models.FloatField(default=1)),
                ("ativo", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="multiplicadores_orcamento",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="orcamento",
            name="multiplicadores",
            field=models.ManyToManyField(blank=True, related_name="orcamentos", to="service.multiplicadororcamento"),
        ),
        migrations.AddConstraint(
            model_name="multiplicadororcamento",
            constraint=models.UniqueConstraint(fields=("owner", "name"), name="unique_multiplicador_orcamento_por_owner"),
        ),
    ]
