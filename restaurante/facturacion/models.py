from django.db import models
from django.utils import timezone
import random
import string
from decimal import Decimal
from django.db.models import Max
import re
from django.contrib.auth.models import User
import json
from django.core.validators import MinValueValidator, MaxValueValidator

class Producto(models.Model):
    # Opciones de categoría
    CATEGORIAS = [
        ('bebida', 'Bebida'),
        ('postre', 'Postre'),
        ('carne', 'Carne'),
        ('verdura', 'Verdura'),
        ('lacteo', 'Lácteo'),
        ('otro', 'Otro'),
    ]
    
    # ID único para cada producto
    codigo = models.CharField(
        max_length=50, 
        unique=True, 
        editable=False,
        help_text="Código único del producto"
    )
    
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del Producto"
    )
    
    categoria = models.CharField(
        max_length=50,
        choices=CATEGORIAS,
        verbose_name="Categoría"
    )
    
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Cantidad",
        help_text="Cantidad en stock"
    )
    
    precio_compra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio de Compra"
    )
    
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        default=Decimal('0.00'),
        verbose_name="Subtotal"
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de actualización"
    )
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['-fecha_creacion']
    
    def save(self, *args, **kwargs):
        # Generar código automático si no existe
        if not self.codigo:
            categoria_abrev = self.categoria[:3].upper() if self.categoria else 'GEN'
            fecha = timezone.now().strftime("%y%m%d")
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            self.codigo = f"PROD-{categoria_abrev}-{fecha}-{random_str}"
        
        # Calcular subtotal automáticamente
        self.subtotal = self.cantidad * self.precio_compra
        
        super().save(*args, **kwargs)
    
    def get_category_label(self):
        """Obtener etiqueta legible de la categoría"""
        for code, label in self.CATEGORIAS:
            if code == self.categoria:
                return label
        return self.categoria
    
    def get_stock_status(self):
        """Determinar el estado del stock"""
        cantidad = float(self.cantidad)
        if cantidad >= 50:
            return 'high'
        elif cantidad >= 10:
            return 'medium'
        else:
            return 'low'
    
    def get_stock_label(self):
        """Obtener etiqueta del estado del stock"""
        status = self.get_stock_status()
        labels = {
            'high': 'Alto',
            'medium': 'Medio',
            'low': 'Bajo'
        }
        return labels.get(status, 'Desconocido')
    
    def get_stock_icon(self):
        """Obtener icono del estado del stock"""
        status = self.get_stock_status()
        icons = {
            'high': '📈',
            'medium': '📊',
            'low': '📉'
        }
        return icons.get(status, '📦')
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre} (${self.subtotal:.2f})"



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
        # Generar código automáticamente si no existe
        if not self.codigo:
            self.codigo = self.generar_codigo()
        super().save(*args, **kwargs)
    
    @classmethod
    def generar_codigo(cls):
        # Obtener el último código existente
        ultimo_plato = cls.objects.filter(
            codigo__regex=r'^COD\d{3}$'
        ).order_by('codigo').last()
        
        if ultimo_plato:
            # Extraer el número del último código
            ultimo_numero = int(re.search(r'\d+', ultimo_plato.codigo).group())
            nuevo_numero = ultimo_numero + 1
        else:
            nuevo_numero = 1
        
        # Formatear como COD001, COD002, etc.
        return f"COD{nuevo_numero:03d}"
    
    def get_categoria_display_color(self):
        """Devuelve el color según la categoría para mostrar en el frontend"""
        colores = {
            'entrada': 'warning',
            'principal': 'danger',
            'postre': 'warning',
            'bebida': 'primary',
            'rapida': 'success',
            'especial': 'info',
        }
        return colores.get(self.categoria, 'secondary')
    

