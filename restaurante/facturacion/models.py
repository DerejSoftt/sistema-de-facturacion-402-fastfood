# =============================================================================
# models.py — 402 FastFood
# Versión consolidada con todas las mejoras de seguridad e integridad
# =============================================================================

from django.db import models, IntegrityError, transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.serializers.json import DjangoJSONEncoder
from decimal import Decimal
import random
import string
import uuid
import re
import json


# =============================================================================
# PRODUCTO
# =============================================================================

class Producto(models.Model):
    CATEGORIAS = [
        ('bebida', 'Bebida'),
        ('trago', 'Trago'),
        ('postre', 'Postre'),
        ('carne', 'Carne'),
        ('verdura', 'Verdura'),
        ('lacteo', 'Lácteo'),
        ('otro', 'Otro'),
    ]

    codigo = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Código único del producto"
    )
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, verbose_name="Categoría")
    cantidad = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Cantidad", help_text="Cantidad en stock"
    )
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de Compra")
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2,
        editable=False, default=Decimal('0.00'), verbose_name="Subtotal"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['-fecha_creacion']

    def save(self, *args, **kwargs):
        if not self.codigo:
            categoria_abrev = self.categoria[:3].upper() if self.categoria else 'GEN'
            fecha = timezone.now().strftime("%y%m%d")
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            self.codigo = f"PROD-{categoria_abrev}-{fecha}-{random_str}"
        self.subtotal = self.cantidad * self.precio_compra
        super().save(*args, **kwargs)

    def get_category_label(self):
        for code, label in self.CATEGORIAS:
            if code == self.categoria:
                return label
        return self.categoria

    def get_stock_status(self):
        cantidad = float(self.cantidad)
        if cantidad >= 50:
            return 'high'
        elif cantidad >= 10:
            return 'medium'
        return 'low'

    def get_stock_label(self):
        return {'high': 'Alto', 'medium': 'Medio', 'low': 'Bajo'}.get(self.get_stock_status(), 'Desconocido')

    def get_stock_icon(self):
        return {'high': '📈', 'medium': '📊', 'low': '📉'}.get(self.get_stock_status(), '📦')

    def __str__(self):
        return f"{self.codigo} - {self.nombre} (${self.subtotal:.2f})"


# =============================================================================
# PLATO
# =============================================================================

class Plato(models.Model):
    CATEGORIAS = [
        ('entrada', 'Entrada'),
        ('principal', 'Plato Principal'),
        ('postre', 'Postre'),
        ('bebida', 'Bebida'),
        ('rapida', 'Comida Rápida'),
        ('especial', 'Especial del Chef'),
    ]

    codigo = models.CharField(max_length=10, unique=True, verbose_name="Código")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Plato")
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, verbose_name="Categoría")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Plato"
        verbose_name_plural = "Platos"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.generar_codigo()
        super().save(*args, **kwargs)

    @classmethod
    def generar_codigo(cls):
        ultimo_plato = cls.objects.filter(
            codigo__regex=r'^COD\d{3}$'
        ).order_by('codigo').last()
        if ultimo_plato:
            ultimo_numero = int(re.search(r'\d+', ultimo_plato.codigo).group())
            nuevo_numero = ultimo_numero + 1
        else:
            nuevo_numero = 1
        return f"COD{nuevo_numero:03d}"

    def get_categoria_display_color(self):
        colores = {
            'entrada': 'warning', 'principal': 'danger', 'postre': 'warning',
            'bebida': 'primary', 'rapida': 'success', 'especial': 'info',
        }
        return colores.get(self.categoria, 'secondary')


# =============================================================================
# MESA
# =============================================================================

class Mesa(models.Model):
    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),
        ('ocupada', 'Ocupada'),
        ('reservada', 'Reservada'),
        ('mantenimiento', 'En Mantenimiento'),
    ]

    NUMERO_CHOICES = [
        ('mesa 01', 'Mesa 01'), ('mesa 02', 'Mesa 02'), ('mesa 03', 'Mesa 03'),
        ('mesa 04', 'Mesa 04'), ('mesa 05', 'Mesa 05'), ('mesa 06', 'Mesa 06'),
        ('mesa 07', 'Mesa 07'), ('mesa 08', 'Mesa 08'), ('mesa 09', 'Mesa 09'),
        ('mesa 10', 'Mesa 10'),
    ]

    numero = models.CharField(max_length=20, choices=NUMERO_CHOICES, verbose_name="Número de Mesa")
    capacidad = models.IntegerField(default=4, verbose_name="Capacidad")
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='disponible', verbose_name="Estado"
    )
    ubicacion = models.CharField(max_length=100, blank=True, verbose_name="Ubicación")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"

    @property
    def numero_display(self):
        if self.numero.startswith('mesa '):
            return self.numero[5:]
        return self.numero

    def __str__(self):
        return f"Mesa {self.numero_display} - {self.get_estado_display()}"


