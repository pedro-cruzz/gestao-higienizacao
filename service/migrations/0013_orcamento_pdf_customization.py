from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0012_lead_cliente_foreignkey"),
    ]

    operations = [
        migrations.AddField(
            model_name="orcamento",
            name="pdf_frase_cliente",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orcamento",
            name="pdf_logo",
            field=models.ImageField(blank=True, null=True, upload_to="orcamentos/logos/"),
        ),
    ]