class Mesa(models.Model):
    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),
        ('ocupada', 'Ocupada'),
        ('reservada', 'Reservada'),
        ('mantenimiento', 'En Mantenimiento'),
    ]
    
    NUMERO_CHOICES = [
        ('mesa 01', 'Mesa 01'),
        ('mesa 02', 'Mesa 02'),
        ('mesa 03', 'Mesa 03'),
        ('mesa 04', 'Mesa 04'),
        ('mesa 05', 'Mesa 05'),
        ('mesa 06', 'Mesa 06'),
        ('mesa 07', 'Mesa 07'),
        ('mesa 08', 'Mesa 08'),
        ('mesa 09', 'Mesa 09'),
        ('mesa 10', 'Mesa 10'),
    ]
    
    numero = models.CharField(
        max_length=20,
        choices=NUMERO_CHOICES,
        verbose_name="Número de Mesa"
    )
    capacidad = models.IntegerField(default=4, verbose_name="Capacidad")
    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_CHOICES, 
        default='disponible',
        verbose_name="Estado"
    )
    ubicacion = models.CharField(max_length=100, blank=True, verbose_name="Ubicación")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def numero_display(self):
        """Propiedad para obtener solo el número sin la palabra 'mesa'"""
        # Extraer los últimos 2 caracteres (el número)
        # Si el formato es "mesa 01", devolvemos "01"
        if self.numero.startswith('mesa '):
            return self.numero[5:]  # Extrae todo después de "mesa "
        return self.numero
    
    def __str__(self):
        return f"Mesa {self.numero_display} - {self.get_estado_display()}"
    
    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"