# =============================================================================
# DELIVERY CONFIG
# =============================================================================

class DeliveryConfig(models.Model):
    """Configuración para códigos de delivery y para llevar"""
    TIPO_CHOICES = [
        ('delivery', 'Delivery'),
        ('llevar', 'Para Llevar'),
    ]
    CODIGO_CHOICES = [
        ('D001', 'D001'), ('D002', 'D002'), ('D003', 'D003'), ('D004', 'D004'), ('D005', 'D005'),
        ('L001', 'L001'), ('L002', 'L002'), ('L003', 'L003'), ('L004', 'L004'), ('L005', 'L005'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='delivery', verbose_name="Tipo")
    codigo = models.CharField(max_length=10, choices=CODIGO_CHOICES, verbose_name="Código")
    estado = models.CharField(
        max_length=20,
        choices=[('disponible', 'Disponible'), ('ocupado', 'Ocupado'), ('inactivo', 'Inactivo')],
        default='disponible',
        verbose_name="Estado"
    )
    descripcion = models.CharField(max_length=200, blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Configuración Código"
        verbose_name_plural = "Configuraciones Códigos"
        unique_together = ['tipo', 'codigo']

    def __str__(self):
        tipo_display = "Delivery" if self.tipo == 'delivery' else "Para Llevar"
        return f"{tipo_display} {self.codigo}"


# =============================================================================
# PEDIDO
# =============================================================================

class Pedido(models.Model):
    """Modelo principal para los pedidos"""
    TIPO_PEDIDO_CHOICES = [
        ('mesa', 'Mesa'),
        ('delivery', 'Delivery'),
        ('llevar', 'Para Llevar'),
    ]
    ESTADO_PEDIDO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('preparacion', 'En Preparación'),
        ('listo', 'Listo para Servir'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
        ('completado', 'Completado'),
    ]

    codigo_pedido = models.CharField(max_length=20, unique=True, verbose_name="Código de Pedido")
    tipo_pedido = models.CharField(max_length=20, choices=TIPO_PEDIDO_CHOICES, verbose_name="Tipo de Pedido")

    mesa = models.ForeignKey(
        'Mesa', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Mesa", related_name='pedidos'
    )
    codigo_delivery = models.CharField(max_length=10, blank=True, verbose_name="Código Delivery")

    nombre_cliente = models.CharField(max_length=200, blank=True, verbose_name="Nombre del Cliente")
    telefono_cliente = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    direccion_entrega = models.TextField(blank=True, verbose_name="Dirección de Entrega")

    items = models.JSONField(verbose_name="Items del Pedido", help_text="Lista de platos en formato JSON")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal")
    envio = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Costo de Envío")
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total")

    estado = models.CharField(
        max_length=20, choices=ESTADO_PEDIDO_CHOICES, default='pendiente', verbose_name="Estado del Pedido"
    )
    fecha_pedido = models.DateTimeField(default=timezone.now, verbose_name="Fecha del Pedido")
    fecha_entrega = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Entrega")
    notas = models.TextField(blank=True, verbose_name="Notas del Pedido")

    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='pedidos_creados', verbose_name="Creado por"
    )
    actualizado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='pedidos_actualizados', verbose_name="Actualizado por"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_pedido']
        indexes = [
            models.Index(fields=['codigo_pedido']),
            models.Index(fields=['estado']),
            models.Index(fields=['tipo_pedido']),
            models.Index(fields=['fecha_pedido']),
        ]

    def __str__(self):
        return f"Pedido {self.codigo_pedido} - {self.get_tipo_pedido_display()}"

    def liberar_mesa_si_corresponde(self):
        """Libera la mesa si la factura está pagada o el pedido está cancelado"""
        if self.tipo_pedido == 'mesa' and self.mesa:
            if self.facturas.filter(estado='pagada').exists():
                self.mesa.estado = 'disponible'
                self.mesa.save()
                return True
            elif self.estado == 'cancelado':
                self.mesa.estado = 'disponible'
                self.mesa.save()
                return True
        return False

    def save(self, *args, **kwargs):
        if not self.codigo_pedido:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d')
            last_pedido = Pedido.objects.filter(
                codigo_pedido__startswith=f'ORD-{timestamp}'
            ).order_by('-codigo_pedido').first()
            new_num = (int(last_pedido.codigo_pedido.split('-')[-1]) + 1) if last_pedido else 1
            self.codigo_pedido = f'ORD-{timestamp}-{new_num:04d}'

        super().save(*args, **kwargs)

        if self.tipo_pedido == 'mesa' and self.mesa:
            if self.estado in ['pendiente', 'confirmado', 'preparacion', 'listo', 'entregado']:
                if self.mesa.estado != 'ocupada':
                    self.mesa.estado = 'ocupada'
                    self.mesa.save()
            elif self.estado in ['completado', 'cancelado']:
                self.liberar_mesa_si_corresponde()

    @property
    def tiene_factura_pagada(self):
        return self.facturas.filter(estado='pagada').exists()

    @property
    def mesa_debe_estar_ocupada(self):
        if not self.mesa:
            return False
        if self.tiene_factura_pagada:
            return False
        if self.estado == 'cancelado':
            return False
        return True

    def get_items_detalle(self):
        try:
            return json.loads(self.items) if isinstance(self.items, str) else self.items
        except Exception:
            return []

    def get_tiempo_preparacion_estimado(self):
        return sum(item.get('prepTime', 0) for item in self.get_items_detalle())

    def get_cantidad_items(self):
        return sum(item.get('quantity', 0) for item in self.get_items_detalle())


# =============================================================================
# DETALLE ITEM PEDIDO
# =============================================================================

class DetalleItemPedido(models.Model):
    """Modelo auxiliar para desnormalizar los items del pedido"""
    TIPOS_ITEM = [
        ('plato', 'Plato'),
        ('bebida', 'Bebida'),
    ]

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles_items')
    id_plato = models.IntegerField(verbose_name="ID del Plato/Bebida")
    nombre_plato = models.CharField(max_length=200, verbose_name="Nombre del Plato/Bebida")
    cantidad = models.IntegerField(verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")
    subtotal_item = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal Item")
    tipo_item = models.CharField(max_length=20, choices=TIPOS_ITEM, default='plato', verbose_name="Tipo de Item")
    notas = models.TextField(blank=True, verbose_name="Notas del Item")

    class Meta:
        verbose_name = "Detalle Item Pedido"
        verbose_name_plural = "Detalles Items Pedido"

    def __str__(self):
        return f"{self.nombre_plato} x{self.cantidad}"


# =============================================================================
# HISTORIAL ESTADO PEDIDO
# =============================================================================

class HistorialEstadoPedido(models.Model):
    """Modelo para rastrear cambios de estado del pedido"""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='historial_estados')
    estado_anterior = models.CharField(max_length=20)
    estado_nuevo = models.CharField(max_length=20)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField(blank=True)

    class Meta:
        verbose_name = "Historial Estado Pedido"
        verbose_name_plural = "Historial Estados Pedido"
        ordering = ['-fecha_cambio']

    def __str__(self):
        return f"Cambio de {self.estado_anterior} a {self.estado_nuevo}"


# =============================================================================
# FACTURA SEQUENCE
# =============================================================================

class FacturaSequence(models.Model):
    """Contador atómico por mes para generación segura de numero_factura"""
    month = models.CharField(max_length=6, unique=True)  # YYYYMM
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Secuencia de Factura"
        verbose_name_plural = "Secuencias de Factura"


# =============================================================================
# FACTURA
# =============================================================================

class Factura(models.Model):
    """Modelo para almacenar facturas generadas"""

    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta de Crédito/Débito'),
        ('transferencia', 'Transferencia Bancaria'),
    ]

    # ── FASE 4: Máquina de estados ─────────────────────────────────────────────
    ESTADO_FACTURA_CHOICES = [
        ('pendiente',             'Pendiente'),
        ('pagada',                'Pagada'),
        ('anulada',               'Anulada'),
        ('parcialmente_devuelta', 'Parcialmente Devuelta'),
        ('totalmente_devuelta',   'Totalmente Devuelta'),
    ]

    # Transiciones válidas: desde qué estado se puede ir a qué estado
    TRANSICIONES_VALIDAS = {
        'pendiente':              ['pagada', 'anulada'],
        'pagada':                 ['parcialmente_devuelta', 'totalmente_devuelta', 'anulada'],
        'parcialmente_devuelta':  ['totalmente_devuelta', 'anulada'],
        'totalmente_devuelta':    [],
        'anulada':                [],
    }

    # Relación con el pedido
    pedido = models.ForeignKey(
        'Pedido', on_delete=models.CASCADE,
        related_name='facturas', verbose_name="Pedido"
    )

    numero_factura = models.CharField(max_length=50, unique=True, verbose_name="Número de Factura")
    fecha_factura = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Factura")

    tipo_pedido = models.CharField(max_length=20, verbose_name="Tipo de Pedido")
    numero_mesa_codigo = models.CharField(max_length=20, blank=True, verbose_name="Número de Mesa/Código")
    nombre_cliente = models.CharField(max_length=200, blank=True, verbose_name="Nombre del Cliente")
    telefono_cliente = models.CharField(max_length=20, blank=True, verbose_name="Teléfono del Cliente")
    direccion_entrega = models.TextField(blank=True, verbose_name="Dirección de Entrega")

    metodo_pago = models.CharField(
        max_length=20, choices=METODO_PAGO_CHOICES, default='efectivo', verbose_name="Método de Pago"
    )
    estado = models.CharField(
        max_length=30, choices=ESTADO_FACTURA_CHOICES, default='pendiente', verbose_name="Estado de la Factura"
    )

    # Campos legacy — no escribir nuevo código en estos, usar Devolucion/DetalleDevolucion
    productos_devueltos = models.JSONField(
        null=True, blank=True,
        verbose_name="Productos Devueltos (legacy)",
        help_text="Campo legacy. Los nuevos registros usan DetalleDevolucion."
    )
    fecha_devolucion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Devolución")

    # Anulación
    motivo_anulacion = models.TextField(blank=True, verbose_name="Motivo de Anulación")
    fecha_anulacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Anulación")
    usuario_anulacion = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='facturas_anuladas', verbose_name="Anulado por"
    )

    # Totales
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal")
    iva = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="IVA 12%")
    envio = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Costo de Envío")
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Descuento")
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total")

    items = models.JSONField(verbose_name="Items de la Factura", help_text="Items en formato JSON")
    notas = models.TextField(blank=True, verbose_name="Notas Adicionales")

    impresa = models.BooleanField(default=False, verbose_name="Factura Impresa")
    fecha_impresion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Impresión")

    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='facturas_creadas', verbose_name="Creado por"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_factura']
        indexes = [
            models.Index(fields=['numero_factura']),
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_factura']),
        ]

    def __str__(self):
        return f"Factura {self.numero_factura} - Pedido: {self.pedido.codigo_pedido}"

    # ── FASE 1: Bloquear eliminación ───────────────────────────────────────────
    def delete(self, *args, **kwargs):
        """Las facturas nunca se eliminan. Usar anular()."""
        raise models.ProtectedError(
            "No se permite eliminar facturas. Use el método anular().",
            [self]
        )

    # ── FASE 4: Máquina de estados ─────────────────────────────────────────────
    def cambiar_estado(self, nuevo_estado):
        """
        Cambia el estado validando que la transición sea permitida.
        Lanza ValueError si la transición no es válida.
        """
        permitidos = self.TRANSICIONES_VALIDAS.get(self.estado, [])
        if nuevo_estado not in permitidos:
            raise ValueError(
                f"Transición inválida: '{self.estado}' → '{nuevo_estado}'. "
                f"Transiciones permitidas: {permitidos or ['ninguna']}"
            )
        self.estado = nuevo_estado
        self.save(update_fields=['estado'])

    # ── FASE 1: Método anular ──────────────────────────────────────────────────
    def anular(self, usuario, motivo=""):
        """
        Anula la factura registrando usuario, fecha y motivo.
        Cancela el pedido asociado y libera la mesa si aplica.
        Cancela la cuenta por cobrar si existe.
        No modifica ningún dato original de la venta.
        """
        if self.estado == 'anulada':
            raise ValueError("La factura ya está anulada.")

        with transaction.atomic():
            self.estado = 'anulada'
            self.motivo_anulacion = motivo
            self.fecha_anulacion = timezone.now()
            self.usuario_anulacion = usuario
            self.save(update_fields=['estado', 'motivo_anulacion', 'fecha_anulacion', 'usuario_anulacion'])

            if self.pedido:
                self.pedido.estado = 'cancelado'
                self.pedido.save(update_fields=['estado'])
                self.pedido.liberar_mesa_si_corresponde()

            if hasattr(self, 'cuenta_por_cobrar'):
                cxc = self.cuenta_por_cobrar
                cxc.estado = 'cancelada'
                cxc.saldo_pendiente = Decimal('0.00')
                cxc.save(update_fields=['estado', 'saldo_pendiente'])

    # ── FASE 3: Actualizar estado post-devolución ──────────────────────────────
    def actualizar_estado_devolucion(self):
        """
        Recalcula el estado de la factura según el total devuelto acumulado.
        Llamar después de crear cada Devolucion.
        No actúa sobre facturas anuladas.
        """
        if self.estado == 'anulada':
            return

        total_devuelto = self.devoluciones.aggregate(
            total=models.Sum('monto_devuelto')
        )['total'] or Decimal('0.00')

        if total_devuelto >= self.total:
            nuevo_estado = 'totalmente_devuelta'
        elif total_devuelto > Decimal('0.00'):
            nuevo_estado = 'parcialmente_devuelta'
        else:
            return

        self.estado = nuevo_estado
        self.save(update_fields=['estado'])

    # ── FASE 6: marcar_como_pagada con transaction ─────────────────────────────
    def marcar_como_pagada(self):
        """Marca la factura como pagada y actualiza el estado del pedido."""
        with transaction.atomic():
            self.estado = 'pagada'
            self.save(update_fields=['estado'])
            if self.pedido:
                self.pedido.estado = 'completado'
                self.pedido.save(update_fields=['estado'])

    def marcar_impresa(self):
        """Marca la factura como impresa."""
        self.impresa = True
        self.fecha_impresion = timezone.now()
        self.save(update_fields=['impresa', 'fecha_impresion'])

    # ── Generación de número de factura ───────────────────────────────────────
    def save(self, *args, **kwargs):
        if not self.numero_factura:
            timestamp = timezone.now().strftime('%Y%m')
            for _ in range(5):
                with transaction.atomic():
                    seq, _ = FacturaSequence.objects.select_for_update().get_or_create(month=timestamp)
                    existentes_mes = Factura.objects.filter(
                        numero_factura__startswith=f'FAC-{timestamp}-'
                    ).values_list('numero_factura', flat=True)
                    max_existente = 0
                    for numero in existentes_mes:
                        try:
                            correlativo = int(str(numero).rsplit('-', 1)[-1])
                            if correlativo > max_existente:
                                max_existente = correlativo
                        except (ValueError, TypeError):
                            continue
                    if seq.last_number < max_existente:
                        seq.last_number = max_existente
                    seq.last_number += 1
                    next_num = seq.last_number
                    seq.save(update_fields=['last_number'])
                    self.numero_factura = f'FAC-{timestamp}-{next_num:06d}'
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    self.numero_factura = ''
            raise IntegrityError('No se pudo generar un numero_factura único tras varios intentos')
        super().save(*args, **kwargs)

    # ── Métodos de consulta ────────────────────────────────────────────────────
    def get_items_detalle(self, enrich_from_db=True, debug=False):
        """Obtener los items de la factura como lista normalizada."""
        try:
            debug_enabled = bool(debug and settings.DEBUG)
            items_raw = self.items

            if not items_raw:
                return []

            if isinstance(items_raw, str):
                items_raw = items_raw.strip()
                if not items_raw:
                    return []
                try:
                    items = json.loads(items_raw)
                except json.JSONDecodeError:
                    try:
                        if items_raw.startswith("'") and items_raw.endswith("'"):
                            items_raw = items_raw[1:-1].replace("'", '"')
                        items_raw = items_raw.replace("'", '"')
                        items = json.loads(items_raw)
                    except Exception:
                        return []
            else:
                items = items_raw

            if isinstance(items, dict):
                if 'items' in items:
                    items = items['items']
                elif 'productos' in items:
                    items = items['productos']
                else:
                    items = [items]

            if not isinstance(items, list):
                items = [items] if items else []

            if not items:
                return []

            items_normalizados = []
            for i, item in enumerate(items):
                nombre = (
                    item.get('nombre') or item.get('name') or
                    item.get('producto') or item.get('product') or f'Producto {i+1}'
                )
                try:
                    cantidad = float(str(item.get('cantidad') or item.get('quantity') or item.get('qty') or '1'))
                except (ValueError, TypeError):
                    cantidad = 1.0

                try:
                    precio = float(str(item.get('precio') or item.get('price') or item.get('unit_price') or '0'))
                except (ValueError, TypeError):
                    precio = 0.0

                subtotal = cantidad * precio
                categoria = (
                    item.get('categoria') or item.get('category') or item.get('categ') or 'otro'
                ).lower()
                producto_id = item.get('producto_id') or item.get('product_id') or item.get('id')
                codigo = item.get('codigo') or item.get('code') or ''

                if enrich_from_db and (not codigo or categoria == 'otro'):
                    producto_db = None
                    plato_db = None
                    if producto_id:
                        producto_db = Producto.objects.filter(id=producto_id).first()
                    if not producto_db and nombre:
                        producto_db = Producto.objects.filter(nombre__iexact=nombre.strip()).first()
                    if not producto_db and nombre:
                        producto_db = Producto.objects.filter(nombre__icontains=nombre.strip()).first()
                    if not producto_db:
                        if producto_id:
                            plato_db = Plato.objects.filter(id=producto_id).first()
                        if not plato_db and nombre:
                            plato_db = Plato.objects.filter(nombre__iexact=nombre.strip()).first()
                        if not plato_db and nombre:
                            plato_db = Plato.objects.filter(nombre__icontains=nombre.strip()).first()
                    if producto_db:
                        if not codigo:
                            codigo = producto_db.codigo
                        if categoria == 'otro':
                            categoria = producto_db.categoria.lower()
                    elif plato_db:
                        if not codigo:
                            codigo = plato_db.codigo
                        if categoria == 'otro':
                            categoria = plato_db.categoria.lower()

                items_normalizados.append({
                    'producto_id': producto_id,
                    'codigo': codigo,
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'precio': precio,
                    'subtotal': subtotal,
                    'categoria': categoria,
                })
            return items_normalizados
        except Exception:
            return []

    def get_cantidad_ya_devuelta(self, producto_nombre):
        """Calcular cuántas unidades de un producto ya fueron devueltas."""
        total_devuelto = 0
        nombre_ref = str(producto_nombre).strip().lower()
        for devolucion in self.devoluciones.prefetch_related('detalles'):
            detalles = list(devolucion.detalles.all())
            if detalles:
                for detalle in detalles:
                    if str(detalle.nombre_producto).strip().lower() == nombre_ref:
                        total_devuelto += float(detalle.cantidad or 0)
                continue

            # Fallback legacy JSON
            if devolucion.productos_devueltos:
                for producto in devolucion.productos_devueltos:
                    if str(producto.get('nombre', '')).strip().lower() == nombre_ref:
                        total_devuelto += float(producto.get('cantidad', 0))
        return total_devuelto

    def get_productos_disponibles_devolucion(self):
        """Obtener productos con cantidades disponibles para devolución."""
        productos_disponibles = []
        for item in self.get_items_detalle():
            nombre = item.get('nombre', '')
            cantidad_original = float(item.get('cantidad', 0))
            cantidad_devuelta = self.get_cantidad_ya_devuelta(nombre)
            cantidad_disponible = cantidad_original - cantidad_devuelta
            if cantidad_disponible > 0:
                item_copy = item.copy()
                item_copy['cantidad_disponible'] = cantidad_disponible
                item_copy['cantidad_ya_devuelta'] = cantidad_devuelta
                productos_disponibles.append(item_copy)
        return productos_disponibles

    def get_resumen_devoluciones(self):
        """Obtener resumen completo de devoluciones."""
        resumen = {'total_devuelto': Decimal('0.00'), 'productos': {}}
        for devolucion in self.devoluciones.prefetch_related('detalles'):
            resumen['total_devuelto'] += devolucion.monto_devuelto

            detalles = list(devolucion.detalles.all())
            if detalles:
                for detalle in detalles:
                    nombre = detalle.nombre_producto or ''
                    cantidad = float(detalle.cantidad or 0)
                    resumen['productos'][nombre] = resumen['productos'].get(nombre, 0) + cantidad
                continue

            # Fallback legacy JSON
            if devolucion.productos_devueltos:
                for producto in devolucion.productos_devueltos:
                    nombre = producto.get('nombre', '')
                    cantidad = float(producto.get('cantidad', 0))
                    resumen['productos'][nombre] = resumen['productos'].get(nombre, 0) + cantidad
        return resumen

    def get_cantidad_items(self):
        return sum(item.get('cantidad', 0) for item in self.get_items_detalle())

    def get_resumen_productos(self):
        return [
            {
                'nombre': item.get('nombre', 'Desconocido'),
                'codigo': item.get('codigo', 'Sin código'),
                'cantidad': item.get('cantidad', 0),
                'categoria': item.get('categoria', 'Desconocida'),
            }
            for item in self.get_items_detalle()
        ]

