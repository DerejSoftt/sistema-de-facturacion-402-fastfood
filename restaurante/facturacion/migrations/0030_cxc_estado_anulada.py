from django.db import migrations, models


def migrar_cancelada_a_anulada(apps, schema_editor):
    CuentaPorCobrar = apps.get_model('facturacion', 'CuentaPorCobrar')
    CuentaPorCobrar.objects.filter(estado='cancelada').update(estado='anulada')


def migrar_anulada_a_cancelada(apps, schema_editor):
    CuentaPorCobrar = apps.get_model('facturacion', 'CuentaPorCobrar')
    CuentaPorCobrar.objects.filter(estado='anulada').update(estado='cancelada')


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0029_detalledevolucion_facturadetalle_and_more'),
    ]

    operations = [
        migrations.RunPython(migrar_cancelada_a_anulada, migrar_anulada_a_cancelada),
        migrations.AlterField(
            model_name='cuentaporcobrar',
            name='estado',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('parcial', 'Parcialmente Pagada'),
                    ('pagada', 'Pagada'),
                    ('vencida', 'Vencida'),
                    ('anulada', 'Anulada'),
                ],
                default='pendiente',
                max_length=20,
                verbose_name='Estado',
            ),
        ),
    ]