class DeliveryConfig(models.Model):
    """Configuración para códigos de delivery y para llevar"""
    TIPO_CHOICES = [
        ('delivery', 'Delivery'),
        ('llevar', 'Para Llevar'),
    ]
    
    CODIGO_CHOICES = [
        ('D001', 'D001'),
        ('D002', 'D002'),
        ('D003', 'D003'),
        ('D004', 'D004'),
        ('D005', 'D005'),
        ('L001', 'L001'),
        ('L002', 'L002'),
        ('L003', 'L003'),
        ('L004', 'L004'),
        ('L005', 'L005'),
    ]
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='delivery',
        verbose_name="Tipo"
    )
    
    codigo = models.CharField(
        max_length=10,
        choices=CODIGO_CHOICES,
        verbose_name="Código"
    )
    
    estado = models.CharField(
        max_length=20,
        choices=[
            ('disponible', 'Disponible'),
            ('ocupado', 'Ocupado'),
            ('inactivo', 'Inactivo')
        ],
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
    
    # Información del pedido
    codigo_pedido = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Código de Pedido"
    )
    tipo_pedido = models.CharField(
        max_length=20, 
        choices=TIPO_PEDIDO_CHOICES,
        verbose_name="Tipo de Pedido"
    )
    
    # Información específica por tipo
    mesa = models.ForeignKey(
        'Mesa', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Mesa",
        related_name='pedidos'
    )
    codigo_delivery = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name="Código Delivery"
    )
    
    # Información del cliente (opcional para delivery/llevar)
    nombre_cliente = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name="Nombre del Cliente"
    )
    telefono_cliente = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Teléfono"
    )
    direccion_entrega = models.TextField(
        blank=True, 
        verbose_name="Dirección de Entrega"
    )
    
    # Detalles del pedido
    items = models.JSONField(
        verbose_name="Items del Pedido",
        help_text="Lista de platos en formato JSON"
    )
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Subtotal"
    )
    envio = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name="Costo de Envío"
    )
    total = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Total"
    )
    
    # Estado y seguimiento
    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_PEDIDO_CHOICES,
        default='pendiente',
        verbose_name="Estado del Pedido"
    )
    fecha_pedido = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha del Pedido"
    )
    fecha_entrega = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Fecha de Entrega"
    )
    notas = models.TextField(
        blank=True, 
        verbose_name="Notas del Pedido"
    )
    
    # Auditoría
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='pedidos_creados',
        verbose_name="Creado por"
    )
    actualizado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='pedidos_actualizados',
        verbose_name="Actualizado por"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Pedido {self.codigo_pedido} - {self.get_tipo_pedido_display()}"
    
    def liberar_mesa_si_corresponde(self):
        """Libera la mesa si la factura está pagada o el pedido está cancelado"""
        if self.tipo_pedido == 'mesa' and self.mesa:
            # Verificar si tiene factura pagada
            if self.facturas.filter(estado='pagada').exists():
                self.mesa.estado = 'disponible'
                self.mesa.save()
                print(f"✅ Mesa {self.mesa.numero_display} liberada por factura pagada")
                return True
            # Si el pedido está cancelado, también liberar mesa
            elif self.estado == 'cancelado':
                self.mesa.estado = 'disponible'
                self.mesa.save()
                print(f"✅ Mesa {self.mesa.numero_display} liberada por pedido cancelado")
                return True
        return False
    
    def save(self, *args, **kwargs):
        # Generar código de pedido automático si no existe
        if not self.codigo_pedido:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d')
            last_pedido = Pedido.objects.filter(
                codigo_pedido__startswith=f'ORD-{timestamp}'
            ).order_by('-codigo_pedido').first()
            
            if last_pedido:
                last_num = int(last_pedido.codigo_pedido.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.codigo_pedido = f'ORD-{timestamp}-{new_num:04d}'
        
        # Guardar el pedido
        super().save(*args, **kwargs)
        
        # Si es un pedido de mesa, manejar el estado de la mesa
        if self.tipo_pedido == 'mesa' and self.mesa:
            if self.estado in ['pendiente', 'confirmado', 'preparacion', 'listo', 'entregado']:
                # Si el pedido está activo, ocupar la mesa
                if self.mesa.estado != 'ocupada':
                    self.mesa.estado = 'ocupada'
                    self.mesa.save()
                    print(f"✅ Mesa {self.mesa.numero_display} ocupada por pedido {self.codigo_pedido} (estado: {self.estado})")
            elif self.estado in ['completado', 'cancelado']:
                # Solo liberar si tiene factura pagada o está cancelado
                self.liberar_mesa_si_corresponde()
    
    # Propiedad para verificar si tiene factura pagada
    @property
    def tiene_factura_pagada(self):
        """Verifica si el pedido tiene una factura con estado 'pagada'"""
        return self.facturas.filter(estado='pagada').exists()
    
    # Propiedad para verificar si la mesa debe estar ocupada
    @property
    def mesa_debe_estar_ocupada(self):
        """Determina si la mesa debe estar ocupada basándose en el estado y facturas"""
        if not self.mesa:
            return False
        
        # Si tiene factura pagada, la mesa debe estar libre
        if self.tiene_factura_pagada:
            return False
        
        # Si el pedido está cancelado, la mesa debe estar libre
        if self.estado == 'cancelado':
            return False
        
        # Para todos los otros casos, la mesa debe estar ocupada
        return True
    
    def get_items_detalle(self):
        """Obtener los items del pedido como lista"""
        try:
            return json.loads(self.items) if isinstance(self.items, str) else self.items
        except:
            return []
    
    def get_tiempo_preparacion_estimado(self):
        """Calcular tiempo estimado de preparación"""
        items = self.get_items_detalle()
        tiempo_total = 0
        
        for item in items:
            # Asumiendo que cada item tiene un campo 'prepTime'
            tiempo_total += item.get('prepTime', 0)
        
        return tiempo_total
    
    def get_cantidad_items(self):
        """Obtener cantidad total de items"""
        items = self.get_items_detalle()
        return sum(item.get('quantity', 0) for item in items)
    
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

class DetalleItemPedido(models.Model):
    """Modelo auxiliar para desnormalizar los items del pedido (opcional)"""
    TIPOS_ITEM = [
        ('plato', 'Plato'),
        ('bebida', 'Bebida'),
    ]
    
    pedido = models.ForeignKey(
        Pedido, 
        on_delete=models.CASCADE,
        related_name='detalles_items'
    )
    id_plato = models.IntegerField(verbose_name="ID del Plato/Bebida")
    nombre_plato = models.CharField(max_length=200, verbose_name="Nombre del Plato/Bebida")
    cantidad = models.IntegerField(verbose_name="Cantidad")
    precio_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Precio Unitario"
    )
    subtotal_item = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Subtotal Item"
    )
    tipo_item = models.CharField(
        max_length=20, 
        choices=TIPOS_ITEM, 
        default='plato',
        verbose_name="Tipo de Item"
    )
    notas = models.TextField(blank=True, verbose_name="Notas del Item")
    
    def __str__(self):
        return f"{self.nombre_plato} x{self.cantidad}"
    
    class Meta:
        verbose_name = "Detalle Item Pedido"
        verbose_name_plural = "Detalles Items Pedido"


