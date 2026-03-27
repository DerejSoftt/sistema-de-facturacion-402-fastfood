from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0022_cuentaporcobrar'),
    ]

    operations = [
        migrations.AddField(
            model_name='pagocuentacobrar',
            name='numero_comprobante',
            field=models.CharField(
                blank=True,
                max_length=40,
                null=True,
                unique=True,
                verbose_name='Numero de comprobante',
            ),
        ),
    ]
