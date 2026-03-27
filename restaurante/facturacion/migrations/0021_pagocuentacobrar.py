from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0020_cliente_registrado_por'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PagoCuentaCobrar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Monto pagado')),
                ('fecha_pago', models.DateField(verbose_name='Fecha de pago')),
                ('metodo_pago', models.CharField(choices=[('efectivo', 'Efectivo'), ('tarjeta', 'Tarjeta de Crédito/Débito'), ('transferencia', 'Transferencia Bancaria')], default='efectivo', max_length=20, verbose_name='Metodo de pago')),
                ('referencia', models.CharField(blank=True, max_length=120, verbose_name='Referencia')),
                ('notas', models.TextField(blank=True, verbose_name='Notas')),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('factura', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pagos_cxc', to='facturacion.factura', verbose_name='Factura')),
                ('registrado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagos_cuentas_cobrar', to=settings.AUTH_USER_MODEL, verbose_name='Registrado por')),
            ],
            options={
                'verbose_name': 'Pago de Cuenta por Cobrar',
                'verbose_name_plural': 'Pagos de Cuentas por Cobrar',
                'ordering': ['-fecha_pago', '-id'],
            },
        ),
    ]