# =============================================================================
# FACTURA DETALLE
# =============================================================================

class FacturaDetalle(models.Model):
    """
    Detalle relacional de una factura.
    Migración progresiva desde Factura.items (JSONField).
    El JSONField se mantiene intacto durante toda la transición.
    """
    factura = models.ForeignKey(
        Factura,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Factura'
    )
    nombre_producto = models.CharField(
        max_length=200,
        verbose_name='Nombre del Producto'
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Cantidad'
    )
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Precio Unitario'
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Subtotal'
    )

    class Meta:
        verbose_name = 'Detalle de Factura'
        verbose_name_plural = 'Detalles de Factura'

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_producto} — ${self.subtotal}"

    def save(self, *args, **kwargs):
        if not self.subtotal:
            self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

# =============================================================================
# SALIDA DE PRODUCTO
# =============================================================================

class SalidaProducto(models.Model):
    MOTIVOS = [
        ('venta', 'Venta'),
        ('dano', 'Daño/Desperdicio'),
        ('ajuste', 'Ajuste de Inventario'),
        ('consumo', 'Consumo Interno'),
        ('otro', 'Otro'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='salidas')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad retirada")
    motivo = models.CharField(max_length=50, choices=MOTIVOS, verbose_name="Motivo de salida")
    responsable = models.CharField(max_length=200, verbose_name="Responsable")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")

    class Meta:
        verbose_name = "Salida de Producto"
        verbose_name_plural = "Salidas de Productos"
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.cantidad} de {self.producto.nombre} - {self.motivo}"


