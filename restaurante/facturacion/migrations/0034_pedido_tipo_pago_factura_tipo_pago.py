# Generated migration for optimized payment type field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0033_alter_movimientofinanciero_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='tipo_pago',
            field=models.CharField(
                choices=[('contado', 'Al Contado'), ('credito', 'A Crédito')],
                default='contado',
                max_length=20,
                verbose_name='Tipo de Pago'
            ),
        ),
        migrations.AddField(
            model_name='factura',
            name='tipo_pago',
            field=models.CharField(
                choices=[('contado', 'Al Contado'), ('credito', 'A Crédito')],
                default='contado',
                db_index=True,
                max_length=20,
                verbose_name='Tipo de Pago'
            ),
        ),
    ]
