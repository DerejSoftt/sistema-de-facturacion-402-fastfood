# Migration to add critical database indexes for performance

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0034_pedido_tipo_pago_factura_tipo_pago'),
    ]

    operations = [
        # Índices en MovimientoFinanciero para queries del dashboard
        migrations.AddIndex(
            model_name='movimientofinanciero',
            index=models.Index(
                fields=['fecha_operacion', 'estado', 'tipo', 'origen'],
                name='movfinanciero_fecha_estado_tipo_origen_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='movimientofinanciero',
            index=models.Index(
                fields=['estado', 'tipo', 'origen'],
                name='movfinanciero_estado_tipo_origen_idx'
            ),
        ),
        # Índice en Factura para tipo_pago (recién agregado)
        migrations.AddIndex(
            model_name='factura',
            index=models.Index(
                fields=['tipo_pago', 'estado', 'fecha_factura'],
                name='factura_tipo_pago_estado_fecha_idx'
            ),
        ),
        # Índices adicionales en FacturaDetalle
        migrations.AddIndex(
            model_name='facturadetalle',
            index=models.Index(
                fields=['factura_id', 'nombre_producto'],
                name='facturadtalle_factura_producto_idx'
            ),
        ),
        # Índice en Pedido para consultas frecuentes
        migrations.AddIndex(
            model_name='pedido',
            index=models.Index(
                fields=['fecha_pedido', 'estado'],
                name='pedido_fecha_estado_idx'
            ),
        ),
    ]