# =============================================================================
# DEVOLUCION
# =============================================================================

class Devolucion(models.Model):
    """
    Cabecera de una devolución.
    Una factura puede tener múltiples devoluciones parciales.
    Los ítems devueltos se registran en DetalleDevolucion.
    """

    TIPO_DEVOLUCION_CHOICES = [
        ('total',   'Devolución Total'),
        ('parcial', 'Devolución Parcial'),
        ('cambio',  'Cambio de Producto'),
    ]

    factura = models.ForeignKey(
        Factura, on_delete=models.CASCADE,
        related_name='devoluciones', verbose_name="Factura"
    )
    tipo_devolucion = models.CharField(
        max_length=20, choices=TIPO_DEVOLUCION_CHOICES, verbose_name="Tipo de Devolución"
    )

    # Legacy — no escribir aquí en registros nuevos, usar DetalleDevolucion
    productos_devueltos = models.JSONField(
        null=True, blank=True,
        verbose_name="Productos Devueltos (legacy)",
        help_text="Campo legacy. Los nuevos registros usan DetalleDevolucion."
    )

    monto_devuelto = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('0.00'), verbose_name="Monto Devuelto"
    )
    motivo = models.TextField(blank=True, verbose_name="Motivo de la Devolución")
    fecha_devolucion = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Devolución")
    procesado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='devoluciones_procesadas', verbose_name="Procesado por"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Devolución"
        verbose_name_plural = "Devoluciones"
        ordering = ['-fecha_devolucion']

    def __str__(self):
        return f"Devolución #{self.id} — Factura: {self.factura.numero_factura}"

    # ── FASE 3: Procesar devolución ────────────────────────────────────────────
    def procesar(self):
        """
        Aplica la devolución actualizando el estado de la factura.
        Valida que la factura no esté anulada.
        Debe llamarse dentro de un transaction.atomic() en la view.
        """
        factura = self.factura

        if factura.estado == 'anulada':
            raise ValueError("No se puede registrar una devolución en una factura anulada.")

        total_devuelto = factura.devoluciones.aggregate(
            total=models.Sum('monto_devuelto')
        )['total'] or Decimal('0.00')

        if total_devuelto >= factura.total:
            factura.estado = 'totalmente_devuelta'
        else:
            factura.estado = 'parcialmente_devuelta'

        factura.save(update_fields=['estado'])

    def calcular_monto_desde_detalles(self):
        """
        Recalcula monto_devuelto sumando los DetalleDevolucion asociados.
        Actualiza el campo en base de datos.
        """
        total = self.detalles.aggregate(
            total=models.Sum('monto')
        )['total'] or Decimal('0.00')
        self.monto_devuelto = total
        self.save(update_fields=['monto_devuelto'])
        return self.monto_devuelto