class HistorialEstadoPedido(models.Model):
    """Modelo para rastrear cambios de estado del pedido"""
    pedido = models.ForeignKey(
        Pedido, 
        on_delete=models.CASCADE,
        related_name='historial_estados'
    )
    estado_anterior = models.CharField(max_length=20)
    estado_nuevo = models.CharField(max_length=20)
    usuario = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField(blank=True)
    
    def __str__(self):
        return f"Cambio de {self.estado_anterior} a {self.estado_nuevo}"
    
    class Meta:
        verbose_name = "Historial Estado Pedido"
        verbose_name_plural = "Historial Estados Pedido"
        ordering = ['-fecha_cambio']


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json
from django.core.serializers.json import DjangoJSONEncoder


class Factura(models.Model):
    """Modelo para almacenar facturas generadas"""
    
    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta de Crédito/Débito'),
        ('transferencia', 'Transferencia Bancaria'),
    ]
    
    ESTADO_FACTURA_CHOICES = [
        ('pagada', 'Pagada'),
        ('pendiente', 'Pendiente'),
        ('anulada', 'Anulada'),
        ('parcialmente_devuelta', 'Parcialmente Devuelta'),
        ('totalmente_devuelta', 'Totalmente Devuelta'),
    ]
    
    # Relación con el pedido
    pedido = models.ForeignKey(
        'Pedido', 
        on_delete=models.CASCADE,
        related_name='facturas',
        verbose_name="Pedido"
    )
    
    # Información de la factura
    numero_factura = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="Número de Factura"
    )
    fecha_factura = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de Factura"
    )
    
    # Información del pedido
    tipo_pedido = models.CharField(
        max_length=20,
        verbose_name="Tipo de Pedido"
    )
    numero_mesa_codigo = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Número de Mesa/Código"
    )
    nombre_cliente = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del Cliente"
    )
    telefono_cliente = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Teléfono del Cliente"
    )
    direccion_entrega = models.TextField(
        blank=True,
        verbose_name="Dirección de Entrega"
    )
    
    # Detalles de pago
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        default='efectivo',
        verbose_name="Método de Pago"
    )
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_FACTURA_CHOICES,
        default='pendiente',
        verbose_name="Estado de la Factura"
    )
    
    productos_devueltos = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Productos Devueltos",
        help_text="Registro de productos devueltos en formato JSON"
    )
    
    fecha_devolucion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Devolución"
    )
    
    motivo_anulacion = models.TextField(
        blank=True,
        verbose_name="Motivo de Anulación"
    )
    
    # Totales
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Subtotal"
    )
    iva = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="IVA 12%"
    )
    envio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Costo de Envío"
    )
    descuento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Descuento"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Total"
    )
    
    # Items de la factura (JSON)
    items = models.JSONField(
        verbose_name="Items de la Factura",
        help_text="Items en formato JSON"
    )
    
    # Notas adicionales
    notas = models.TextField(
        blank=True,
        verbose_name="Notas Adicionales"
    )
    
    # Para impresión térmica
    impresa = models.BooleanField(
        default=False,
        verbose_name="Factura Impresa"
    )
    fecha_impresion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Impresión"
    )
    
    # Auditoría
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='facturas_creadas',
        verbose_name="Creado por"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    
    def __str__(self):
        return f"Factura {self.numero_factura} - Pedido: {self.pedido.codigo_pedido}"
    
    def save(self, *args, **kwargs):
        # Generar número de factura automático si no existe
        if not self.numero_factura:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m')
            last_factura = Factura.objects.filter(
                numero_factura__startswith=f'FAC-{timestamp}'
            ).order_by('-numero_factura').first()
            
            if last_factura:
                try:
                    last_num = int(last_factura.numero_factura.split('-')[-1])
                    new_num = last_num + 1
                except:
                    new_num = 1
            else:
                new_num = 1
            
            self.numero_factura = f'FAC-{timestamp}-{new_num:06d}'
        
        super().save(*args, **kwargs)
    
    def get_items_detalle(self):
        """Obtener los items de la factura como lista normalizada"""
        try:
            # Obtener items como JSON
            items_raw = self.items
            
            print(f"\n🔍 GET_ITEMS_DETALLE - Factura: {self.numero_factura}")
            print(f"   Tipo de items_raw: {type(items_raw)}")
            
            # Si items_raw es None o vacío
            if not items_raw:
                print(f"   ❌ Campo 'items' está vacío o es None")
                return []
            
            # Si es una cadena, intentar convertir a JSON
            if isinstance(items_raw, str):
                print(f"   📝 Es una cadena, intentando parsear JSON...")
                print(f"   📝 Longitud: {len(items_raw)}")
                
                items_raw = items_raw.strip()
                
                if not items_raw:
                    print(f"   ❌ Cadena vacía después de strip()")
                    return []
                
                try:
                    items = json.loads(items_raw)
                    print(f"   ✅ JSON parseado exitosamente")
                except json.JSONDecodeError as e:
                    print(f"   ❌ Error de decodificación JSON: {e}")
                    try:
                        if items_raw.startswith("'") and items_raw.endswith("'"):
                            items_raw = items_raw[1:-1].replace("'", '"')
                        items_raw = items_raw.replace("'", '"')
                        items = json.loads(items_raw)
                        print(f"   ✅ JSON reparado y parseado")
                    except Exception as e2:
                        print(f"   ❌ No se pudo reparar el JSON: {e2}")
                        return []
            else:
                items = items_raw
                print(f"   ✅ Ya es de tipo: {type(items)}")
            
            # Si items es un diccionario, convertirlo a lista
            if isinstance(items, dict):
                print(f"   🔄 Convirtiendo diccionario a lista...")
                if 'items' in items:
                    items = items['items']
                elif 'productos' in items:
                    items = items['productos']
                else:
                    items = [items]
            
            # Asegurarse de que items es una lista
            if not isinstance(items, list):
                print(f"   ⚠️  Items no es una lista, es: {type(items)}. Convirtiendo...")
                items = [items] if items else []
            
            print(f"   📋 Total de items encontrados: {len(items)}")
            
            if not items:
                print(f"   ⚠️  Lista de items vacía")
                return []
            
            # Normalizar estructura
            items_normalizados = []
            
            for i, item in enumerate(items):
                print(f"\n   🔍 Procesando item {i+1}:")
                
                nombre = (
                    item.get('nombre') or 
                    item.get('name') or 
                    item.get('producto') or 
                    item.get('product') or 
                    f'Producto {i+1}'
                )
                
                print(f"      Nombre: {nombre}")
                
                # Asegurar que cantidad sea numérico
                cantidad_str = str(item.get('cantidad') or item.get('quantity') or item.get('qty') or '1')
                try:
                    cantidad = float(cantidad_str)
                except (ValueError, TypeError):
                    cantidad = 1.0
                    print(f"      ⚠️  Cantidad inválida '{cantidad_str}', usando 1.0")
                
                print(f"      Cantidad: {cantidad}")
                
                # Asegurar que precio sea numérico
                precio_str = str(item.get('precio') or item.get('price') or item.get('unit_price') or '0')
                try:
                    precio = float(precio_str)
                except (ValueError, TypeError):
                    precio = 0.0
                    print(f"      ⚠️  Precio inválido '{precio_str}', usando 0.0")
                
                print(f"      Precio: {precio}")
                
                # Calcular subtotal
                subtotal = cantidad * precio
                
                # Obtener categoría
                categoria = (
                    item.get('categoria') or 
                    item.get('category') or 
                    item.get('categ') or 
                    'otro'
                ).lower()
                
                print(f"      Categoría: {categoria}")
                
                # Obtener IDs
                producto_id = item.get('producto_id') or item.get('product_id') or item.get('id')
                
                # Obtener código
                codigo = item.get('codigo') or item.get('code') or ''
                
                # Buscar producto en la base de datos para completar información faltante
                if not codigo or categoria == 'otro':
                    from .models import Producto  # Import local para evitar circular
                    producto_db = None
                    
                    # Buscar por ID primero
                    if producto_id:
                        try:
                            producto_db = Producto.objects.filter(id=producto_id).first()
                            if producto_db:
                                print(f"      ✅ Producto encontrado por ID: {producto_db.nombre}")
                        except Exception as e:
                            print(f"      ❌ Error al buscar producto por ID: {e}")
                    
                    # Si no se encontró por ID, buscar por nombre
                    if not producto_db and nombre:
                        try:
                            producto_db = Producto.objects.filter(
                                nombre__iexact=nombre.strip()
                            ).first()
                            if producto_db:
                                print(f"      ✅ Producto encontrado por nombre: {producto_db.nombre}")
                        except Exception as e:
                            print(f"      ❌ Error al buscar producto por nombre: {e}")
                    
                    # Completar información con datos de la base de datos
                    if producto_db:
                        if not codigo:
                            codigo = producto_db.codigo
                            print(f"      ✅ Código actualizado: {codigo}")
                        if categoria == 'otro':
                            categoria = producto_db.categoria.lower()
                            print(f"      ✅ Categoría actualizada: {categoria}")
                
                items_normalizados.append({
                    'producto_id': producto_id,
                    'codigo': codigo,
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'precio': precio,
                    'subtotal': subtotal,
                    'categoria': categoria
                })
            
            print(f"\n   ✅ Items normalizados: {len(items_normalizados)}")
            return items_normalizados
            
        except Exception as e:
            print(f"\n❌ ERROR en get_items_detalle para factura {self.numero_factura}: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_cantidad_ya_devuelta(self, producto_nombre):
        """Calcular cuántas unidades de un producto ya fueron devueltas"""
        total_devuelto = 0
        
        # Obtener todas las devoluciones de esta factura
        devoluciones = self.devoluciones.all()
        
        for devolucion in devoluciones:
            if devolucion.productos_devueltos:
                for producto in devolucion.productos_devueltos:
                    # Comparar nombres (case-insensitive y sin espacios extra)
                    nombre_dev = str(producto.get('nombre', '')).strip().lower()
                    nombre_buscar = str(producto_nombre).strip().lower()
                    
                    if nombre_dev == nombre_buscar:
                        total_devuelto += float(producto.get('cantidad', 0))
        
        return total_devuelto
    
    def get_productos_disponibles_devolucion(self):
        """Obtener productos con cantidades disponibles para devolución"""
        items = self.get_items_detalle()
        productos_disponibles = []
        
        for item in items:
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
        """Obtener resumen completo de devoluciones"""
        devoluciones = self.devoluciones.all()
        resumen = {
            'total_devuelto': Decimal('0.00'),
            'productos': {}
        }
        
        for devolucion in devoluciones:
            resumen['total_devuelto'] += devolucion.monto_devuelto
            
            if devolucion.productos_devueltos:
                for producto in devolucion.productos_devueltos:
                    nombre = producto.get('nombre', '')
                    cantidad = float(producto.get('cantidad', 0))
                    
                    if nombre in resumen['productos']:
                        resumen['productos'][nombre] += cantidad
                    else:
                        resumen['productos'][nombre] = cantidad
        
        return resumen
    
    def get_cantidad_items(self):
        """Obtener cantidad total de items"""
        items = self.get_items_detalle()
        return sum(item.get('cantidad', 0) for item in items)
    
    def marcar_como_pagada(self):
        """Marcar la factura como pagada y actualizar el estado del pedido"""
        self.estado = 'pagada'
        self.save()
        
        # Actualizar el estado del pedido a completado
        if self.pedido:
            self.pedido.estado = 'completado'
            self.pedido.save()
    
    def marcar_impresa(self):
        """Marcar la factura como impresa"""
        self.impresa = True
        self.fecha_impresion = timezone.now()
        self.save()
    
    def get_resumen_productos(self):
        """Obtener resumen de productos para depuración"""
        items = self.get_items_detalle()
        resumen = []
        
        for item in items:
            resumen.append({
                'nombre': item.get('nombre', 'Desconocido'),
                'codigo': item.get('codigo', 'Sin código'),
                'cantidad': item.get('cantidad', 0),
                'categoria': item.get('categoria', 'Desconocida')
            })
        
        return resumen
    
    def imprimir_info_depuracion(self):
        """Imprimir información de depuración en consola"""
        print(f"\n{'='*60}")
        print(f"📄 FACTURA: {self.numero_factura}")
        print(f"📦 Items en factura ({len(self.get_items_detalle())}):")
        
        for i, item in enumerate(self.get_items_detalle(), 1):
            print(f"  {i}. {item.get('nombre', 'Sin nombre')}")
            print(f"     Código: '{item.get('codigo', 'Sin código')}'")
            print(f"     Cantidad: {item.get('cantidad', 0)}")
            print(f"     Categoría: '{item.get('categoria', '')}'")
            print(f"     Precio: ${item.get('precio', 0):.2f}")
        
        print(f"{'='*60}\n")
    
    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_factura']

class SalidaProducto(models.Model):
    MOTIVOS = [
        ('venta', 'Venta'),
        ('dano', 'Daño/Desperdicio'),
        ('ajuste', 'Ajuste de Inventario'),
        ('consumo', 'Consumo Interno'),
        ('otro', 'Otro'),
    ]
    
    producto = models.ForeignKey(
        Producto, 
        on_delete=models.CASCADE,
        related_name='salidas'
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Cantidad retirada"
    )
    motivo = models.CharField(
        max_length=50,
        choices=MOTIVOS,
        verbose_name="Motivo de salida"
    )
    responsable = models.CharField(
        max_length=200,
        verbose_name="Responsable"
    )
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones"
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    class Meta:
        verbose_name = "Salida de Producto"
        verbose_name_plural = "Salidas de Productos"
        ordering = ['-fecha_registro']
    
    def __str__(self):
        return f"{self.cantidad} de {self.producto.nombre} - {self.motivo}"



# models.py - Añade este nuevo modelo

class Devolucion(models.Model):
    """Modelo para registrar devoluciones de facturas"""
    
    TIPO_DEVOLUCION_CHOICES = [
        ('total', 'Devolución Total'),
        ('parcial', 'Devolución Parcial'),
        ('cambio', 'Cambio de Producto'),
    ]
    
    factura = models.ForeignKey(
        Factura,
        on_delete=models.CASCADE,
        related_name='devoluciones',
        verbose_name="Factura"
    )
    
    tipo_devolucion = models.CharField(
        max_length=20,
        choices=TIPO_DEVOLUCION_CHOICES,
        verbose_name="Tipo de Devolución"
    )
    
    # Productos devueltos (JSON con detalles)
    productos_devueltos = models.JSONField(
        verbose_name="Productos Devueltos",
        help_text="Lista de productos devueltos con cantidades"
    )
    
    monto_devuelto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monto Devuelto"
    )
    
    motivo = models.TextField(
        blank=True,
        verbose_name="Motivo de la Devolución"
    )
    
    fecha_devolucion = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de Devolución"
    )
    
    procesado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='devoluciones_procesadas',
        verbose_name="Procesado por"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Devolución {self.id} - Factura: {self.factura.numero_factura}"
    
    class Meta:
        verbose_name = "Devolución"
        verbose_name_plural = "Devoluciones"
        ordering = ['-fecha_devolucion']
        
        
        
        
        
        
class Cliente(models.Model):
    cedula = models.CharField(
        max_length=11,
        unique=True,
        verbose_name="Cédula",
        help_text="Debe contener exactamente 11 dígitos"
    )
    nombre_completo = models.CharField(
        max_length=200,
        verbose_name="Nombre Completo"
    )
    direccion = models.TextField(
        verbose_name="Dirección"
    )
    telefono_principal = models.CharField(
        max_length=10,
        verbose_name="Teléfono Principal"
    )
    telefono_alternativo = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Teléfono Alternativo"
    )
    limite_credito = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name="Límite de Crédito"
    )
    dias_credito = models.PositiveIntegerField(
        default=30,
        validators=[MaxValueValidator(365)],
        verbose_name="Días de Crédito"
    )
    notas_credito = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notas sobre Crédito"
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Cliente Activo"
    )

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
        """Verifica si el cliente tiene crédito disponible"""
        return self.limite_credito > 0

    @property
    def venta_contado(self):
        """Verifica si el cliente es solo al contado"""
        return self.dias_credito == 0