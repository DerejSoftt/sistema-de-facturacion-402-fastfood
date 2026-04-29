import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurante.settings')
django.setup()

from decimal import Decimal
from facturacion.models import Factura, MovimientoFinanciero, Devolucion
DRY_RUN = False  # ← Primero True, luego False

creados        = 0
ya_tienen      = 0
omitidas       = 0
errores        = []

ESTADOS_MIGRABLES = {'pagada', 'parcialmente_devuelta', 'totalmente_devuelta', 'anulada'}

facturas = (
    Factura.objects
    .filter(estado__in=ESTADOS_MIGRABLES)
    .prefetch_related('movimientos', 'devoluciones', 'pagos_cxc')
    .order_by('fecha_factura')
)

total = facturas.count()

print(f"\n{'='*60}")
print(f"MODO: {'SIMULACIÓN' if DRY_RUN else '⚠️  ESCRITURA REAL'}")
print(f"Facturas a procesar: {total}")
print(f"{'='*60}\n")

for factura in facturas:

    # Si ya tiene movimiento de VENTA, saltar
    ya_tiene_venta = factura.movimientos.filter(origen='VENTA').exists()
    if ya_tiene_venta:
        ya_tienen += 1
        continue

    movimientos_a_crear = []

    # ── 1. Movimiento de INGRESO por la venta ─────────────────────────────
    # Facturas anuladas sin ningún pago registrado no generan ingreso
    if factura.estado == 'anulada':
        tuvo_pago = factura.pagos_cxc.exists()
        if not tuvo_pago and factura.metodo_pago == 'efectivo':
            # Asumimos que fue pagada en efectivo en el momento
            # Solo la incluimos si tiene total > 0
            if factura.total > 0:
                movimientos_a_crear.append(dict(
                    tipo='INGRESO',
                    origen='VENTA',
                    estado='REVERTIDO',  # ya fue anulada, marcamos como revertida
                    monto=factura.total,
                    fecha_operacion=factura.fecha_factura,
                    factura=factura,
                    metodo_pago=factura.metodo_pago,
                    creado_por=None,
                    descripcion=f"[MIGRADO] Venta {factura.numero_factura} (anulada)",
                    referencia=f"MIGRADO-{factura.numero_factura}",
                ))
        else:
            omitidas += 1
            continue
    else:
        # pagada / parcialmente_devuelta / totalmente_devuelta
        movimientos_a_crear.append(dict(
            tipo='INGRESO',
            origen='VENTA',
            estado='ACTIVO',
            monto=factura.total,
            fecha_operacion=factura.fecha_factura,
            factura=factura,
            metodo_pago=factura.metodo_pago,
            creado_por=None,
            descripcion=f"[MIGRADO] Venta {factura.numero_factura}",
            referencia=f"MIGRADO-{factura.numero_factura}",
        ))

    # ── 2. Movimientos de EGRESO por cada devolución ──────────────────────
    if factura.estado in {'parcialmente_devuelta', 'totalmente_devuelta'}:
        for dev in factura.devoluciones.all():
            ya_tiene_dev = dev.movimientos.filter(origen='DEVOLUCION').exists()
            if ya_tiene_dev:
                continue
            if dev.monto_devuelto > 0:
                movimientos_a_crear.append(dict(
                    tipo='EGRESO',
                    origen='DEVOLUCION',
                    estado='ACTIVO',
                    monto=dev.monto_devuelto,
                    fecha_operacion=dev.fecha_devolucion,
                    factura=factura,
                    devolucion=dev,
                    metodo_pago=factura.metodo_pago,
                    creado_por=None,
                    descripcion=f"[MIGRADO] Devolución #{dev.id} — Factura {factura.numero_factura}",
                    referencia=f"MIGRADO-DEV-{dev.id}",
                ))

    # ── Imprimir o crear ───────────────────────────────────────────────────
    if DRY_RUN:
        for m in movimientos_a_crear:
            print(
                f"[SIM] {m['tipo']:7} | {m['origen']:10} | "
                f"RD${m['monto']:>10} | {factura.numero_factura} | {m['estado']}"
            )
        creados += len(movimientos_a_crear)
    else:
        try:
            for m in movimientos_a_crear:
                MovimientoFinanciero.objects.create(**m)
            creados += len(movimientos_a_crear)
        except Exception as e:
            errores.append(f"{factura.numero_factura}: {e}")

print(f"\n{'='*60}")
print(f"RESUMEN:")
print(f"  Movimientos {'a crear' if DRY_RUN else 'creados'}: {creados}")
print(f"  Facturas ya tenían movimiento : {ya_tienen}")
print(f"  Omitidas (pendiente/sin pago) : {omitidas}")
print(f"  Errores                       : {len(errores)}")
if errores:
    print(f"\nERRORES:")
    for e in errores:
        print(f"  ❌ {e}")
print(f"{'='*60}\n")