# =============================================================================
# DETALLE DEVOLUCION
# =============================================================================

class DetalleDevolucion(models.Model):
    """
    Línea de detalle de una devolución.
    Registra qué producto, en qué cantidad y por qué monto fue devuelto.
    El nombre se guarda en texto para preservar trazabilidad histórica.
    """

    devolucion = models.ForeignKey(
        Devolucion, on_delete=models.CASCADE,
        related_name='detalles', verbose_name="Devolución"
    )
    nombre_producto = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Devuelta")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Devuelto")

    class Meta:
        verbose_name = "Detalle de Devolución"
        verbose_name_plural = "Detalles de Devolución"

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_producto} — ${self.monto}"

    def save(self, *args, **kwargs):
        # Calcular monto automáticamente si no viene definido
        if not self.monto:
            self.monto = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)


# =============================================================================
# CUENTA POR COBRAR
# =============================================================================

class CuentaPorCobrar(models.Model):
    """Cuenta por cobrar asociada a una factura de crédito."""

    ESTADO_CHOICES = [
        ('pendiente',  'Pendiente'),
        ('parcial',    'Parcialmente Pagada'),
        ('pagada',     'Pagada'),
        ('vencida',    'Vencida'),
        ('cancelada',  'Cancelada'),   # ← necesario para el flujo de anulación
    ]

    factura = models.OneToOneField(
        Factura, on_delete=models.CASCADE,
        related_name='cuenta_por_cobrar', verbose_name='Factura'
    )
    cliente = models.ForeignKey(
        'Cliente', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cuentas_por_cobrar', verbose_name='Cliente'
    )
    fecha_emision = models.DateField(verbose_name='Fecha de emision')
    fecha_vencimiento = models.DateField(verbose_name='Fecha de vencimiento')
    monto_original = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto original')
    saldo_pendiente = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Saldo pendiente')
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado'
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cuenta por Cobrar'
        verbose_name_plural = 'Cuentas por Cobrar'
        ordering = ['-fecha_vencimiento']
        db_table = 'cuentaporcobrar'

    def __str__(self):
        return f"CxC {self.factura.numero_factura} - Saldo {self.saldo_pendiente}"

    # ── FASE 2: Aplicar pago ───────────────────────────────────────────────────
    def aplicar_pago(self, monto):
        """
        Descuenta el monto del saldo pendiente y actualiza el estado.
        Lanza ValueError si el monto es inválido o excede el saldo.
        NO llamar desde PagoCuentaCobrar.save() — llamar desde la view.
        """
        if monto <= 0:
            raise ValueError("El monto debe ser mayor a cero.")
        if monto > self.saldo_pendiente:
            raise ValueError(
                f"El pago RD$ {monto} excede el saldo pendiente RD$ {self.saldo_pendiente}."
            )
        with transaction.atomic():
            self.saldo_pendiente -= monto
            self.estado = 'pagada' if self.saldo_pendiente <= 0 else 'parcial'
            self.save(update_fields=['saldo_pendiente', 'estado'])


