from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0021_pagocuentacobrar'),
    ]

    operations = [
        migrations.CreateModel(
            name='CuentaPorCobrar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_emision', models.DateField(verbose_name='Fecha de emision')),
                ('fecha_vencimiento', models.DateField(verbose_name='Fecha de vencimiento')),
                ('monto_original', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Monto original')),
                ('saldo_pendiente', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Saldo pendiente')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('parcial', 'Parcialmente Pagada'), ('pagada', 'Pagada'), ('vencida', 'Vencida')], default='pendiente', max_length=20, verbose_name='Estado')),
                ('notas', models.TextField(blank=True, verbose_name='Notas')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cuentas_por_cobrar', to='facturacion.cliente', verbose_name='Cliente')),
                ('factura', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cuenta_por_cobrar', to='facturacion.factura', verbose_name='Factura')),
            ],
            options={
                'verbose_name': 'Cuenta por Cobrar',
                'verbose_name_plural': 'Cuentas por Cobrar',
                'ordering': ['-fecha_vencimiento'],
                'db_table': 'cuentaporcobrar',
            },
        ),
        migrations.AddField(
            model_name='pagocuentacobrar',
            name='cuenta_por_cobrar',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pagos', to='facturacion.cuentaporcobrar', verbose_name='Cuenta por cobrar'),
        ),
        migrations.AlterModelTable(
            name='pagocuentacobrar',
            table='pagocuentacobrar',
        ),
    ]
