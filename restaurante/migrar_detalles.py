import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurante.settings')
django.setup()

from decimal import Decimal, InvalidOperation
from facturacion.models import Factura, FacturaDetalle

DRY_RUN = False # ← PRIMERO corre con True, luego cambia a False

errores = []
ya_migradas = 0
migradas = 0
sin_items = 0

facturas = Factura.objects.all().order_by('id')
total = facturas.count()

print(f"\n{'='*60}")
print(f"MODO: {'SIMULACIÓN (sin escribir nada)' if DRY_RUN else '⚠️  ESCRITURA REAL EN BD'}")
print(f"Total facturas a procesar: {total}")
print(f"{'='*60}\n")

for factura in facturas:
    if factura.detalles.exists():
        ya_migradas += 1
        continue

    items = factura.items
    if not items:
        sin_items += 1
        continue

    if not isinstance(items, list):
        errores.append(f"Factura {factura.numero_factura}: items no es lista ({type(items)})")
        continue

    detalles_a_crear = []
    for item in items:
        nombre = (
            item.get('name') or item.get('nombre') or
            item.get('product') or item.get('producto') or 'Sin nombre'
        )
        try:
            cantidad = Decimal(str(item.get('quantity') or item.get('cantidad') or 1))
        except InvalidOperation:
            cantidad = Decimal('1')

        try:
            precio = Decimal(str(item.get('price') or item.get('precio') or 0))
        except InvalidOperation:
            precio = Decimal('0')

        try:
            subtotal = Decimal(str(item.get('total') or item.get('subtotal') or 0))
            if subtotal == 0:
                subtotal = cantidad * precio
        except InvalidOperation:
            subtotal = cantidad * precio

        detalles_a_crear.append(FacturaDetalle(
            factura=factura,
            nombre_producto=nombre,
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=subtotal,
        ))

    if DRY_RUN:
        print(f"[SIM] {factura.numero_factura}: {len(detalles_a_crear)} items → OK")
    else:
        FacturaDetalle.objects.bulk_create(detalles_a_crear)
        migradas += 1

print(f"\n{'='*60}")
print(f"RESUMEN:")
print(f"  Ya tenían detalles : {ya_migradas}")
print(f"  Migradas ahora     : {migradas}")
print(f"  Sin items          : {sin_items}")
print(f"  Con errores        : {len(errores)}")
if errores:
    print(f"\nERRORES DETECTADOS:")
    for e in errores:
        print(f"  ❌ {e}")
print(f"{'='*60}\n")