# =============================================================================
# PAGO CUENTA POR COBRAR
# =============================================================================

class PagoCuentaCobrar(models.Model):
    """Pagos aplicados a facturas pendientes para cuentas por cobrar."""

    METODO_PAGO_CHOICES = [
        ('efectivo',       'Efectivo'),
        ('tarjeta',        'Tarjeta de Crédito/Débito'),
        ('transferencia',  'Transferencia Bancaria'),
    ]

    cuenta_por_cobrar = models.ForeignKey(
        CuentaPorCobrar, on_delete=models.CASCADE,
        related_name='pagos', null=True, blank=True, verbose_name='Cuenta por cobrar'
    )
    factura = models.ForeignKey(
        Factura, on_delete=models.CASCADE,
        related_name='pagos_cxc', verbose_name='Factura'
    )
    monto = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto pagado'
    )
    fecha_pago = models.DateTimeField(default=timezone.now, verbose_name='Fecha y hora de pago')
    metodo_pago = models.CharField(
        max_length=20, choices=METODO_PAGO_CHOICES, default='efectivo', verbose_name='Metodo de pago'
    )
    referencia = models.CharField(max_length=120, blank=True, verbose_name='Referencia')
    numero_comprobante = models.CharField(
        max_length=40, unique=True, null=True, blank=True, verbose_name='Numero de comprobante'
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pagos_cuentas_cobrar', verbose_name='Registrado por'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # UUID para idempotencia — debe generarse en el frontend antes de enviar
    # En pagos distribuidos se usa uuid5(uuid_base, str(factura.id)) para derivar
    # un UUID válido por factura sin romper el formato UUID estándar
    uuid_pago = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name='UUID de pago (idempotencia)'
    )

    class Meta:
        verbose_name = 'Pago de Cuenta por Cobrar'
        verbose_name_plural = 'Pagos de Cuentas por Cobrar'
        ordering = ['-fecha_pago', '-id']
        db_table = 'pagocuentacobrar'

    def __str__(self):
        comprobante = self.numero_comprobante or f"CP-{self.id}"
        return f"{comprobante} - {self.factura.numero_factura} - {self.monto}"

    def _generar_numero_comprobante(self):
        fecha_ref = self.fecha_pago or timezone.localdate()
        numero_factura = (self.factura.numero_factura or '').strip()
        match = re.match(r'^[A-Z]+-(\d{6})-(\d+)$', numero_factura)
        if match:
            periodo = match.group(1)
            secuencia = match.group(2)
            pagos_previos = type(self).objects.filter(
                factura=self.factura
            ).exclude(pk=self.pk).count()
            indice_pago = pagos_previos + 1
            if indice_pago == 1:
                return f"CP-{periodo}-{secuencia}"
            return f"CP-{periodo}-{secuencia}-{indice_pago:02d}"
        return f"CP-{fecha_ref.strftime('%Y%m')}-{self.pk:06d}"

    def save(self, *args, **kwargs):
        if self.pk is None and not self.numero_comprobante:
            super().save(*args, **kwargs)
            self.numero_comprobante = self._generar_numero_comprobante()
            type(self).objects.filter(pk=self.pk).update(
                numero_comprobante=self.numero_comprobante
            )
            return
        if not self.numero_comprobante and self.pk is not None:
            self.numero_comprobante = self._generar_numero_comprobante()
        super().save(*args, **kwargs)


