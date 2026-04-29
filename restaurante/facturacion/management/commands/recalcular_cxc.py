from decimal import Decimal
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from facturacion.models import Cliente, CuentaPorCobrar, Factura, PagoCuentaCobrar


class Command(BaseCommand):
    help = 'Recalcula cuentas por cobrar segun la logica actual de facturacion y devoluciones.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra los cambios que haria sin guardar nada.',
        )
        parser.add_argument(
            '--factura',
            action='append',
            dest='facturas',
            help='Procesa solo una o varias facturas por numero_factura.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        facturas_filtro = options.get('facturas') or []

        facturas_qs = Factura.objects.select_related('pedido').prefetch_related(
            'pagos_cxc',
            'devoluciones',
            'cuenta_por_cobrar',
        ).order_by('id')

        if facturas_filtro:
            facturas_qs = facturas_qs.filter(numero_factura__in=facturas_filtro)

        clientes = list(Cliente.objects.all())
        cliente_por_telefono = {}
        cliente_por_nombre = {}

        for cliente in clientes:
            telefono_principal = self._solo_digitos(cliente.telefono_principal)
            telefono_alternativo = self._solo_digitos(cliente.telefono_alternativo)
            if telefono_principal:
                cliente_por_telefono[telefono_principal] = cliente
            if telefono_alternativo:
                cliente_por_telefono[telefono_alternativo] = cliente

            nombre_key = (cliente.nombre_completo or '').strip().lower()
            if nombre_key and nombre_key not in cliente_por_nombre:
                cliente_por_nombre[nombre_key] = cliente

        resumen = {
            'procesadas': 0,
            'credito_actualizadas': 0,
            'contado_eliminadas': 0,
            'creadas': 0,
            'sin_cliente': 0,
        }

        with transaction.atomic():
            for factura in facturas_qs:
                resumen['procesadas'] += 1
                es_credito = self._factura_es_credito(factura)
                cuenta = getattr(factura, 'cuenta_por_cobrar', None)

                if not es_credito:
                    if cuenta:
                        resumen['contado_eliminadas'] += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'Eliminar CxC de contado: {factura.numero_factura} (saldo RD${cuenta.saldo_pendiente})'
                            )
                        )
                        if not dry_run:
                            cuenta.delete()
                    continue

                cliente_match = self._obtener_cliente_match(
                    factura,
                    cliente_por_telefono,
                    cliente_por_nombre,
                )

                if cliente_match is None:
                    resumen['sin_cliente'] += 1

                fecha_emision, fecha_vencimiento = self._calcular_fechas_cxc(factura, cliente_match)
                total_factura = self._total_factura(factura)
                total_pagado = self._total_pagado(factura)
                total_devuelto = self._total_devuelto(factura)
                saldo = total_factura - total_pagado - total_devuelto
                if saldo < Decimal('0.00'):
                    saldo = Decimal('0.00')

                if cuenta is None:
                    resumen['creadas'] += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Crear CxC: {factura.numero_factura} saldo RD${saldo:.2f}'
                        )
                    )
                    if dry_run:
                        continue
                    CuentaPorCobrar.objects.create(
                        factura=factura,
                        cliente=cliente_match,
                        fecha_emision=fecha_emision,
                        fecha_vencimiento=fecha_vencimiento,
                        monto_original=total_factura,
                        saldo_pendiente=saldo,
                        estado=self._estado_cxc(saldo, total_factura, fecha_vencimiento),
                        notas=factura.notas or '',
                    )
                    continue

                cambios = []
                if cliente_match is not None and cuenta.cliente_id != cliente_match.id:
                    cuenta.cliente = cliente_match
                    cambios.append('cliente')
                if cuenta.fecha_emision != fecha_emision:
                    cuenta.fecha_emision = fecha_emision
                    cambios.append('fecha_emision')
                if cuenta.fecha_vencimiento != fecha_vencimiento:
                    cuenta.fecha_vencimiento = fecha_vencimiento
                    cambios.append('fecha_vencimiento')
                if cuenta.monto_original != total_factura:
                    cuenta.monto_original = total_factura
                    cambios.append('monto_original')
                if cuenta.saldo_pendiente != saldo:
                    cuenta.saldo_pendiente = saldo
                    cambios.append('saldo_pendiente')

                nuevo_estado = self._estado_cxc(saldo, total_factura, fecha_vencimiento)
                if cuenta.estado != nuevo_estado:
                    cuenta.estado = nuevo_estado
                    cambios.append('estado')
                if cuenta.notas != (factura.notas or ''):
                    cuenta.notas = factura.notas or ''
                    cambios.append('notas')

                if cambios:
                    resumen['credito_actualizadas'] += 1
                    self.stdout.write(
                        f'Actualizar CxC: {factura.numero_factura} -> RD${saldo:.2f} ({nuevo_estado})'
                    )
                    if not dry_run:
                        cuenta.save(update_fields=sorted(set(cambios + ['fecha_actualizacion'])))

        self.stdout.write(self.style.SUCCESS('Resumen de recalculo de CxC:'))
        self.stdout.write(f"  Procesadas: {resumen['procesadas']}")
        self.stdout.write(f"  CxC credito actualizadas: {resumen['credito_actualizadas']}")
        self.stdout.write(f"  CxC contado eliminadas: {resumen['contado_eliminadas']}")
        self.stdout.write(f"  CxC creadas: {resumen['creadas']}")
        self.stdout.write(f"  Facturas sin cliente vinculable: {resumen['sin_cliente']}")
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: no se guardaron cambios.'))

    def _solo_digitos(self, valor):
        return ''.join(ch for ch in str(valor or '') if ch.isdigit())

    def _factura_es_credito(self, factura):
        notas_pedido = (factura.pedido.notas or '') if getattr(factura, 'pedido', None) else ''
        return (
            ('TIPO_PAGO_PEDIDO=credito' in notas_pedido)
            or hasattr(factura, 'cuenta_por_cobrar')
            or factura.pagos_cxc.exists()
        )

    def _obtener_cliente_match(self, factura, cliente_por_telefono, cliente_por_nombre):
        telefono_factura = self._solo_digitos(factura.telefono_cliente)
        nombre_factura = (factura.nombre_cliente or '').strip().lower()

        if telefono_factura and telefono_factura in cliente_por_telefono:
            return cliente_por_telefono[telefono_factura]
        if nombre_factura and nombre_factura in cliente_por_nombre:
            return cliente_por_nombre[nombre_factura]
        return None

    def _total_factura(self, factura):
        if hasattr(factura, 'get_total_neto'):
            return factura.get_total_neto() or Decimal('0.00')
        return Decimal(str(factura.total or 0))

    def _total_pagado(self, factura):
        return factura.pagos_cxc.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    def _total_devuelto(self, factura):
        return factura.devoluciones.aggregate(total=Sum('monto_devuelto'))['total'] or Decimal('0.00')

    def _calcular_fechas_cxc(self, factura, cliente_match=None):
        fecha_base = factura.fecha_factura or timezone.now()
        fecha_emision = timezone.localtime(fecha_base).date() if timezone.is_aware(fecha_base) else fecha_base.date()
        dias_credito = 30
        if cliente_match and cliente_match.dias_credito is not None:
            dias_credito = max(0, int(cliente_match.dias_credito))
        fecha_vencimiento = fecha_emision + timedelta(days=dias_credito)
        return fecha_emision, fecha_vencimiento

    def _estado_cxc(self, saldo, total_factura, fecha_vencimiento):
        hoy = timezone.localdate()
        if saldo <= Decimal('0.00'):
            return 'pagada'
        if saldo < total_factura:
            return 'vencida' if fecha_vencimiento < hoy else 'parcial'
        return 'vencida' if fecha_vencimiento < hoy else 'pendiente'