# =============================================================================
# CLIENTE
# =============================================================================

class Cliente(models.Model):
    cedula = models.CharField(
        max_length=11, unique=True,
        verbose_name="Cédula", help_text="Debe contener exactamente 11 dígitos"
    )
    nombre_completo = models.CharField(max_length=200, verbose_name="Nombre Completo")
    direccion = models.TextField(verbose_name="Dirección")
    telefono_principal = models.CharField(max_length=10, verbose_name="Teléfono Principal")
    telefono_alternativo = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Teléfono Alternativo"
    )
    limite_credito = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0)], verbose_name="Límite de Crédito"
    )
    dias_credito = models.PositiveIntegerField(
        default=30, validators=[MaxValueValidator(365)], verbose_name="Días de Crédito"
    )
    notas_credito = models.TextField(blank=True, null=True, verbose_name="Notas sobre Crédito")
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='clientes_registrados', verbose_name='Registrado por'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    activo = models.BooleanField(default=True, verbose_name="Cliente Activo")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre_completo']
        indexes = [
            models.Index(fields=['cedula']),
            models.Index(fields=['nombre_completo']),
        ]

    def __str__(self):
        return f"{self.nombre_completo} ({self.cedula})"

    @property
    def tiene_credito(self):
        return self.limite_credito > 0

    @property
    def venta_contado(self):
        return self.dias_credito == 0