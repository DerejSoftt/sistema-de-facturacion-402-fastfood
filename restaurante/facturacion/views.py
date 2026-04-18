from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from decimal import Decimal
from .models import Cliente, CuentaPorCobrar, PagoCuentaCobrar
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from .models import Factura, Pedido, Producto, Plato
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from django.db import models
from django.db.models import Sum, Count, F, Q
from django.http import HttpResponse, JsonResponse
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from django.conf import settings
from django.db.models import Sum, Max, Min
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
import os
import textwrap
import io
import re
from django.db.models import Sum
from django.contrib.auth.models import User
from .models import Pedido, Factura, Mesa, DeliveryConfig, Producto
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from .models import Producto, Plato, Pedido, Mesa, DeliveryConfig, HistorialEstadoPedido, DetalleItemPedido, Factura, Devolucion, DetalleDevolucion, Cliente, PagoCuentaCobrar, CuentaPorCobrar, FacturaDetalle, MovimientoFinanciero, SaldoAFavor
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, Exists, OuterRef
from django.db.models.functions import Coalesce
from django.db.models import DecimalField, IntegerField, DateField
from django.db.models import Case, When, Value
from django.db.models import Func
from django.db.models.functions import TruncDate, Extract, TruncMonth
from functools import lru_cache
from decimal import Decimal
from django.contrib import messages
from datetime import date
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group, Permission
from django.db import transaction, IntegrityError
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.http import HttpResponse
from django.db.models import F
from django.core.cache import cache
import pytz
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from django.db.models import Sum, Count, Q
import io
import os
from datetime import date, time
import uuid
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import datetime


@csrf_exempt
def index(request):
    """
    Vista principal que maneja tanto el login como el dashboard
    """
    def obtener_redireccion_por_rol(usuario):
        if usuario.is_superuser:
            return 'dashbort'

        grupos = set()
        for nombre_grupo in usuario.groups.values_list('name', flat=True):
            nombre = (nombre_grupo or '').strip().lower()
            nombre = (
                nombre
                .replace('á', 'a')
                .replace('é', 'e')
                .replace('í', 'i')
                .replace('ó', 'o')
                .replace('ú', 'u')
            )
            grupos.add(nombre)

        if 'admin' in grupos or 'administrador' in grupos:
            return 'dashbort'

        if 'usuario normal' in grupos or 'usuarionormal' in grupos:
            return 'inventario'

        if 'cajero' in grupos:
            return 'pedidos'

        return 'dashbort'

    if request.user.is_authenticated:
        return redirect(obtener_redireccion_por_rol(request.user))

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember') == 'on'

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)

            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect(obtener_redireccion_por_rol(user))
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')

    return render(request, 'facturacion/index.html')


def logout_view(request):
    """
    Cierra la sesión del usuario y redirige al index (login)
    """
    logout(request)
    messages.success(request, 'Has cerrado sesión correctamente')
    return redirect('index')


def inicializar_permisos():
    """
    Función para inicializar permisos personalizados si no existen
    """
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.auth.models import Permission

    # Usar un content type existente (por ejemplo, del modelo User)
    content_type = ContentType.objects.get_for_model(User)

    permisos_personalizados = [
        ('access_inventario', 'Puede acceder al módulo de inventario'),
        ('access_facturacion', 'Puede acceder al módulo de facturación'),
        ('access_pedidos', 'Puede acceder al módulo de pedidos'),
        ('access_gestion_pedidos', 'Puede acceder al módulo de gestión de pedidos'),
    ]

    for codename, name in permisos_personalizados:
        Permission.objects.get_or_create(
            codename=codename,
            name=name,
            content_type=content_type
        )


@csrf_exempt
def guardar_producto(request):
    """Vista para guardar productos desde el formulario HTML"""
    print("=== RECIBIENDO SOLICITUD ===")

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Método no permitido'
        }, status=405)

    try:
        # Imprimir datos de la solicitud
        print("Headers:", dict(request.headers))
        print("Body raw:", request.body)

        # Obtener datos del formulario
        data = json.loads(request.body) if request.body else {}
        print("Datos recibidos:", data)

        # Validar datos requeridos
        required_fields = ['productName', 'category', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'message': f'Falta el campo: {field}'
                }, status=400)

        # Crear producto
        producto = Producto(
            nombre=data['productName'],
            categoria=data['category'],
            cantidad=float(data['quantity']),
            precio_compra=float(data['price'])
        )

        # Guardar
        producto.save()
        print("Producto guardado en BD:", producto.id, producto.codigo)

        return JsonResponse({
            'success': True,
            'message': 'Producto agregado exitosamente',
            'producto': {
                'id': producto.id,
                'codigo': producto.codigo,
                'nombre': producto.nombre,
                'categoria': producto.categoria,
                'cantidad': str(producto.cantidad),
                'precio_compra': str(producto.precio_compra),
                'subtotal': str(producto.subtotal),
                'fecha': producto.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Error al decodificar JSON'
        }, status=400)

    except Exception as e:
        print("Error detallado:", str(e))
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
def entradadeproductos(request):
    """Vista principal para la entrada de productos"""
    return render(request, 'facturacion/entradadeproductos.html')


@csrf_exempt
def api_tragos(request):
    """API para registrar tragos. Guarda solo nombre, categoria, precio_compra y cantidad (total_tragos)."""
    import json
    from decimal import Decimal
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        nombre = data.get('nombre', '').strip()
        categoria = data.get('categoria', '').strip() or 'trago'
        precio_compra = data.get('precio_compra')
        botellas = int(data.get('botellas', 0))
        ml_botella = int(data.get('ml_botella', 0))
        ml_trago = int(data.get('ml_trago', 0))
        # Validaciones
        if not nombre or not categoria or not precio_compra:
            return JsonResponse({'success': False, 'message': 'Faltan campos obligatorios.'}, status=400)
        if botellas <= 0 or ml_botella <= 0 or ml_trago <= 0:
            return JsonResponse({'success': False, 'message': 'Datos de trago inválidos.'}, status=400)
        # Calcular total de tragos
        total_tragos = (botellas * ml_botella) // ml_trago
        if total_tragos <= 0:
            return JsonResponse({'success': False, 'message': 'El total de tragos debe ser mayor a 0.'}, status=400)
        # Guardar producto
        producto = Producto.objects.create(
            nombre=nombre,
            categoria=categoria,
            cantidad=total_tragos,
            precio_compra=precio_compra
        )
        producto.subtotal = Decimal(
            str(producto.cantidad)) * Decimal(str(producto.precio_compra))
        producto.save()
        return JsonResponse({
            'success': True,
            'message': 'Trago registrado correctamente',
            'producto': {
                'nombre': producto.nombre,
                'categoria': producto.categoria,
                'cantidad': float(producto.cantidad),
                'precio_compra': float(producto.precio_compra),
                'total_tragos': int(producto.cantidad)
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@csrf_exempt
def inventario(request):
    """Vista principal del inventario con filtros - versión simple"""
    # Obtener parámetros de filtrado
    search = request.GET.get('search', '')
    categoria = request.GET.get('categoria', '')
    stock = request.GET.get('stock', '')
    sort_by = request.GET.get('sort', 'nombre')
    page = request.GET.get('page', 1)

    try:
        page = int(page)
    except ValueError:
        page = 1

    # Mapeo de categorías
    CATEGORIAS_LABELS = {
        'bebida': 'Bebida',
        'postre': 'Postre',
        'carne': 'Carne',
        'verdura': 'Verdura',
        'lacteo': 'Lácteo',
        'otro': 'Otro',
    }

    # Mapeo de estados de stock
    STOCK_LABELS = {
        'high': 'Alto',
        'medium': 'Medio',
        'low': 'Bajo'
    }

    STOCK_ICONS = {
        'high': '📈',
        'medium': '📊',
        'low': '📉'
    }

    # Filtrar productos
    productos = Producto.objects.all()

    # Aplicar filtros
    if search:
        productos = productos.filter(
            Q(nombre__icontains=search) |
            Q(codigo__icontains=search)
        )

    if categoria:
        productos = productos.filter(categoria=categoria)

    if stock:
        if stock == 'low':
            productos = productos.filter(cantidad__lt=10)
        elif stock == 'medium':
            productos = productos.filter(cantidad__gte=10, cantidad__lt=50)
        elif stock == 'high':
            productos = productos.filter(cantidad__gte=50)

    # Ordenar
    if sort_by == 'nombre':
        productos = productos.order_by('nombre')
    elif sort_by == 'cantidad':
        productos = productos.order_by('-cantidad')
    elif sort_by == 'precio':
        productos = productos.order_by('-precio_compra')
    elif sort_by == 'categoria':
        productos = productos.order_by('categoria')
    elif sort_by == 'subtotal':
        productos = productos.order_by('-subtotal')
    else:
        productos = productos.order_by('-fecha_creacion')

    # Paginación
    paginator = Paginator(productos, 8)  # 8 productos por página

    try:
        page_obj = paginator.get_page(page)
    except:
        page_obj = paginator.get_page(1)

    # Calcular estadísticas
    total_productos = Producto.objects.count()

    total_valor = 0
    for producto in Producto.objects.all():
        total_valor += float(producto.subtotal)

    bajo_stock = Producto.objects.filter(cantidad__lt=10).count()

    # Obtener categorías únicas
    categorias = Producto.objects.values_list(
        'categoria', flat=True).distinct()
    categorias_count = categorias.count()

    # Preparar datos de productos para la plantilla
    productos_data = []
    for producto in page_obj:
        # Determinar estado de stock
        cantidad = float(producto.cantidad)
        if cantidad >= 50:
            stock_status = 'high'
        elif cantidad >= 10:
            stock_status = 'medium'
        else:
            stock_status = 'low'

        productos_data.append({
            'id': producto.id,
            'codigo': producto.codigo,
            'nombre': producto.nombre,
            'categoria': producto.categoria,
            'categoria_label': CATEGORIAS_LABELS.get(producto.categoria, producto.categoria),
            'cantidad': float(producto.cantidad),
            'precio': float(producto.precio_compra),
            'subtotal': float(producto.subtotal),
            'stock_status': stock_status,
            'stock_label': STOCK_LABELS.get(stock_status, 'Desconocido'),
            'stock_icon': STOCK_ICONS.get(stock_status, '📦'),
            'fecha_creacion': producto.fecha_creacion.strftime('%Y-%m-%d')
        })

    context = {
        'productos': productos_data,
        'page_obj': page_obj,
        'total_productos': total_productos,
        'total_valor': total_valor,
        'bajo_stock': bajo_stock,
        'categorias_count': categorias_count,
        'search': search,
        'categoria_filtro': categoria,
        'stock_filtro': stock,
        'sort_filtro': sort_by,
        'current_page': page,
    }

    return render(request, 'facturacion/inventario.html', context)


@csrf_exempt
def eliminar_producto(request, producto_id):
    """Eliminar un producto"""
    if request.method == 'POST':
        producto = get_object_or_404(Producto, id=producto_id)
        producto.delete()
        return redirect('inventario')

    return redirect('inventario')


@csrf_exempt
def actualizar_cantidad(request, producto_id):
    """Actualizar la cantidad y precio de un producto"""
    if request.method == 'POST':
        producto = get_object_or_404(Producto, id=producto_id)
        nueva_cantidad = request.POST.get('cantidad', 0)
        nuevo_precio = request.POST.get('precio_compra', None)

        try:
            producto.cantidad = Decimal(nueva_cantidad)

            # Actualizar precio si se proporcionó
            if nuevo_precio:
                producto.precio_compra = Decimal(nuevo_precio)
                # Recalcular subtotal
                producto.subtotal = producto.cantidad * producto.precio_compra

            producto.save()
            return redirect('inventario')
        except Exception as e:
            print(f"Error al actualizar producto: {e}")
            pass

    return redirect('inventario')


@csrf_exempt
def entradadeplatillos(request):
    """Vista para mostrar el formulario de entrada de platos"""
    # Obtener el próximo código disponible
    proximo_codigo = Plato.generar_codigo()

    context = {
        'proximo_codigo': proximo_codigo
    }
    return render(request, 'facturacion/entradadeplatillos.html', context)


@csrf_exempt
def guardar_plato(request):
    """Vista para guardar un nuevo plato (acepta AJAX y POST normal)"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            nombre = request.POST.get('nombre', '').strip()
            categoria = request.POST.get('categoria', '')
            precio = request.POST.get('precio', '0')

            # Validaciones básicas
            if not nombre or not categoria:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Nombre y categoría son requeridos'})
                else:
                    messages.error(
                        request, 'Nombre y categoría son requeridos')
                    return redirect('entrada_platos')

            try:
                precio_decimal = float(precio)
                if precio_decimal <= 0:
                    raise ValueError("Precio debe ser mayor a 0")
            except ValueError:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Precio inválido'})
                else:
                    messages.error(request, 'Precio inválido')
                    return redirect('entrada_platos')

            # Crear y guardar el plato (el código se genera automáticamente)
            plato = Plato(
                nombre=nombre,
                categoria=categoria,
                precio=precio_decimal
            )
            plato.save()

            # Obtener el próximo código para la vista
            proximo_codigo = Plato.generar_codigo()

            # Responder según el tipo de petición
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Plato "{nombre}" guardado exitosamente',
                    'plato_id': plato.id,
                    'codigo_asignado': plato.codigo,
                    'proximo_codigo': proximo_codigo
                })
            else:
                messages.success(
                    request, f'Plato "{nombre}" (Código: {plato.codigo}) guardado exitosamente')
                return redirect('entrada_platos')

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            else:
                messages.error(request, f'Error al guardar: {str(e)}')
                return redirect('entrada_platos')

    # Si no es POST, redirigir
    return redirect('entrada_platos')


@csrf_exempt
def listadeplatillos(request):
    """Vista para mostrar la lista de platos"""
    # Obtener todos los platos activos ordenados por código
    platos = Plato.objects.filter(activo=True).order_by('codigo')

    # Calcular estadísticas
    total_platos = platos.count()

    if total_platos > 0:
        precio_promedio = sum(p.precio for p in platos) / total_platos
        categorias = platos.values_list(
            'categoria', flat=True).distinct().count()
        hoy = date.today()
        platos_hoy = platos.filter(fecha_creacion__date=hoy).count()
    else:
        precio_promedio = 0
        categorias = 0
        platos_hoy = 0

    context = {
        'platos': platos,
        'total_platos': total_platos,
        'precio_promedio': precio_promedio,
        'categorias': categorias,
        'platos_hoy': platos_hoy,
    }
    return render(request, 'facturacion/listadeplatillos.html', context)


@csrf_exempt
def eliminar_plato(request, plato_id):
    """Vista para eliminar un plato (acepta AJAX)"""
    if request.method == 'DELETE':
        try:
            plato = get_object_or_404(Plato, id=plato_id)
            # Cambiar estado a inactivo en lugar de eliminar
            plato.activo = False
            plato.save()

            return JsonResponse({
                'success': True,
                'message': f'Plato "{plato.nombre}" eliminado exitosamente'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@csrf_exempt
def obtener_plato(request, plato_id):
    """Vista para obtener datos de un plato específico"""
    if request.method == 'GET':
        try:
            plato = Plato.objects.get(id=plato_id)

            return JsonResponse({
                'success': True,
                'plato': {
                    'id': plato.id,
                    'codigo': plato.codigo,
                    'nombre': plato.nombre,
                    'categoria': plato.categoria,
                    'precio': float(plato.precio),
                    'fecha_creacion': plato.fecha_creacion.strftime('%Y-%m-%d'),
                    'activo': plato.activo
                }
            })
        except Plato.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Plato no encontrado'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@csrf_exempt
def actualizar_plato(request, plato_id):
    """Vista para actualizar un plato"""
    if request.method in ['POST', 'PUT']:
        try:
            plato = Plato.objects.get(id=plato_id)

            # Parsear datos según el método
            if request.method == 'POST':
                # Datos desde formulario POST
                data = {
                    'nombre': request.POST.get('nombre'),
                    'categoria': request.POST.get('categoria'),
                    'precio': request.POST.get('precio')
                }
            else:
                # Datos JSON desde PUT
                data = json.loads(request.body)

            # Actualizar campos
            if 'nombre' in data and data['nombre']:
                plato.nombre = data['nombre'].strip()

            if 'categoria' in data and data['categoria']:
                plato.categoria = data['categoria']

            if 'precio' in data and data['precio']:
                try:
                    precio = float(data['precio'])
                    if precio >= 0:
                        plato.precio = precio
                    else:
                        return JsonResponse({'success': False, 'error': 'El precio debe ser mayor o igual a 0'})
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': 'Precio inválido'})

            plato.save()

            # Si es POST, redirigir a la lista de platos
            if request.method == 'POST':
                from django.shortcuts import redirect
                return redirect('listadeplatillos')

            # Si es PUT, devolver JSON
            return JsonResponse({
                'success': True,
                'message': f'Plato "{plato.nombre}" actualizado exitosamente',
                'plato': {
                    'id': plato.id,
                    'codigo': plato.codigo,
                    'nombre': plato.nombre,
                    'categoria': plato.categoria,
                    'precio': float(plato.precio)
                }
            })
        except Plato.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Plato no encontrado'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@csrf_exempt
def pedidos(request):
    """Vista principal para realizar pedidos - BEBIDAS de Producto y PLATOS de Plato"""

    try:
        # Obtener mesas disponibles
        mesas = Mesa.objects.all().order_by('numero')

        # Actualizar estado de mesas según pedidos activos
        pedidos_activos = Pedido.objects.filter(
            tipo_pedido='mesa',
            estado__in=['pendiente', 'confirmado',
                        'preparacion', 'listo', 'entregado']
        ).select_related('mesa')

        mesas_ocupadas_activas = set()
        for pedido in pedidos_activos:
            if pedido.mesa:
                mesas_ocupadas_activas.add(pedido.mesa.id)

        for mesa in mesas:
            if mesa.id in mesas_ocupadas_activas:
                if mesa.estado != 'ocupada':
                    mesa.estado = 'ocupada'
                    mesa.save()
            else:
                if mesa.estado != 'disponible':  # ¡CORREGIDO: Quité el paréntesis extra!
                    mesa.estado = 'disponible'
                    mesa.save()

        # Crear códigos si no existen
        if not DeliveryConfig.objects.filter(tipo='delivery').exists():
            for i in range(1, 11):
                DeliveryConfig.objects.create(
                    codigo=f'D{i:03d}',
                    tipo='delivery',
                    estado='disponible'
                )

        if not DeliveryConfig.objects.filter(tipo='llevar').exists():
            for i in range(1, 11):
                DeliveryConfig.objects.create(
                    codigo=f'L{i:03d}',
                    tipo='llevar',
                    estado='disponible'
                )

        # Obtener códigos disponibles
        delivery_codes = DeliveryConfig.objects.filter(
            tipo='delivery',
            estado='disponible'
        ).order_by('codigo')

        llevar_codes = DeliveryConfig.objects.filter(
            tipo='llevar',
            estado='disponible'
        ).order_by('codigo')

        # 🔥 **BEBIDAS DE PRODUCTO**
        bebidas = Producto.objects.filter(
            categoria__in=['bebida', 'trago'],
            cantidad__gt=0  # Solo bebidas con stock
        ).order_by('nombre')

        # Convertir bebidas a formato JSON para el frontend
        bebidas_json = []
        for bebida in bebidas:
            bebidas_json.append({
                'id': f"bebida_{bebida.id}",  # 🔥 AGREGAR PREFIJO
                'codigo': bebida.codigo,
                'nombre': bebida.nombre,
                'categoria': 'bebida',  # Siempre será 'bebida'
                'precio': float(bebida.precio_compra),
                'tiempoPreparacion': 5,  # Menos tiempo que los platos
                'descripcion': f"Bebida: {bebida.nombre}",
                'popularidad': 'alta' if float(bebida.cantidad) > 20 else 'media',
                'disponibilidad': 'disponible' if float(bebida.cantidad) > 0 else 'agotado',
                'stock': float(bebida.cantidad),
                'tipo': 'bebida',  # Flag para identificar que es una bebida
                'es_bebida': True,
                'categoria_display': bebida.get_category_label(),
                'precio_formateado': f"${float(bebida.precio_compra):.2f}"
            })

        # 🔥 **PLATOS DE LA TABLA PLATO**
        platos = Plato.objects.filter(activo=True).order_by('nombre')

        # Convertir platos a formato JSON para el frontend
        platos_json = []
        for plato in platos:
            # Para los platos, el tiempo de preparación puede ser un campo fijo o podemos calcularlo
            # En este caso, como no tenemos un campo, usamos un valor por defecto
            tiempo_preparacion = 15  # minutos por defecto para platos
            if plato.categoria == 'entrada':
                tiempo_preparacion = 10
            elif plato.categoria == 'postre':
                tiempo_preparacion = 5
            elif plato.categoria == 'bebida':
                tiempo_preparacion = 5
            elif plato.categoria == 'rapida':
                tiempo_preparacion = 10
            elif plato.categoria == 'especial':
                tiempo_preparacion = 20

            platos_json.append({
                'id': f"plato_{plato.id}",  # 🔥 AGREGAR PREFIJO
                'codigo': plato.codigo,
                'nombre': plato.nombre,
                'categoria': plato.categoria,
                'precio': float(plato.precio),
                'tiempoPreparacion': tiempo_preparacion,
                'descripcion': f"Plato: {plato.nombre}",
                'popularidad': 'alta',  # Podemos ajustar esto si hay un campo en el modelo
                # Asumimos que todos los platos activos están disponibles
                'disponibilidad': 'disponible',
                'stock': 0,  # Los platos no tienen stock, se preparan al momento
                'tipo': 'plato',  # Flag para identificar que es un plato
                'es_bebida': False,
                'categoria_display': plato.get_categoria_display(),
                'precio_formateado': f"${float(plato.precio):.2f}"
            })

        context = {
            'mesas': mesas,
            'delivery_codes': delivery_codes,
            'llevar_codes': llevar_codes,
            'bebidas_json': json.dumps(bebidas_json),  # Solo bebidas
            'platos_json': json.dumps(platos_json),    # Solo platos
            'clientes_credito_json': json.dumps([
                {
                    'id': cliente.id,
                    'nombre': cliente.nombre_completo,
                    'cedula': cliente.cedula,
                    'telefono': cliente.telefono_principal,
                    'limite_credito': float(cliente.limite_credito or 0),
                    'dias_credito': int(cliente.dias_credito or 0),
                }
                for cliente in Cliente.objects.filter(activo=True).order_by('nombre_completo')
            ]),
            'total_bebidas': bebidas.count(),
            'total_platos': platos.count(),
            'title': 'Realizar Pedido',
        }

        return render(request, 'facturacion/pedidos.html', context)

    except Exception as e:
        print(f"ERROR en vista pedidos: {str(e)}")
        import traceback
        traceback.print_exc()

        context = {
            'mesas': [],
            'delivery_codes': [],
            'llevar_codes': [],
            'bebidas_json': '[]',
            'platos_json': '[]',
            'clientes_credito_json': '[]',
            'total_bebidas': 0,
            'total_platos': 0,
            'title': 'Realizar Pedido',
        }
        return render(request, 'facturacion/pedidos.html', context)


def crear_pedido(request):
    """Vista para crear un nuevo pedido. Solo staff autenticado puede crear pedidos a crédito."""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario con valores por defecto
            tipo_pedido = request.POST.get('tipo_pedido')
            cart_items_json = request.POST.get('cart_items')
            tipo_pago = (request.POST.get('tipo_pago', 'contado')
                         or 'contado').strip().lower()
            cliente_credito_id = (request.POST.get(
                'cliente_credito_id', '') or '').strip()
            cliente_credito = None

            if tipo_pago not in ['contado', 'credito']:
                tipo_pago = 'contado'

            # RESTRICCIÓN DE SEGURIDAD: Solo staff autenticado puede crear pedidos a crédito
            if tipo_pago == 'credito':
                if not request.user.is_authenticated or not request.user.is_staff:
                    messages.error(
                        request, 'Solo personal autorizado puede crear pedidos a crédito. Inicie sesión como staff.')
                    return redirect('pedidos')
                if not cliente_credito_id:
                    messages.error(
                        request, 'Para venta a crédito debes seleccionar un cliente')
                    return redirect('pedidos')
                try:
                    cliente_credito = Cliente.objects.get(
                        id=cliente_credito_id, activo=True)
                except Cliente.DoesNotExist:
                    messages.error(
                        request, 'El cliente seleccionado para crédito no es válido')
                    return redirect('pedidos')

            print("=" * 80)
            print("CART ITEMS JSON RECIBIDO:")
            print(cart_items_json)
            print("=" * 80)

            # 🔥 Convertir valores numéricos a Decimal (no float)
            try:
                subtotal = Decimal(str(request.POST.get('subtotal', 0) or 0))
                envio = Decimal(str(request.POST.get('envio', 0) or 0))
                total = Decimal(str(request.POST.get('total', 0) or 0))
            except (ValueError, TypeError):
                subtotal = envio = total = Decimal('0.00')

            # Validar datos requeridos
            if not cart_items_json:
                messages.error(request, 'El carrito está vacío')
                return redirect('pedidos')

            # Parsear items del carrito
            try:
                cart_items = json.loads(cart_items_json)
            except json.JSONDecodeError as e:
                print(f"ERROR parseando JSON: {e}")
                messages.error(
                    request, 'Error al procesar los items del carrito')
                return redirect('pedidos')

            if not cart_items:
                messages.error(request, 'El carrito está vacío')
                return redirect('pedidos')

            print("=" * 80)
            print("ITEMS EN EL CARRITO (PARSED):")
            for idx, item in enumerate(cart_items):
                print(f"  [{idx}] {item.get('name')} (ID: {item.get('id')}, Tipo: {item.get('tipo')}, es_bebida: {item.get('es_bebida')}, Quantity: {item.get('quantity')})")
            print("=" * 80)

            # 🔥 VALIDAR Y DESCONTAR STOCK DE BEBIDAS ANTES DE CREAR EL PEDIDO
            print("=" * 60)
            print("DESCONTANDO STOCK DE BEBIDAS:")
            print("=" * 60)

            bebidas_sin_stock = []
            bebidas_descontadas = []

            for item in cart_items:
                # Verificar si es una bebida
                es_bebida = item.get('tipo') == 'bebida' or item.get(
                    'es_bebida', False)

                if not es_bebida:
                    continue  # Saltar si no es bebida

                # Extraer información del item
                item_id = item.get('id', '')
                nombre_bebida = item.get('name', 'Bebida sin nombre')
                cantidad_solicitada = int(item.get('quantity', 1))

                print(f"\n[Procesando] {nombre_bebida}")
                print(f"  - ID original: {item_id}")
                print(f"  - Cantidad solicitada: {cantidad_solicitada}")

                # 🔥 FUNCIÓN PARA EXTRAER ID REAL
                def extraer_id_bebida(item_id_str):
                    """Extrae el ID numérico del string con prefijo 'bebida_'"""
                    if isinstance(item_id_str, (int, float)):
                        return int(item_id_str)

                    item_id_str = str(item_id_str)

                    # Caso 1: Tiene prefijo "bebida_"
                    if item_id_str.startswith('bebida_'):
                        try:
                            return int(item_id_str.replace('bebida_', ''))
                        except ValueError:
                            return None

                    # Caso 2: Tiene prefijo "PROD-" (viene de Producto)
                    if item_id_str.startswith('PROD-'):
                        try:
                            # Extraer solo el número después de "PROD-"
                            partes = item_id_str.split('-')
                            if len(partes) >= 2:
                                return int(partes[1])
                        except (ValueError, IndexError):
                            return None

                    # Caso 3: Es solo un número
                    try:
                        return int(item_id_str)
                    except ValueError:
                        # Intentar extraer números del string
                        import re
                        numeros = re.findall(r'\d+', item_id_str)
                        if numeros:
                            return int(numeros[0])
                        return None

                # Extraer ID de la bebida
                bebida_id = extraer_id_bebida(item_id)

                if not bebida_id:
                    error_msg = f'❌ ID inválido para {nombre_bebida}: {item_id}'
                    bebidas_sin_stock.append(error_msg)
                    print(f"  {error_msg}")
                    continue

                print(f"  - ID extraído: {bebida_id}")

                # Buscar la bebida en Producto
                try:
                    bebida = Producto.objects.get(
                        id=bebida_id, categoria='bebida')

                    # 🔥 DEBUG: Mostrar información de la bebida encontrada
                    print(f"  - Bebida encontrada: {bebida.nombre}")
                    print(f"  - Stock actual: {bebida.cantidad}")
                    print(f"  - Precio: ${bebida.precio_compra}")

                    # Verificar si hay suficiente stock
                    stock_disponible = bebida.cantidad
                    if stock_disponible < cantidad_solicitada:
                        error_msg = f'❌ No hay suficiente stock de {bebida.nombre}. Disponible: {stock_disponible}, Solicitado: {cantidad_solicitada}'
                        bebidas_sin_stock.append(error_msg)
                        print(f"  {error_msg}")
                        continue

                    # 🔥 DESCONTAR EL STOCK
                    stock_anterior = bebida.cantidad
                    bebida.cantidad = stock_disponible - \
                        Decimal(str(cantidad_solicitada))

                    # Recalcular subtotal del producto
                    bebida.subtotal = bebida.cantidad * bebida.precio_compra

                    # Guardar cambios
                    bebida.save()

                    # Registrar bebida descontada
                    bebidas_descontadas.append({
                        'id': bebida.id,
                        'nombre': bebida.nombre,
                        'cantidad': cantidad_solicitada,
                        'stock_anterior': float(stock_anterior),
                        'stock_nuevo': float(bebida.cantidad)
                    })

                    print(
                        f"  ✅ Stock descontado: {cantidad_solicitada} unidad(es)")
                    print(f"  ✅ Stock anterior: {stock_anterior}")
                    print(f"  ✅ Stock nuevo: {bebida.cantidad}")

                except Producto.DoesNotExist:
                    # Buscar por código alternativo
                    try:
                        # Intentar buscar por nombre o código
                        codigo_bebida = item.get('codigo', '')
                        if codigo_bebida:
                            bebida = Producto.objects.get(
                                codigo=codigo_bebida, categoria='bebida')

                            print(
                                f"  - Bebida encontrada por código: {bebida.nombre} ({codigo_bebida})")
                            print(f"  - Stock actual: {bebida.cantidad}")

                            # Verificar stock
                            stock_disponible = bebida.cantidad
                            if stock_disponible < cantidad_solicitada:
                                error_msg = f'❌ No hay suficiente stock de {bebida.nombre}. Disponible: {stock_disponible}, Solicitado: {cantidad_solicitada}'
                                bebidas_sin_stock.append(error_msg)
                                print(f"  {error_msg}")
                                continue

                            # Descontar stock
                            stock_anterior = bebida.cantidad
                            bebida.cantidad = stock_disponible - \
                                Decimal(str(cantidad_solicitada))
                            bebida.subtotal = bebida.cantidad * bebida.precio_compra
                            bebida.save()

                            bebidas_descontadas.append({
                                'id': bebida.id,
                                'nombre': bebida.nombre,
                                'cantidad': cantidad_solicitada,
                                'stock_anterior': float(stock_anterior),
                                'stock_nuevo': float(bebida.cantidad)
                            })

                            print(
                                f"  ✅ Stock descontado: {cantidad_solicitada} unidad(es)")
                            print(f"  ✅ Stock nuevo: {bebida.cantidad}")

                        else:
                            error_msg = f'❌ La bebida "{nombre_bebida}" no existe en la base de datos'
                            bebidas_sin_stock.append(error_msg)
                            print(f"  {error_msg}")

                    except Producto.DoesNotExist:
                        error_msg = f'❌ La bebida "{nombre_bebida}" no existe en la base de datos (ID: {bebida_id})'
                        bebidas_sin_stock.append(error_msg)
                        print(f"  {error_msg}")
                    except Exception as e:
                        error_msg = f'❌ Error al buscar bebida: {str(e)}'
                        bebidas_sin_stock.append(error_msg)
                        print(f"  {error_msg}")

            # 🔥 RESUMEN DEL DESCUENTO
            print("\n" + "=" * 60)
            print("RESUMEN DEL DESCUENTO DE BEBIDAS:")
            print("=" * 60)

            if bebidas_descontadas:
                print(f"✅ Bebidas descontadas: {len(bebidas_descontadas)}")
                for b in bebidas_descontadas:
                    print(
                        f"  - {b['nombre']}: {b['cantidad']} unidad(es) | Stock: {b['stock_anterior']} → {b['stock_nuevo']}")
            else:
                print("ℹ️ No se descontaron bebidas")

            if bebidas_sin_stock:
                print(f"⚠️ Bebidas sin stock: {len(bebidas_sin_stock)}")
                for error in bebidas_sin_stock:
                    print(f"  {error}")
            print("=" * 60)

            # Si hay bebidas sin stock, mostrar error y cancelar el pedido
            if bebidas_sin_stock:
                for error in bebidas_sin_stock:
                    messages.error(request, error)
                return redirect('pedidos')

            # 🔥🔥🔥 CAMBIO PRINCIPAL: Crear el pedido con estado 'pendiente'
            pedido = Pedido(
                tipo_pedido=tipo_pedido,
                items=cart_items,
                subtotal=subtotal,
                envio=envio,
                total=total,
                estado='pendiente',  # 🔥 CAMBIADO A 'pendiente'
            )

            # Asignar información según tipo de pedido
            if tipo_pedido == 'mesa':
                mesa_id = request.POST.get('mesa_id')
                if not mesa_id:
                    messages.error(request, 'Se requiere seleccionar una mesa')
                    return redirect('pedidos')

                try:
                    mesa = Mesa.objects.get(id=mesa_id)
                except Mesa.DoesNotExist:
                    messages.error(request, 'La mesa seleccionada no existe')
                    return redirect('pedidos')

                pedido.mesa = mesa
                pedido.nombre_cliente = f"Mesa {mesa.numero_display}"

                # 🔥🔥🔥 IMPORTANTE: OCUPAR LA MESA CUANDO SE CREA EL PEDIDO
                mesa.estado = 'ocupada'
                mesa.save()
                print(f"✅ Mesa {mesa.numero_display} ocupada por el pedido")

            elif tipo_pedido == 'delivery':
                codigo_delivery = request.POST.get('codigo_delivery')
                if not codigo_delivery:
                    messages.error(request, 'Se requiere código de delivery')
                    return redirect('pedidos')

                pedido.codigo_delivery = codigo_delivery

                nombre_cliente = request.POST.get('customer_name', '').strip()
                telefono_cliente = request.POST.get(
                    'customer_phone', '').strip()
                direccion_entrega = request.POST.get(
                    'customer_address', '').strip()

                if not nombre_cliente:
                    nombre_cliente = f"Cliente Delivery {codigo_delivery}"
                if not telefono_cliente:
                    telefono_cliente = "No especificado"
                if not direccion_entrega:
                    direccion_entrega = "Dirección no especificada"

                pedido.nombre_cliente = nombre_cliente
                pedido.telefono_cliente = telefono_cliente
                pedido.direccion_entrega = direccion_entrega

                # 🔥 OCUPAR código de delivery
                try:
                    delivery_config = DeliveryConfig.objects.get(
                        tipo='delivery',
                        codigo=codigo_delivery
                    )
                    delivery_config.estado = 'ocupado'
                    delivery_config.save()
                    print(f"✅ Código delivery {codigo_delivery} ocupado")
                except DeliveryConfig.DoesNotExist:
                    print(
                        f"⚠️ Código delivery {codigo_delivery} no encontrado")

            elif tipo_pedido == 'llevar':
                codigo_llevar = request.POST.get('codigo_llevar')
                if not codigo_llevar:
                    messages.error(request, 'Se requiere código para llevar')
                    return redirect('pedidos')

                pedido.codigo_delivery = codigo_llevar

                nombre_cliente = request.POST.get(
                    'customer_name_takeaway', '').strip()
                if not nombre_cliente:
                    nombre_cliente = f"Cliente Para Llevar {codigo_llevar}"

                pedido.nombre_cliente = nombre_cliente

                # 🔥 OCUPAR código para llevar
                try:
                    llevar_config = DeliveryConfig.objects.get(
                        tipo='llevar',
                        codigo=codigo_llevar
                    )
                    llevar_config.estado = 'ocupado'
                    llevar_config.save()
                    print(f"✅ Código para llevar {codigo_llevar} ocupado")
                except DeliveryConfig.DoesNotExist:
                    print(
                        f"⚠️ Código para llevar {codigo_llevar} no encontrado")
            else:
                messages.error(request, 'Tipo de pedido no válido')
                return redirect('pedidos')

            # Persistir metadatos de pago para usarlos al facturar/CxC.
            if tipo_pago == 'credito' and cliente_credito:
                pedido.nombre_cliente = cliente_credito.nombre_completo
                pedido.telefono_cliente = cliente_credito.telefono_principal or pedido.telefono_cliente
                pedido.notas = f"TIPO_PAGO_PEDIDO=credito;CLIENTE_CREDITO_ID={cliente_credito.id}"
            else:
                pedido.notas = "TIPO_PAGO_PEDIDO=contado"

            # Guardar el pedido (esto generará automáticamente el código_pedido)
            pedido.save()
            print(
                f"✅ Pedido {pedido.codigo_pedido} creado con ID: {pedido.id} y estado PENDIENTE")

            # 🔥 SOLUCIÓN: Crear DetalleItemPedido con IDs extraídos correctamente
            try:
                print("Creando DetalleItemPedido...")
                for item in cart_items:
                    # 🔥 FUNCIÓN PARA EXTRAER ID REAL
                    def extraer_id_real(item_id_str):
                        """Extrae el ID numérico del string con prefijo"""
                        if isinstance(item_id_str, (int, float)):
                            return int(item_id_str)

                        item_id_str = str(item_id_str)

                        # Remover prefijos conocidos
                        if item_id_str.startswith('bebida_'):
                            return int(item_id_str.replace('bebida_', ''))
                        elif item_id_str.startswith('plato_'):
                            return int(item_id_str.replace('plato_', ''))
                        else:
                            # Intentar convertir directamente
                            try:
                                return int(item_id_str)
                            except ValueError:
                                # Si falla, intentar extraer números
                                import re
                                numeros = re.findall(r'\d+', item_id_str)
                                if numeros:
                                    return int(numeros[0])
                                return 0

                    # Extraer datos del item
                    item_id_original = item.get('id', '')
                    id_real = extraer_id_real(item_id_original)

                    tipo_item = item.get('tipo', 'plato')
                    es_bebida = item.get('es_bebida', False)

                    # Si es_bebida es True pero tipo no está definido, corregir
                    if es_bebida and tipo_item != 'bebida':
                        tipo_item = 'bebida'

                    nombre_plato = item.get(
                        'name', item.get('nombre', 'Sin nombre'))
                    cantidad = int(item.get('quantity', 1))
                    # 🔥 Convertir a Decimal en lugar de float
                    precio_unitario = Decimal(
                        str(item.get('price', item.get('precio', 0))))
                    subtotal_item = Decimal(str(item.get('total', 0)))

                    # Si no hay subtotal, calcularlo
                    if subtotal_item == 0:
                        subtotal_item = precio_unitario * cantidad

                    codigo_item = item.get('codigo', 'N/A')

                    print(f"  - Creando detalle:")
                    print(f"    ID original: {item_id_original}")
                    print(f"    ID extraído: {id_real}")
                    print(f"    Nombre: {nombre_plato}")
                    print(f"    Tipo: {tipo_item}")
                    print(f"    Cantidad: {cantidad}")
                    print(f"    Precio unitario: ${precio_unitario}")
                    print(f"    Subtotal: ${subtotal_item}")

                    # Validar que id_real sea válido
                    if id_real <= 0:
                        print(
                            f"    ⚠️ ADVERTENCIA: ID inválido para {nombre_plato}, usando 0")

                    # Crear el detalle
                    DetalleItemPedido.objects.create(
                        pedido=pedido,
                        id_plato=id_real,
                        nombre_plato=nombre_plato,
                        cantidad=cantidad,
                        precio_unitario=precio_unitario,
                        subtotal_item=subtotal_item,
                        tipo_item=tipo_item,
                        notas=f"Código: {codigo_item}"
                    )
                    print(f"    ✅ Detalle creado exitosamente")

                print("✅ Todos los detalles del pedido creados exitosamente")
            except Exception as e:
                print(f"⚠️ Error creando detalles del pedido: {e}")
                import traceback
                traceback.print_exc()
                # No interrumpimos el flujo principal por este error

            # 🔥 GENERAR TICKET DEL SERVIDOR Y DEVOLVERLO DIRECTAMENTE
            # Determinar código según tipo
            codigo_display = ""
            if pedido.tipo_pedido == 'mesa' and pedido.mesa:
                codigo_display = f"M{pedido.mesa.numero_display}"
            elif pedido.codigo_delivery:
                codigo_display = pedido.codigo_delivery

            # Separar platos y bebidas
            platos_items = [item for item in cart_items if item.get(
                'tipo') != 'bebida' and not item.get('es_bebida')]
            bebidas_items = [item for item in cart_items if item.get(
                'tipo') == 'bebida' or item.get('es_bebida')]

            # Crear contexto para el ticket
            context = {
                'pedido': pedido,
                'items': cart_items,
                'platos_items': platos_items,
                'bebidas_items': bebidas_items,
                'fecha': now().strftime('%d/%m/%Y %H:%M'),
                'codigo_display': codigo_display,
                'codigo_pedido': pedido.codigo_pedido,
                'total_items': len(cart_items),
                'platos_count': len(platos_items),
                'bebidas_count': len(bebidas_items),
                'tiempo_estimado': sum(item.get('prepTime', 15) for item in cart_items),
            }

            # Renderizar el template del ticket
            ticket_html = render_to_string(
                'facturacion/ticket_chef.html', context)

            # DEBUG: Mostrar información del ticket generado
            print("=" * 80)
            print("TICKET GENERADO:")
            print(f"Código Pedido: {pedido.codigo_pedido}")
            print(f"Estado: PENDIENTE (mesa ocupada)")
            print(f"Código Display: {codigo_display}")
            print(f"Total Items: {len(cart_items)}")
            print(f"Platos: {len(platos_items)}")
            print(f"Bebidas: {len(bebidas_items)}")
            print("=" * 80)

            # 🔥 DEVOLVER EL TICKET HTML DIRECTAMENTE
            return HttpResponse(ticket_html)

        except Exception as e:
            import traceback
            print("=" * 80)
            print("ERROR EN crear_pedido:")
            traceback.print_exc()
            print("=" * 80)
            messages.error(request, f'❌ Error al crear el pedido: {str(e)}')
            return redirect('pedidos')

    return redirect('pedidos')


@csrf_exempt
def generar_ticket_chef_servidor(pedido, cart_items):
    """Función para generar ticket del chef desde el servidor"""
    try:
        from django.template.loader import render_to_string
        from django.utils.timezone import now

        # Determinar código según tipo
        codigo_display = ""
        if pedido.tipo_pedido == 'mesa' and pedido.mesa:
            codigo_display = f"M{pedido.mesa.numero_display}"
        elif pedido.codigo_delivery:
            codigo_display = pedido.codigo_delivery

        # Separar platos y bebidas
        platos_items = [item for item in cart_items if item.get(
            'tipo') != 'bebida' and not item.get('es_bebida')]
        bebidas_items = [item for item in cart_items if item.get(
            'tipo') == 'bebida' or item.get('es_bebida')]

        context = {
            'pedido': pedido,
            'items': cart_items,
            'platos_items': platos_items,
            'bebidas_items': bebidas_items,
            'fecha': now().strftime('%d/%m/%Y %H:%M'),
            'codigo_display': codigo_display,
            'codigo_pedido': pedido.codigo_pedido,  # 🔥 AGREGAR ESTO
            'total_items': len(cart_items),
            'platos_count': len(platos_items),
            'bebidas_count': len(bebidas_items),
            'tiempo_estimado': sum(item.get('prepTime', 15) for item in cart_items),
        }

        ticket_html = render_to_string('facturacion/ticket_chef.html', context)

        print("=" * 50)
        print("TICKET COCINA GENERADO")
        print(f"Código Pedido: {pedido.codigo_pedido}")
        print(f"Código Display: {codigo_display}")
        print(f"Fecha: {context['fecha']}")
        print(f"Items totales: {len(cart_items)}")
        print(f"  - Platos: {len(platos_items)}")
        print(f"  - Bebidas: {len(bebidas_items)}")
        print("=" * 50)

        return ticket_html  # 🔥 RETORNAR EL HTML

    except Exception as e:
        print(f"Error generando ticket del chef: {e}")
        return None


@csrf_exempt
def limpiar_carrito(request):
    """Vista para limpiar el carrito (opcional)"""
    # En una aplicación real, esto limpiaría el carrito de la sesión
    # request.session['cart'] = []

    messages.success(request, 'Carrito limpiado exitosamente')
    return redirect('pedidos')


@csrf_exempt
def gestiondepedidos(request):
    """Vista principal de gestión de pedidos - EXCLUYE PEDIDOS FACTURADOS"""
    # Obtener parámetros de filtrado
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    tipo_pedido = request.GET.get('tipo', '')
    fecha = request.GET.get('fecha', '')
    sort_by = request.GET.get('sort', '-fecha_pedido')
    page = request.GET.get('page', 1)

    # Construir query base - EXCLUIR PEDIDOS CON FACTURAS ACTIVAS
    from django.db.models import Q, Exists, OuterRef

    # Subconsulta para verificar si el pedido tiene factura activa.
    # Solo volvemos a mostrar pedidos con factura anulada.
    facturas_activas = Factura.objects.filter(
        pedido_id=OuterRef('pk'),
    ).exclude(
        estado='anulada'
    )

    # Consulta principal: todos los pedidos que NO tienen facturas activas
    # Usamos un nombre diferente para la anotación para evitar conflicto con la propiedad
    pedidos = Pedido.objects.annotate(
        factura_activa_annotated=Exists(facturas_activas)
    ).filter(
        factura_activa_annotated=False
    ).select_related('mesa').order_by('-fecha_pedido')

    # Si no se especifica estado, excluir cancelados por defecto
    if not estado:
        pedidos = pedidos.exclude(estado='cancelado')

    # Aplicar filtros
    if search:
        pedidos = pedidos.filter(
            Q(codigo_pedido__icontains=search) |
            Q(nombre_cliente__icontains=search) |
            Q(telefono_cliente__icontains=search) |
            Q(codigo_delivery__icontains=search) |
            Q(mesa__numero__icontains=search) |
            Q(mesa__numero_display__icontains=search)
        )

    if estado:
        pedidos = pedidos.filter(estado=estado)

    if tipo_pedido:
        pedidos = pedidos.filter(tipo_pedido=tipo_pedido)

    if fecha:
        today = timezone.localdate()
        if fecha == 'hoy':
            pedidos = pedidos.filter(fecha_pedido__date=today)
        elif fecha == 'ayer':
            yesterday = today - timedelta(days=1)
            pedidos = pedidos.filter(fecha_pedido__date=yesterday)
        elif fecha == 'semana':
            week_ago = today - timedelta(days=7)
            pedidos = pedidos.filter(fecha_pedido__date__gte=week_ago)
        elif fecha == 'mes':
            month_ago = today - timedelta(days=30)
            pedidos = pedidos.filter(fecha_pedido__date__gte=month_ago)

    # Aplicar ordenamiento
    sort_map = {
        'fecha_desc': '-fecha_pedido',
        'fecha_asc': 'fecha_pedido',
        'total_desc': '-total',
        'total_asc': 'total',
        'cliente': 'nombre_cliente'
    }
    sort_field = sort_map.get(sort_by, '-fecha_pedido')
    pedidos = pedidos.order_by(sort_field)

    # 🔥 ACTUALIZAR ESTADO DE MESAS SEGÚN PEDIDOS ACTIVOS
    # Solo para pedidos que no tienen facturas activas
    pedidos_activos = Pedido.objects.annotate(
        factura_activa_annotated=Exists(facturas_activas)
    ).filter(
        factura_activa_annotated=False,
        tipo_pedido='mesa',
        estado__in=['pendiente', 'confirmado',
                    'preparacion', 'listo', 'entregado']
    ).select_related('mesa')

    for pedido in pedidos_activos:
        if pedido.mesa and pedido.mesa.estado != 'ocupada':
            pedido.mesa.estado = 'ocupada'
            pedido.mesa.save()
            print(
                f"✅ Mesa {pedido.mesa.numero_display} actualizada a OCUPADA por pedido activo (sin factura pagada)")

    # Paginación
    paginator = Paginator(pedidos, 10)
    page_obj = paginator.get_page(page)

    # Procesar pedidos para template
    pedidos_procesados = procesar_pedidos_para_template(page_obj)

    # Calcular estadísticas SOLO de pedidos NO pagados
    ahora_local = timezone.localtime()
    inicio_dia = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_dia = inicio_dia + timedelta(days=1)

    # Total de pedidos activos (sin factura activa)
    total_pedidos_activos = Pedido.objects.annotate(
        factura_activa_annotated=Exists(facturas_activas)
    ).filter(
        factura_activa_annotated=False
    ).exclude(
        estado='cancelado'
    ).count()

    # Pedidos pendientes (sin factura activa)
    pedidos_pendientes_count = Pedido.objects.annotate(
        factura_activa_annotated=Exists(facturas_activas)
    ).filter(
        factura_activa_annotated=False,
        estado__in=['pendiente', 'confirmado']
    ).count()

    # Ingresos hoy (solo de pedidos con facturas pagadas - para mostrar diferencia)
    facturas_hoy_pagadas = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lt=fin_dia,
        estado='pagada'
    )
    ingresos_hoy = facturas_hoy_pagadas.aggregate(total=Sum('total'))[
        'total'] or 0

    # Pedidos a domicilio activos (sin factura activa)
    pedidos_domicilio_activos = Pedido.objects.annotate(
        factura_activa_annotated=Exists(facturas_activas)
    ).filter(
        factura_activa_annotated=False,
        tipo_pedido='delivery'
    ).exclude(
        estado='cancelado'
    ).count()

    # Obtener estadísticas adicionales para información
    total_pedidos_completados = Factura.objects.filter(estado='pagada').count()
    ingresos_totales = Factura.objects.filter(
        estado='pagada').aggregate(total=Sum('total'))['total'] or 0

    context = {
        'user': request.user,
        'page_title': 'Gestión de Pedidos Activos',
        'pedidos': pedidos_procesados,
        'clientes_credito_json': json.dumps([
            {
                'id': cliente.id,
                'nombre': cliente.nombre_completo,
                'cedula': cliente.cedula,
                'telefono': cliente.telefono_principal,
                'limite_credito': float(cliente.limite_credito or 0),
                'dias_credito': int(cliente.dias_credito or 0),
            }
            for cliente in Cliente.objects.filter(activo=True).order_by('nombre_completo')
        ]),
        'estadisticas': {
            # Solo pedidos activos (sin pagar)
            'total_pedidos': total_pedidos_activos,
            'pedidos_pendientes': pedidos_pendientes_count,
            'ingresos_hoy': ingresos_hoy,  # Solo ingresos de pedidos ya pagados hoy
            'pedidos_domicilio': pedidos_domicilio_activos,
            'total_pedidos_pagados': total_pedidos_completados,  # Para información
            'ingresos_totales': ingresos_totales,  # Para información
        },
        'filtros': {
            'search': search,
            'estado': estado,
            'tipo_pedido': tipo_pedido,
            'fecha': fecha,
            'sort': sort_by,
        },
        'paginator': page_obj,
        'mostrando_activos': True,  # Flag para mostrar que solo se ven activos
    }
    return render(request, 'facturacion/gestiondepedidos.html', context)


@csrf_exempt
def actualizar_inventario_bebidas(items, operacion='restar'):
    """
    Actualiza el inventario de bebidas basado en los items de un pedido.
    Retorna alertas cuando el stock llega a cero o es insuficiente.

    operacion: 'restar' (al agregar al pedido) o 'sumar' (al cancelar o quitar del pedido)
    Retorna: (alertas, productos_actualizados)
    """
    print(
        f"🔄 actualizar_inventario_bebidas: {len(items)} items, operación: {operacion}")

    alertas = []
    productos_actualizados = []

    for item in items:
        item_id = item.get('id', '')
        item_name = item.get('name', '')
        cantidad = item.get('quantity', 1)

        # Evitar ruido/errores: solo procesar items de bebidas.
        categoria_item = str(item.get('categoria', '') or '').lower()
        tipo_item = str(item.get('tipo', '') or '').lower()
        item_id_str = str(item_id or '').strip()
        item_id_upper = item_id_str.upper()

        es_bebida = bool(item.get('es_bebida')
                         ) or categoria_item == 'bebida' or tipo_item == 'bebida'
        es_id_bebida = item_id_upper.startswith(
            'PROD-') or item_id_str.startswith('bebida_')
        es_id_plato = item_id_upper.startswith(
            'PLATO-') or item_id_str.startswith('plato_')

        if es_id_plato:
            es_bebida = False

        if not es_bebida and not es_id_bebida:
            continue

        print(
            f"  Procesando item: {item_name} (id: {item_id}, cantidad: {cantidad})")

        # Caso 1: El ID viene con prefijo de producto/bebida (PROD-123 o bebida_123)
        if es_id_bebida:
            try:
                if item_id_upper.startswith('PROD-'):
                    prod_id = int(item_id_str.split('-')[1])
                else:
                    prod_id = int(item_id_str.replace('bebida_', '', 1))

                producto = Producto.objects.filter(
                    id=prod_id, categoria='bebida').first()

                if producto:
                    try:
                        cantidad_decimal = Decimal(str(cantidad))
                        stock_anterior = producto.cantidad

                        if operacion == 'restar':
                            producto.cantidad -= cantidad_decimal
                            mensaje = f"Descontando {cantidad_decimal} de {producto.nombre}"

                            # Verificar si quedó en cero o negativo
                            if producto.cantidad <= 0:
                                alertas.append({
                                    'tipo': 'advertencia',
                                    'producto': producto.nombre,
                                    'stock_anterior': float(stock_anterior),
                                    'stock_actual': float(producto.cantidad),
                                    'cantidad_solicitada': float(cantidad_decimal),
                                    'mensaje': f"¡ATENCIÓN! {producto.nombre} quedó con stock CERO o NEGATIVO. Stock actual: {producto.cantidad}"
                                })
                                print(
                                    f"  ⚠️ ALERTA: {producto.nombre} quedó con stock {producto.cantidad}")

                            # Verificar si el stock es bajo (menos de 10 unidades)
                            elif producto.cantidad < 10:
                                alertas.append({
                                    'tipo': 'bajo_stock',
                                    'producto': producto.nombre,
                                    'stock_actual': float(producto.cantidad),
                                    'mensaje': f"Stock bajo de {producto.nombre}. Quedan solo {producto.cantidad} unidades."
                                })
                                print(
                                    f"  📉 Stock bajo: {producto.nombre} - {producto.cantidad} unidades")

                        else:  # 'sumar'
                            producto.cantidad += cantidad_decimal
                            mensaje = f"Reponiendo {cantidad_decimal} a {producto.nombre}"

                        producto.save()
                        print(
                            f"  ✅ {mensaje} (Stock anterior: {stock_anterior}, actual: {producto.cantidad})")

                        productos_actualizados.append({
                            'id': producto.id,
                            'nombre': producto.nombre,
                            'stock_anterior': float(stock_anterior),
                            'stock_actual': float(producto.cantidad),
                            'categoria': producto.categoria
                        })

                    except Exception as e:
                        print(f"  ❌ Error con cantidad: {e}")
                else:
                    print(
                        f"  ⚠️ Producto no encontrado o no es bebida: {item_id}")

            except (IndexError, ValueError) as e:
                print(f"  ❌ Error al parsear ID {item_id}: {e}")

        # Caso 2: Buscar por ID numérico directo
        elif item_id_str.isdigit():
            producto = Producto.objects.filter(
                id=int(item_id_str),
                categoria='bebida'
            ).first()

            if producto:
                try:
                    cantidad_decimal = Decimal(str(cantidad))
                    stock_anterior = producto.cantidad

                    if operacion == 'restar':
                        producto.cantidad -= cantidad_decimal
                        mensaje = f"Descontando {cantidad_decimal} de {producto.nombre}"

                        if producto.cantidad <= 0:
                            alertas.append({
                                'tipo': 'advertencia',
                                'producto': producto.nombre,
                                'stock_anterior': float(stock_anterior),
                                'stock_actual': float(producto.cantidad),
                                'cantidad_solicitada': float(cantidad_decimal),
                                'mensaje': f"¡ATENCIÓN! {producto.nombre} quedó con stock CERO o NEGATIVO. Stock actual: {producto.cantidad}"
                            })
                        elif producto.cantidad < 10:
                            alertas.append({
                                'tipo': 'bajo_stock',
                                'producto': producto.nombre,
                                'stock_actual': float(producto.cantidad),
                                'mensaje': f"Stock bajo de {producto.nombre}. Quedan solo {producto.cantidad} unidades."
                            })
                    else:
                        producto.cantidad += cantidad_decimal
                        mensaje = f"Reponiendo {cantidad_decimal} a {producto.nombre}"

                    producto.save()
                    print(
                        f"  ✅ {mensaje} (Stock anterior: {stock_anterior}, actual: {producto.cantidad})")

                    productos_actualizados.append({
                        'id': producto.id,
                        'nombre': producto.nombre,
                        'stock_anterior': float(stock_anterior),
                        'stock_actual': float(producto.cantidad),
                        'categoria': producto.categoria
                    })
                except Exception as e:
                    print(f"  ❌ Error con cantidad: {e}")
            else:
                print(
                    f"  ⚠️ No se encontró bebida con ID numérico: {item_id_str}")

        # Caso 3: Buscar por nombre si no tenemos ID utilizable
        elif item_name:
            producto = Producto.objects.filter(
                nombre__iexact=item_name,
                categoria='bebida'
            ).first() or Producto.objects.filter(
                nombre__icontains=item_name,
                categoria='bebida'
            ).first()

            if producto:
                try:
                    cantidad_decimal = Decimal(str(cantidad))
                    stock_anterior = producto.cantidad

                    if operacion == 'restar':
                        producto.cantidad -= cantidad_decimal
                        mensaje = f"Descontando {cantidad_decimal} de {producto.nombre}"

                        # Verificar si quedó en cero o negativo
                        if producto.cantidad <= 0:
                            alertas.append({
                                'tipo': 'advertencia',
                                'producto': producto.nombre,
                                'stock_anterior': float(stock_anterior),
                                'stock_actual': float(producto.cantidad),
                                'cantidad_solicitada': float(cantidad_decimal),
                                'mensaje': f"¡ATENCIÓN! {producto.nombre} quedó con stock CERO o NEGATIVO. Stock actual: {producto.cantidad}"
                            })
                            print(
                                f"  ⚠️ ALERTA: {producto.nombre} quedó con stock {producto.cantidad}")

                        # Verificar si el stock es bajo (menos de 10 unidades)
                        elif producto.cantidad < 10:
                            alertas.append({
                                'tipo': 'bajo_stock',
                                'producto': producto.nombre,
                                'stock_actual': float(producto.cantidad),
                                'mensaje': f"Stock bajo de {producto.nombre}. Quedan solo {producto.cantidad} unidades."
                            })
                            print(
                                f"  📉 Stock bajo: {producto.nombre} - {producto.cantidad} unidades")

                    else:  # 'sumar'
                        producto.cantidad += cantidad_decimal
                        mensaje = f"Reponiendo {cantidad_decimal} a {producto.nombre}"

                    producto.save()
                    print(
                        f"  ✅ {mensaje} (Stock anterior: {stock_anterior}, actual: {producto.cantidad})")

                    productos_actualizados.append({
                        'id': producto.id,
                        'nombre': producto.nombre,
                        'stock_anterior': float(stock_anterior),
                        'stock_actual': float(producto.cantidad),
                        'categoria': producto.categoria
                    })

                except Exception as e:
                    print(f"  ❌ Error con cantidad: {e}")
            else:
                print(f"  ⚠️ No se encontró bebida con nombre: {item_name}")

        else:
            print(f"  ⚠️ Item sin ID ni nombre válido: {item}")

    return alertas, productos_actualizados


@csrf_exempt
def procesar_pedidos_para_template(pedidos_queryset):
    """Procesa los pedidos para ser usados en el template - Incluye info de pago"""
    from zoneinfo import ZoneInfo

    tz_rd = ZoneInfo('America/Santo_Domingo')
    pedidos_procesados = []

    for pedido in pedidos_queryset:
        # Obtener items del pedido
        try:
            if isinstance(pedido.items, str):
                items = json.loads(pedido.items)
            else:
                items = pedido.items or []
        except:
            items = []

        # Usar la propiedad existente del modelo para verificar si tiene factura pagada
        tiene_factura_pagada = pedido.tiene_factura_pagada

        # Determinar nombre del cliente basado en el tipo de pedido
        nombre_cliente = pedido.nombre_cliente
        if not nombre_cliente:
            if pedido.tipo_pedido == 'mesa' and pedido.mesa:
                nombre_cliente = f"Mesa {pedido.mesa.numero_display}"
            elif pedido.tipo_pedido == 'delivery':
                nombre_cliente = f"Delivery {pedido.codigo_delivery}"
            elif pedido.tipo_pedido == 'llevar':
                nombre_cliente = f"Para Llevar {pedido.codigo_delivery}"
            else:
                nombre_cliente = "Cliente no especificado"

        # Convertir el tipo de pedido al formato del frontend
        tipo_map = {
            'mesa': 'restaurante',
            'delivery': 'domicilio',
            'llevar': 'recoger'
        }
        tipo_frontend = tipo_map.get(pedido.tipo_pedido, pedido.tipo_pedido)

        # Calcular cantidad total de items
        cantidad_items = sum(item.get('quantity', 0) for item in items)

        fecha_local = timezone.localtime(pedido.fecha_pedido, tz_rd)

        pedido_procesado = {
            'id': pedido.id,
            'codigo_pedido': pedido.codigo_pedido,
            'nombre_cliente': pedido.nombre_cliente or '',
            'nombre_cliente_original': pedido.nombre_cliente or '',
            'customer_name': nombre_cliente,
            'customer_phone': pedido.telefono_cliente or '',
            'customer_address': pedido.direccion_entrega or '',
            'fecha_pedido': pedido.fecha_pedido,
            'items': items,
            'tipo_pedido': tipo_frontend,
            'tipo_pedido_original': pedido.tipo_pedido,
            'estado': pedido.estado,
            'estado_display': pedido.get_estado_display(),
            'subtotal': float(pedido.subtotal),
            'envio': float(pedido.envio),
            'total': float(pedido.total),
            'mesa_numero': pedido.mesa.numero_display if pedido.mesa else '',
            'codigo_delivery': pedido.codigo_delivery or '',
            'notas': pedido.notas or '',
            'cantidad_items': cantidad_items,
            'fecha_formateada': fecha_local.strftime('%d/%m/%Y %I:%M'),
            'tiene_factura_pagada': tiene_factura_pagada,
        }

        pedidos_procesados.append(pedido_procesado)

    return pedidos_procesados


@csrf_exempt
def historial_pedidos_pagados(request):
    """Vista para ver el historial de facturas emitidas con paginación."""
    # Zona horaria República Dominicana + formato de fecha local.
    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    fecha_reporte = ahora_local.strftime('%d/%m/%Y %I:%M %p')
    # Obtener parámetros de filtrado
    search = request.GET.get('search', '')
    tipo_pedido = request.GET.get('tipo_pedido', request.GET.get('tipo', ''))
    fecha = request.GET.get('fecha', '')
    page = request.GET.get('page', 1)

    # Consulta base: TODAS las facturas (sin filtro de estado)
    facturas_base = Factura.objects.all().select_related('pedido')
    # Consulta para listado (sí aplica filtros)
    facturas = facturas_base.order_by('numero_factura')

    # Aplicar filtros
    if search:
        facturas = facturas.filter(
            Q(numero_factura__icontains=search) |
            Q(nombre_cliente__icontains=search) |
            Q(telefono_cliente__icontains=search) |
            Q(numero_mesa_codigo__icontains=search) |
            Q(pedido__codigo_pedido__icontains=search)
        )

    if tipo_pedido:
        facturas = facturas.filter(tipo_pedido=tipo_pedido)

    if fecha:
        # Filtro por rangos de fecha-hora en zona RD para evitar desfases por timezone.
        inicio_hoy = ahora_local.replace(
            hour=0, minute=0, second=0, microsecond=0)
        fin_hoy = inicio_hoy + timedelta(days=1)
        inicio_mes_actual = inicio_hoy.replace(day=1)

        if fecha == 'hoy':
            facturas = facturas.filter(
                fecha_factura__gte=inicio_hoy, fecha_factura__lt=fin_hoy)
        elif fecha == 'ayer':
            inicio_ayer = inicio_hoy - timedelta(days=1)
            facturas = facturas.filter(
                fecha_factura__gte=inicio_ayer, fecha_factura__lt=inicio_hoy)
        elif fecha in ['ultimos_7_dias', 'semana']:
            inicio_7_dias = inicio_hoy - timedelta(days=6)
            facturas = facturas.filter(
                fecha_factura__gte=inicio_7_dias, fecha_factura__lt=fin_hoy)
        elif fecha == 'ultimos_30_dias':
            inicio_30_dias = inicio_hoy - timedelta(days=29)
            facturas = facturas.filter(
                fecha_factura__gte=inicio_30_dias, fecha_factura__lt=fin_hoy)
        elif fecha in ['este_mes', 'mes']:
            facturas = facturas.filter(
                fecha_factura__gte=inicio_mes_actual, fecha_factura__lt=fin_hoy)
        elif fecha == 'mes_pasado':
            fin_mes_pasado = inicio_mes_actual
            ultimo_dia_mes_pasado = inicio_mes_actual - timedelta(days=1)
            inicio_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
            facturas = facturas.filter(
                fecha_factura__gte=inicio_mes_pasado, fecha_factura__lt=fin_mes_pasado)
        elif fecha == 'este_anio':
            inicio_anio = inicio_hoy.replace(month=1, day=1)
            facturas = facturas.filter(
                fecha_factura__gte=inicio_anio, fecha_factura__lt=fin_hoy)
        elif fecha == 'semana_actual':
            inicio_semana = (
                inicio_hoy - timedelta(days=ahora_local.weekday()))
            facturas = facturas.filter(
                fecha_factura__gte=inicio_semana, fecha_factura__lt=fin_hoy)

    # Paginación de 50 facturas por página
    paginator = Paginator(facturas, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Procesar facturas para template (reutiliza estructura de la tabla actual)
    pedidos_procesados = []
    for factura in page_obj:
        fecha_base = factura.fecha_factura or timezone.now()
        fecha_local = timezone.localtime(fecha_base, tz_rd)

        pedido_asociado = factura.pedido
        if pedido_asociado:
            tipo_pedido_display = pedido_asociado.get_tipo_pedido_display()
        else:
            tipos = {
                'mesa': 'Comer en Restaurante',
                'delivery': 'Domicilio',
                'llevar': 'Recoger en Local',
            }
            tipo_pedido_display = tipos.get(factura.tipo_pedido, factura.tipo_pedido.title(
            ) if factura.tipo_pedido else 'No definido')

        pedido_procesado = {
            'id': pedido_asociado.id if pedido_asociado else '',
            'codigo_pedido': pedido_asociado.codigo_pedido if pedido_asociado else 'N/A',
            'nombre_cliente': factura.nombre_cliente or 'Cliente no registrado',
            'telefono_cliente': factura.telefono_cliente or '',
            'direccion_entrega': factura.direccion_entrega or '',
            'tipo_pedido': factura.tipo_pedido,
            'tipo_pedido_display': tipo_pedido_display,
            'estado': factura.estado,
            'estado_display': factura.get_estado_display(),
            'total': float(factura.total or 0),
            'fecha_formateada': fecha_local.strftime('%d/%m/%Y %I:%M %p'),
            'mesa_numero': factura.numero_mesa_codigo or '',
            'factura_numero': factura.numero_factura,
            'factura_fecha': factura.fecha_factura,
            'metodo_pago': factura.metodo_pago or '',
        }
        pedidos_procesados.append(pedido_procesado)

    # Estadísticas

    facturas_pagadas = facturas.filter(estado='pagada')
    total_facturas_emitidas = facturas.count()
    ingresos_totales = facturas_pagadas.aggregate(total=Sum('total'))[
        'total'] or 0

    # Ingresos del mes actual en zona horaria RD (solo facturas pagadas)
    inicio_mes_rd = ahora_local.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_hoy_rd = ahora_local.replace(
        hour=0, minute=0, second=0, microsecond=0)
    fin_hoy_rd = inicio_hoy_rd + timedelta(days=1)
    ingresos_mes_actual = facturas_base.filter(
        estado='pagada',
        fecha_factura__gte=inicio_mes_rd,
        fecha_factura__lt=fin_hoy_rd
    ).aggregate(total=Sum('total'))['total'] or 0

    context = {
        'user': request.user,
        'page_title': 'Historial de Todas las Facturas',
        'pedidos': pedidos_procesados,
        'estadisticas': {
            'total_pedidos': total_facturas_emitidas,
            'ingresos_totales': ingresos_totales,
            'ingresos_mes_actual': ingresos_mes_actual,
        },
        'filtros': {
            'search': search,
            'tipo_pedido': tipo_pedido,
            'fecha': fecha,
        },
        'paginator': paginator,
        'page_obj': page_obj,
        'fecha_reporte': fecha_reporte,
    }
    return render(request, 'facturacion/historial_pedidos.html', context)


@csrf_exempt
def detalle_pedido(request, pedido_id):
    """Obtener detalles completos de un pedido para el modal"""
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # Obtener items del pedido
    try:
        if isinstance(pedido.items, str):
            items = json.loads(pedido.items)
        else:
            items = pedido.items or []
    except:
        items = []

    # Formatear fecha
    fecha_pedido = pedido.fecha_pedido.strftime(
        '%A, %d de %B de %Y a las %H:%M')

    # Determinar información del cliente
    nombre_cliente = pedido.nombre_cliente

    data = {
        'id': pedido.id,
        'codigo_pedido': pedido.codigo_pedido,
        'fecha_pedido': fecha_pedido,
        'estado': pedido.estado,
        'estado_display': pedido.get_estado_display(),
        'tipo_pedido': pedido.tipo_pedido,
        'tipo_pedido_display': pedido.get_tipo_pedido_display(),
        'nombre_cliente': nombre_cliente,
        'telefono_cliente': pedido.telefono_cliente or '',
        'direccion_entrega': pedido.direccion_entrega or '',
        'codigo_delivery': pedido.codigo_delivery or '',
        'mesa_numero': pedido.mesa.numero_display if pedido.mesa else '',
        'items': items,  # Asegúrate de que esto incluya todos los campos necesarios
        'subtotal': float(pedido.subtotal),
        'envio': float(pedido.envio),
        'total': float(pedido.total),
        'notas': pedido.notas or '',
        'cantidad_items': len(items),
    }

    return JsonResponse(data)


@csrf_exempt
def cambiar_estado_pedido(request, pedido_id):
    """Cambiar estado de un pedido y agregar nuevos items si los hay"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        nuevo_estado = request.POST.get('estado')
        nuevos_items_json = request.POST.get('nuevos_items')

        if not nuevo_estado:
            return JsonResponse({'error': 'Estado no especificado'}, status=400)

        # Obtener los items actuales del pedido
        try:
            if isinstance(pedido.items, str):
                items_actuales = json.loads(pedido.items)
            else:
                items_actuales = pedido.items or []
        except:
            items_actuales = []

        alertas_totales = []
        reposicion_detalle = []

        # Si el estado cambia a CANCELADO, reponer bebidas del inventario
        if nuevo_estado == 'cancelado' and pedido.estado != 'cancelado':
            print(
                f"🔄 Cancelando pedido {pedido.codigo_pedido} - Reponiendo bebidas...")
            alertas, productos_actualizados = actualizar_inventario_bebidas(
                items_actuales, operacion='sumar')
            alertas_totales.extend(alertas)
            reposicion_detalle.extend(productos_actualizados)

        # Si el estado cambia de CANCELADO a otro, descontar bebidas
        elif pedido.estado == 'cancelado' and nuevo_estado != 'cancelado':
            print(
                f"🔄 Reactivando pedido {pedido.codigo_pedido} - Descontando bebidas...")
            alertas, _ = actualizar_inventario_bebidas(
                items_actuales, operacion='restar')
            alertas_totales.extend(alertas)

        # Procesar nuevos items si los hay
        nuevos_items = []
        if nuevos_items_json:
            nuevos_items = json.loads(nuevos_items_json)

        # Si hay nuevos items, descontar bebidas del inventario
        if nuevos_items:
            print(
                f"🔄 Agregando {len(nuevos_items)} nuevos items - Descontando bebidas...")
            alertas, _ = actualizar_inventario_bebidas(
                nuevos_items, operacion='restar')
            alertas_totales.extend(alertas)

        # Agregar los nuevos items a la lista de items actuales
        for item in nuevos_items:
            # Buscar el plato para obtener su información completa
            plato = Plato.objects.filter(id=item.get('plato_id')).first()
            if plato:
                nuevo_item = {
                    'id': plato.id,
                    'name': plato.nombre,
                    'price': float(plato.precio),
                    'quantity': item.get('cantidad', 1),
                    'total': float(plato.precio) * item.get('cantidad', 1)
                }
                items_actuales.append(nuevo_item)

        # Actualizar el pedido con los nuevos items
        pedido.items = json.dumps(items_actuales)

        # Recalcular subtotal/total sin asumir estructura exacta del item.
        def calcular_total_item(item):
            cantidad_item = item.get('quantity', item.get('cantidad', 1))
            try:
                cantidad_decimal = Decimal(str(cantidad_item or 1))
            except (ValueError, TypeError):
                cantidad_decimal = Decimal('1')

            if item.get('total') is not None:
                try:
                    return Decimal(str(item.get('total')))
                except (ValueError, TypeError):
                    pass

            if item.get('subtotal') is not None:
                try:
                    return Decimal(str(item.get('subtotal')))
                except (ValueError, TypeError):
                    pass

            precio_item = item.get('price', item.get('precio', 0))
            try:
                precio_decimal = Decimal(str(precio_item or 0))
            except (ValueError, TypeError):
                precio_decimal = Decimal('0')

            return precio_decimal * cantidad_decimal

        subtotal = sum((calcular_total_item(item)
                       for item in items_actuales), Decimal('0.00'))
        total = subtotal + Decimal(str(pedido.envio or 0))

        pedido.subtotal = subtotal
        pedido.total = total

        # Registrar cambio en historial
        HistorialEstadoPedido.objects.create(
            pedido=pedido,
            estado_anterior=pedido.estado,
            estado_nuevo=nuevo_estado,
            usuario=request.user
        )

        # Actualizar pedido
        pedido.estado = nuevo_estado

        # Si se entrega, registrar fecha de entrega
        if nuevo_estado == 'entregado':
            pedido.fecha_entrega = timezone.now()

        # Liberar mesa si se cancela
        if nuevo_estado == 'cancelado':
            if pedido.mesa:
                pedido.mesa.estado = 'disponible'
                pedido.mesa.save()

        pedido.actualizado_por = request.user
        pedido.save()

        respuesta = {
            'success': True,
            'mensaje': f'Estado actualizado a {pedido.get_estado_display()} y items agregados',
            'estado': pedido.estado,
            'estado_display': pedido.get_estado_display(),
            'codigo_pedido': pedido.codigo_pedido
        }

        # Agregar alertas a la respuesta si existen
        if alertas_totales:
            respuesta['alertas'] = alertas_totales
            print(f"⚠️ Se generaron {len(alertas_totales)} alertas de stock")

        if reposicion_detalle:
            respuesta['reposicion_detalle'] = reposicion_detalle

        return JsonResponse(respuesta)

    except Exception as e:
        print(f"❌ Error en cambiar_estado_pedido: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def eliminar_pedido(request, pedido_id):
    """Eliminar un pedido de la base de datos"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)

        # Verificar si es para eliminar de la vista o cancelar
        eliminar_vista = request.POST.get('eliminar_vista', 'false') == 'true'

        # Obtener items del pedido
        try:
            if isinstance(pedido.items, str):
                items = json.loads(pedido.items) if pedido.items else []
            else:
                items = pedido.items or []
        except:
            items = []

        # Verificar si tiene factura pagada
        tiene_factura_pagada = pedido.facturas.filter(estado='pagada').exists()

        alertas_totales = []
        reposicion_detalle = []

        if eliminar_vista:
            # Eliminar permanentemente de la base de datos
            codigo_pedido = pedido.codigo_pedido

            # Reponer bebidas del inventario si no tiene factura pagada
            if not tiene_factura_pagada:
                print(
                    f"🔄 Eliminando pedido {codigo_pedido} - Reponiendo bebidas...")
                alertas, productos_actualizados = actualizar_inventario_bebidas(
                    items, operacion='sumar')
                alertas_totales.extend(alertas)
                reposicion_detalle.extend(productos_actualizados)

            # Verificar si tiene facturas antes de eliminar
            if pedido.facturas.exists():
                return JsonResponse({
                    'error': 'No se puede eliminar el pedido porque tiene facturas asociadas'
                }, status=400)

            # LIBERAR MESA solo si NO tiene factura pagada
            if pedido.mesa and not tiene_factura_pagada:
                pedido.mesa.estado = 'disponible'
                pedido.mesa.save()

            pedido.delete()

            respuesta = {
                'success': True,
                'mensaje': f'Pedido {codigo_pedido} eliminado de la vista',
                'eliminado': True
            }

        else:
            # Marcar como cancelado (comportamiento anterior)

            # Reponer bebidas del inventario si no tiene factura pagada
            if not tiene_factura_pagada:
                print(
                    f"🔄 Cancelando pedido {pedido.codigo_pedido} - Reponiendo bebidas...")
                alertas, productos_actualizados = actualizar_inventario_bebidas(
                    items, operacion='sumar')
                alertas_totales.extend(alertas)
                reposicion_detalle.extend(productos_actualizados)

            # LIBERAR MESA solo si NO tiene factura pagada
            if pedido.mesa and not tiene_factura_pagada:
                pedido.mesa.estado = 'disponible'
                pedido.mesa.save()

            pedido.estado = 'cancelado'
            pedido.actualizado_por = request.user
            pedido.save()

            respuesta = {
                'success': True,
                'mensaje': f'Pedido {pedido.codigo_pedido} cancelado'
            }

        # Agregar alertas a la respuesta si existen
        if alertas_totales:
            respuesta['alertas'] = alertas_totales
            print(f"⚠️ Se generaron {len(alertas_totales)} alertas de stock")

        if reposicion_detalle:
            respuesta['reposicion_detalle'] = reposicion_detalle

        return JsonResponse(respuesta)

    except Exception as e:
        print(f"❌ Error al eliminar pedido: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def verificar_stock_multiples(request):
    """Verificar stock de múltiples productos (bebidas) a la vez"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        items = data.get('items', [])

        productos_sin_stock = []

        for item in items:
            item_id = item.get('id', '')
            item_name = item.get('name', '')
            cantidad = item.get('quantity', 1)

            # Verificar si es un producto de categoría bebida
            if isinstance(item_id, str) and item_id.startswith('PROD-'):
                try:
                    prod_id = int(item_id.split('-')[1])
                    producto = Producto.objects.filter(
                        id=prod_id, categoria='bebida').first()

                    if producto:
                        cantidad_decimal = Decimal(str(cantidad))

                        # Verificar si hay suficiente stock
                        if producto.cantidad < cantidad_decimal:
                            productos_sin_stock.append({
                                'id': producto.id,
                                'nombre': producto.nombre,
                                'stock_actual': float(producto.cantidad),
                                'cantidad_solicitada': float(cantidad_decimal),
                                'mensaje': f'Stock insuficiente de {producto.nombre}. Stock actual: {producto.cantidad}, cantidad solicitada: {cantidad_decimal}'
                            })

                except (IndexError, ValueError) as e:
                    print(f"Error al parsear ID {item_id}: {e}")

            elif item_name:
                producto = Producto.objects.filter(
                    nombre__icontains=item_name,
                    categoria='bebida'
                ).first()

                if producto:
                    cantidad_decimal = Decimal(str(cantidad))

                    # Verificar si hay suficiente stock
                    if producto.cantidad < cantidad_decimal:
                        productos_sin_stock.append({
                            'id': producto.id,
                            'nombre': producto.nombre,
                            'stock_actual': float(producto.cantidad),
                            'cantidad_solicitada': float(cantidad_decimal),
                            'mensaje': f'Stock insuficiente de {producto.nombre}. Stock actual: {producto.cantidad}, cantidad solicitada: {cantidad_decimal}'
                        })

        if productos_sin_stock:
            return JsonResponse({
                'exito': False,
                'productos_sin_stock': productos_sin_stock,
                'mensaje': f'Stock insuficiente para {len(productos_sin_stock)} producto(s)'
            })

        return JsonResponse({
            'exito': True,
            'mensaje': 'Stock disponible para todos los productos'
        })

    except Exception as e:
        print(f"Error en verificar_stock_multiples: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def verificar_stock(request, producto_id):
    """Verificar stock de un producto específico"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        cantidad_solicitada = request.GET.get('cantidad', 1)

        # Buscar el producto por ID y que sea de categoría bebida
        producto = Producto.objects.filter(
            id=producto_id, categoria='bebida').first()

        if not producto:
            return JsonResponse({
                'exito': False,
                'mensaje': 'Producto no encontrado o no es una bebida'
            }, status=404)

        cantidad_decimal = Decimal(str(cantidad_solicitada))

        if producto.cantidad >= cantidad_decimal:
            return JsonResponse({
                'exito': True,
                'producto': producto.nombre,
                'stock_actual': float(producto.cantidad),
                'cantidad_solicitada': float(cantidad_decimal),
                'disponible': True
            })
        else:
            return JsonResponse({
                'exito': False,
                'producto': producto.nombre,
                'stock_actual': float(producto.cantidad),
                'cantidad_solicitada': float(cantidad_decimal),
                'disponible': False,
                'mensaje': f'Stock insuficiente de {producto.nombre}. Stock actual: {producto.cantidad}, cantidad solicitada: {cantidad_decimal}'
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def platos_disponibles(request):
    """Obtener lista de productos disponibles (bebidas y platos) para agregar a un pedido"""
    search = request.GET.get('search', '')
    tipo = request.GET.get('tipo', 'todos')  # 'bebida', 'plato', 'todos'

    try:
        resultados = []

        # Si se solicita bebidas o todos
        if tipo in ['bebida', 'todos']:
            # Filtrar productos de categoría bebida
            productos = Producto.objects.filter(categoria='bebida')
            if search:
                productos = productos.filter(nombre__icontains=search)

            for producto in productos:
                resultados.append({
                    'id': f"PROD-{producto.id}",
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'precio': float(producto.precio_compra),
                    'tipo': 'bebida',
                    'categoria': producto.get_category_label(),
                    'cantidad_disponible': float(producto.cantidad),
                    'stock_status': producto.get_stock_status(),
                    'stock_label': producto.get_stock_label(),
                    'stock_icon': producto.get_stock_icon(),
                    'es_producto': True,
                })

        # Si se solicita platos o todos
        if tipo in ['plato', 'todos']:
            # Filtrar platos activos
            platos = Plato.objects.filter(activo=True)
            if search:
                platos = platos.filter(nombre__icontains=search)

            for plato in platos:
                resultados.append({
                    'id': f"PLATO-{plato.id}",
                    'codigo': plato.codigo,
                    'nombre': plato.nombre,
                    'precio': float(plato.precio),
                    'tipo': 'plato',
                    'categoria': plato.get_categoria_display(),
                    'cantidad_disponible': None,  # Platos no tienen inventario directo
                    'stock_status': 'high',
                    'stock_label': 'Disponible',
                    'stock_icon': '🍽️',
                    'es_producto': False,
                })

        # Ordenar por tipo y nombre
        resultados.sort(key=lambda x: (x['tipo'] != 'bebida', x['nombre']))

        return JsonResponse(resultados, safe=False)

    except Exception as e:
        print(f"Error en platos_disponibles: {e}")
        return JsonResponse([], safe=False)


@csrf_exempt
def editar_pedido(request, pedido_id):
    """Editar un pedido existente - agregar/eliminar items, cambiar estado"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)

        print(f"\n=== EDITANDO PEDIDO {pedido.codigo_pedido} ===")

        # Obtener datos del formulario
        nuevos_items_json = request.POST.get('nuevos_items')
        nombre_cliente = request.POST.get('nombre_cliente')
        telefono_cliente = request.POST.get('telefono_cliente')
        notas = request.POST.get('notas')
        tipo_pago = (request.POST.get('tipo_pago', 'contado')
                     or 'contado').strip().lower()
        cliente_credito_id = (request.POST.get(
            'cliente_credito_id', '') or '').strip()

        if tipo_pago not in ['contado', 'credito']:
            tipo_pago = 'contado'

        if not nuevos_items_json:
            return JsonResponse({'error': 'No se proporcionaron items'}, status=400)

        # Obtener los items actuales del pedido (antes de cambiar)
        try:
            if isinstance(pedido.items, str):
                items_actuales = json.loads(
                    pedido.items) if pedido.items else []
            else:
                items_actuales = pedido.items or []
        except Exception as e:
            print(f"❌ Error al cargar items actuales: {e}")
            items_actuales = []

        print(f"Items actuales: {len(items_actuales)} items")

        # Parsear los nuevos items
        nuevos_items = json.loads(nuevos_items_json)
        print(f"Nuevos items: {len(nuevos_items)} items")

        # 🔄 GESTIÓN DE INVENTARIO DE BEBIDAS

        # 1. Identificar items que se van a eliminar (están en items_actuales pero no en nuevos_items)
        items_a_eliminar = []
        for item_actual in items_actuales:
            encontrado = False
            for item_nuevo in nuevos_items:
                # Comparar por id o nombre
                if (item_nuevo.get('id') == item_actual.get('id') or
                        item_nuevo.get('name') == item_actual.get('name')):
                    encontrado = True
                    break

            if not encontrado:
                items_a_eliminar.append(item_actual)

        # 2. Identificar items nuevos (están en nuevos_items pero no en items_actuales)
        items_a_agregar = []
        for item_nuevo in nuevos_items:
            encontrado = False
            for item_actual in items_actuales:
                if (item_nuevo.get('id') == item_actual.get('id') or
                        item_nuevo.get('name') == item_actual.get('name')):
                    encontrado = True
                    break

            if not encontrado:
                items_a_agregar.append(item_nuevo)

        # 3. Identificar items modificados (cambia la cantidad)
        items_modificados = []
        for item_nuevo in nuevos_items:
            for item_actual in items_actuales:
                if (item_nuevo.get('id') == item_actual.get('id') or
                        item_nuevo.get('name') == item_actual.get('name')):

                    cantidad_actual = item_actual.get('quantity', 1)
                    cantidad_nueva = item_nuevo.get('quantity', 1)

                    if cantidad_actual != cantidad_nueva:
                        items_modificados.append({
                            'item': item_nuevo,
                            'cantidad_anterior': cantidad_actual,
                            'cantidad_nueva': cantidad_nueva,
                            'diferencia': cantidad_nueva - cantidad_actual
                        })
                    break

        print(f"\n🔍 Análisis de cambios:")
        print(f"   Items a eliminar: {len(items_a_eliminar)}")
        print(f"   Items a agregar: {len(items_a_agregar)}")
        print(f"   Items modificados: {len(items_modificados)}")

        # 4. Aplicar cambios al inventario de bebidas
        alertas_totales = []

        # Reponer bebidas de items eliminados
        if items_a_eliminar:
            print(
                f"\n🔄 Reponiendo bebidas de {len(items_a_eliminar)} items eliminados...")
            alertas, _ = actualizar_inventario_bebidas(
                items_a_eliminar, operacion='sumar')
            alertas_totales.extend(alertas)

        # Descontar bebidas de items nuevos
        if items_a_agregar:
            print(
                f"\n🔄 Descontando bebidas de {len(items_a_agregar)} items nuevos...")
            alertas, _ = actualizar_inventario_bebidas(
                items_a_agregar, operacion='restar')
            alertas_totales.extend(alertas)

        # Ajustar bebidas de items modificados
        for item_mod in items_modificados:
            item = item_mod['item']
            diferencia = item_mod['diferencia']

            if diferencia != 0:
                # Crear un item temporal con la diferencia
                item_diferencia = {
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'quantity': abs(diferencia),
                    'price': item.get('price'),
                    'total': item.get('total')
                }

                if diferencia > 0:
                    # Se aumentó la cantidad, descontar diferencia
                    print(
                        f"\n📈 Aumentando cantidad de {item['name']} en {diferencia} - Descontando...")
                    alertas, _ = actualizar_inventario_bebidas(
                        [item_diferencia], operacion='restar')
                    alertas_totales.extend(alertas)
                else:
                    # Se disminuyó la cantidad, reponer diferencia
                    print(
                        f"\n📉 Disminuyendo cantidad de {item['name']} en {abs(diferencia)} - Reponiendo...")
                    alertas, _ = actualizar_inventario_bebidas(
                        [item_diferencia], operacion='sumar')
                    alertas_totales.extend(alertas)

        # Actualizar información del cliente según tipo de pago
        cliente_credito = None
        if tipo_pago == 'credito':
            if not cliente_credito_id:
                return JsonResponse({'error': 'Para venta a crédito debes seleccionar un cliente'}, status=400)
            try:
                cliente_credito = Cliente.objects.get(
                    id=cliente_credito_id, activo=True)
            except Cliente.DoesNotExist:
                return JsonResponse({'error': 'El cliente seleccionado para crédito no es válido'}, status=400)

            pedido.nombre_cliente = cliente_credito.nombre_completo
            pedido.telefono_cliente = cliente_credito.telefono_principal or ''
            pedido.notas = f"TIPO_PAGO_PEDIDO=credito;CLIENTE_CREDITO_ID={cliente_credito.id}"
        else:
            # Contado por defecto: para pedidos de mesa mantener referencia de mesa.
            if pedido.tipo_pedido == 'mesa' and pedido.mesa:
                pedido.nombre_cliente = f"Mesa {pedido.mesa.numero_display}"
                pedido.telefono_cliente = ''
            else:
                if nombre_cliente is not None:
                    pedido.nombre_cliente = nombre_cliente
                if telefono_cliente is not None:
                    pedido.telefono_cliente = telefono_cliente
            pedido.notas = "TIPO_PAGO_PEDIDO=contado"

        if notas is not None:
            notas_limpias = (notas or '').strip()
            if notas_limpias:
                pedido.notas = f"{pedido.notas};{notas_limpias}"

        # Actualizar items del pedido
        pedido.items = json.dumps(nuevos_items)

        # Recalcular subtotal y total
        subtotal = sum(item.get('total', 0) for item in nuevos_items)
        total = subtotal + float(pedido.envio)

        pedido.subtotal = subtotal
        pedido.total = total

        # Guardar cambios
        pedido.actualizado_por = request.user
        pedido.save()

        print(f"✅ Pedido {pedido.codigo_pedido} actualizado correctamente")

        # Preparar respuesta con alertas si las hay
        respuesta = {
            'success': True,
            'mensaje': f'Pedido {pedido.codigo_pedido} actualizado correctamente',
            'nuevo_total': total,
            'cantidad_items': len(nuevos_items)
        }

        # Agregar alertas a la respuesta si existen
        if alertas_totales:
            respuesta['alertas'] = alertas_totales
            print(f"⚠️ Se generaron {len(alertas_totales)} alertas de stock")

        return JsonResponse(respuesta)

    except Exception as e:
        print(f"❌ Error al editar pedido: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def liberar_mesa_si_corresponde(self):
    """Libera la mesa si la factura está pagada"""
    # Estados que liberan mesa cuando hay factura PAGADA
    # Solo cancelado libera sin factura
    estados_que_liberan_mesa = ['cancelado']

    # Verificar si tiene factura PAGADA
    tiene_factura_pagada = self.facturas.filter(estado='pagada').exists()

    if tiene_factura_pagada and self.mesa:
        # Si tiene factura pagada, liberar mesa
        self.mesa.estado = 'disponible'
        self.mesa.save()
        return True
    elif self.estado in estados_que_liberan_mesa and self.mesa:
        # Solo liberar mesa si está cancelado (sin factura)
        self.mesa.estado = 'disponible'
        self.mesa.save()
        return True

    return False


@csrf_exempt
@login_required
def facturacion(request):
    """Vista principal de facturación"""
    import json
    from datetime import datetime

    try:
        # Obtener IDs de pedidos que ya tienen factura activa (pagada o pendiente de crédito).
        # Solo se permite volver a mostrar si la factura está anulada.
        pedidos_con_factura_activa_ids = set(
            Factura.objects.exclude(estado='anulada').values_list(
                'pedido_id', flat=True)
        )

        # 🔥 Obtener pedidos que NO tienen factura activa
        pedidos_pendientes = Pedido.objects.filter(
            estado__in=['pendiente', 'confirmado', 'preparacion',
                        'listo', 'entregado', 'completado']
        ).exclude(
            # EXCLUIR pedidos con facturas ya creadas (incluye crédito)
            id__in=pedidos_con_factura_activa_ids
        ).select_related('mesa').order_by('-fecha_pedido')

        # Obtener facturas PENDIENTES (las pagadas NO se muestran)
        facturas_pendientes = Factura.objects.filter(
            estado='pendiente').select_related('pedido').all().order_by('-fecha_factura')

        # Preparar datos para JavaScript
        pedidos_json = []

        # Añadir pedidos pendientes de facturar (sin factura pagada)
        for pedido in pedidos_pendientes:
            # Obtener items del pedido
            items_data = []
            try:
                items = pedido.get_items_detalle()
                if isinstance(items, list):
                    for item in items:
                        items_data.append({
                            'name': item.get('nombre', item.get('name', 'Producto')),
                            'quantity': item.get('cantidad', item.get('quantity', 1)),
                            'price': float(item.get('precio', item.get('price', 0))),
                            'total': float(item.get('subtotal', item.get('total', 0))),
                            'categoria': item.get('categoria', '')
                        })
            except Exception as e:
                print(f"Error procesando items del pedido {pedido.id}: {e}")
                items_data = [{
                    'name': 'Producto',
                    'quantity': 1,
                    'price': float(pedido.total),
                    'total': float(pedido.total),
                    'categoria': ''
                }]

            # Determinar número de mesa o código
            numero_mesa_codigo = ''
            if pedido.tipo_pedido == 'mesa' and pedido.mesa:
                numero_mesa_codigo = pedido.mesa.numero_display
            elif pedido.codigo_delivery:
                numero_mesa_codigo = pedido.codigo_delivery

            notas_pedido = pedido.notas or ''
            es_venta_credito = 'TIPO_PAGO_PEDIDO=credito' in notas_pedido

            pedido_dict = {
                'id': pedido.id,
                'codigo_pedido': pedido.codigo_pedido,
                'tipo_pedido': pedido.tipo_pedido,
                'estado': pedido.estado,
                'total': float(pedido.total),
                'mesa': {
                    'id': pedido.mesa.id if pedido.mesa else None,
                    'numero': pedido.mesa.numero if pedido.mesa else None,
                    'numero_display': pedido.mesa.numero_display if pedido.mesa else None,
                } if pedido.mesa else None,
                'codigo_delivery': pedido.codigo_delivery or '',
                'nombre_cliente': pedido.nombre_cliente or '',
                'telefono_cliente': pedido.telefono_cliente or '',
                'direccion_entrega': pedido.direccion_entrega or '',
                'items': items_data,
                'subtotal': float(pedido.subtotal),
                'envio': float(pedido.envio),
                'fecha_pedido': pedido.fecha_pedido.isoformat() if pedido.fecha_pedido else None,
                'es_factura': False,
                'factura_id': None,
                'numero_factura': None,
                'estado_factura': None,
                'metodo_pago': None,
                'fecha_factura': None,
                'es_venta_credito': es_venta_credito,
            }

            pedidos_json.append(pedido_dict)

        # Preparar facturas para estadísticas (todas, incluyendo pagadas)
        facturas_json = []
        todas_facturas = Factura.objects.select_related(
            'pedido').all().order_by('-fecha_factura')
        for factura in todas_facturas:
            try:
                factura_dict = {
                    'id': factura.id,
                    'pedido_id': factura.pedido_id,
                    'invoiceNumber': factura.numero_factura,
                    'codigoPedido': factura.pedido.codigo_pedido if factura.pedido else 'N/A',
                    'tipoPedido': factura.tipo_pedido,
                    'numeroMesaCodigo': factura.numero_mesa_codigo or '',
                    'nombreCliente': factura.nombre_cliente or '',
                    'telefonoCliente': factura.telefono_cliente or '',
                    'direccionEntrega': factura.direccion_entrega or '',
                    'date': factura.fecha_factura.isoformat() if factura.fecha_factura else None,
                    'paymentMethod': factura.metodo_pago,
                    'status': factura.estado,
                    'subtotal': float(factura.subtotal),
                    # 'iva': float(factura.iva),
                    'envio': float(factura.envio),
                    'total': float(factura.total),
                    'notes': factura.notas or '',
                }
                facturas_json.append(factura_dict)
            except Exception as e:
                print(f"Error procesando factura {factura.id}: {e}")

        # Estadísticas
        hoy = datetime.now().date()
        inicio_mes = hoy.replace(day=1)

        total_facturas = todas_facturas.count()
        facturas_mes = todas_facturas.filter(
            fecha_factura__date__gte=inicio_mes)
        ingresos_mes = sum(float(f.total)
                           for f in facturas_mes.filter(estado='pagada'))
        facturas_pendientes_count = facturas_pendientes.count()

        promedio_factura = 0
        if facturas_mes.filter(estado='pagada').count() > 0:
            total_ingresos = sum(float(f.total)
                                 for f in facturas_mes.filter(estado='pagada'))
            promedio_factura = total_ingresos / \
                facturas_mes.filter(estado='pagada').count()

        context = {
            'pedidos_json': json.dumps(pedidos_json, default=str),
            'facturas_json': json.dumps(facturas_json, default=str),
            'estadisticas': {
                'total_facturas': total_facturas,
                'ingresos_mes': round(ingresos_mes, 2),
                'facturas_pendientes': facturas_pendientes_count,
                'promedio_factura': round(promedio_factura, 2),
            }
        }

        return render(request, 'facturacion/facturacion.html', context)

    except Exception as e:
        import traceback
        print(f"ERROR en facturación: {str(e)}")
        traceback.print_exc()

        context = {
            'pedidos_json': json.dumps([], default=str),
            'facturas_json': json.dumps([], default=str),
            'estadisticas': {
                'total_facturas': 0,
                'ingresos_mes': 0,
                'facturas_pendientes': 0,
                'promedio_factura': 0,
            }
        }
        return render(request, 'facturacion/facturacion.html', context)


@csrf_exempt
@login_required
def crear_factura(request):
    """Crear una nueva factura desde un pedido"""
    if request.method == 'POST':
        try:
            pedido_id = request.POST.get('pedido_id')
            pedido = get_object_or_404(Pedido, id=pedido_id)

            notas_pedido = pedido.notas or ''
            pedido_es_credito = 'TIPO_PAGO_PEDIDO=credito' in notas_pedido
            cliente_credito = None

            if pedido_es_credito and 'CLIENTE_CREDITO_ID=' in notas_pedido:
                try:
                    cliente_id_str = notas_pedido.split(
                        'CLIENTE_CREDITO_ID=')[-1].split(';')[0].strip()
                    cliente_credito = Cliente.objects.filter(
                        id=int(cliente_id_str), activo=True).first()
                except (ValueError, TypeError):
                    cliente_credito = None

            # Calcular totales como Decimal para evitar errores float vs Decimal.
            def _to_decimal(value, default='0.00'):
                try:
                    return Decimal(str(value))
                except (ValueError, TypeError):
                    return Decimal(default)

            subtotal = _to_decimal(request.POST.get(
                'subtotal', pedido.subtotal), '0.00')
            # Obtener el valor real de envío si es delivery, si no, dejar en 0
            if pedido.tipo_pedido == 'delivery':
                envio = _to_decimal(request.POST.get(
                    'envio', pedido.envio), '0.00')
            else:
                envio = Decimal('0.00')
            # Establecer IVA a 0 ya que no lo estamos usando
            iva = Decimal('0.00')

            # Calcular el total correctamente
            # Si hay descuento, tomarlo en cuenta (si no existe, usar 0)
            descuento = _to_decimal(request.POST.get('descuento', 0), '0.00')
            total = subtotal - descuento + envio

            # Obtener items del pedido
            items_json = request.POST.get('items', '[]')
            try:
                items = json.loads(items_json)
            except:
                items = pedido.get_items_detalle()

            # Crear la factura con estado PAGADA
            # Obtener hora actual en zona horaria de República Dominicana
            from zoneinfo import ZoneInfo
            from django.utils import timezone
            tz_rd = ZoneInfo('America/Santo_Domingo')
            now_rd = timezone.now().astimezone(tz_rd)

            factura = Factura(
                pedido=pedido,
                tipo_pedido=pedido.tipo_pedido,
                metodo_pago=request.POST.get('metodo_pago', 'efectivo'),
                estado='pendiente' if pedido_es_credito else 'pagada',
                subtotal=subtotal,
                iva=iva,
                envio=envio,
                total=total,
                items=items,
                notas=request.POST.get('notas', ''),
                creado_por=request.user,
                fecha_factura=now_rd,  # Establecer fecha en zona horaria RD
            )

            # Agregar información específica según el tipo de pedido
            if pedido.tipo_pedido == 'mesa' and pedido.mesa:
                factura.numero_mesa_codigo = pedido.mesa.numero_display
            elif pedido.codigo_delivery:
                factura.numero_mesa_codigo = pedido.codigo_delivery

            if pedido.nombre_cliente:
                factura.nombre_cliente = pedido.nombre_cliente
                factura.telefono_cliente = pedido.telefono_cliente

            if pedido_es_credito and cliente_credito:
                factura.nombre_cliente = cliente_credito.nombre_completo
                factura.telefono_cliente = cliente_credito.telefono_principal

            if pedido.tipo_pedido == 'delivery':
                factura.direccion_entrega = pedido.direccion_entrega

            # Guardar la factura y crear FacturaDetalle en la misma transacción
            with transaction.atomic():
                factura.save()

                # Crear detalles relacionales para cada item
                detalles = []
                for item in items:
                    nombre = (
                        item.get('name') or item.get('nombre') or
                        item.get('product') or item.get(
                            'producto') or 'Sin nombre'
                    )
                    try:
                        cantidad = Decimal(
                            str(item.get('quantity') or item.get('cantidad') or 1))
                    except Exception:
                        cantidad = Decimal('1')

                    try:
                        precio = Decimal(
                            str(item.get('price') or item.get('precio') or 0))
                    except Exception:
                        precio = Decimal('0')

                    try:
                        subtotal_item = Decimal(
                            str(item.get('total') or item.get('subtotal') or 0))
                        if subtotal_item == 0:
                            subtotal_item = cantidad * precio
                    except Exception:
                        subtotal_item = cantidad * precio

                    detalles.append(FacturaDetalle(
                        factura=factura,
                        nombre_producto=nombre,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        subtotal=subtotal_item,
                    ))

                if detalles:
                    FacturaDetalle.objects.bulk_create(detalles)

            if pedido_es_credito:
                _sincronizar_cuenta_por_cobrar(factura, cliente_credito)
            else:
                # Factura de contado: el dinero entra en este momento
                MovimientoFinanciero.objects.create(
                    tipo="INGRESO",
                    origen="VENTA",
                    referencia='VENTA_CONTADO',
                    monto=factura.total,
                    fecha_operacion=factura.fecha_factura,
                    factura=factura,
                    metodo_pago=factura.metodo_pago,
                    creado_por=request.user,
                    descripcion=f"Venta factura {factura.numero_factura}",
                )

            # IMPORTANTE: Actualizar estado del pedido a 'completado'
            pedido.estado = 'completado'
            pedido.fecha_entrega = now_rd  # Establecer fecha de entrega en zona horaria RD
            pedido.save()

            # 🔥🔥🔥 LIBERAR MESA solo cuando la factura está PAGADA
            if pedido.tipo_pedido == 'mesa' and pedido.mesa:
                pedido.mesa.estado = 'disponible'
                pedido.mesa.save()
                print(
                    f"✅ Mesa {pedido.mesa.numero_display} liberada al pagar factura")

            # Liberar código de delivery/para llevar si existe
            if pedido.tipo_pedido in ['delivery', 'llevar'] and pedido.codigo_delivery:
                try:
                    config = DeliveryConfig.objects.get(
                        tipo=pedido.tipo_pedido,
                        codigo=pedido.codigo_delivery
                    )
                    config.estado = 'disponible'
                    config.save()
                    print(
                        f"✅ Código {pedido.codigo_delivery} liberado para {pedido.tipo_pedido}")
                except DeliveryConfig.DoesNotExist:
                    pass

            # Descontar bebidas del inventario
            descontar_bebidas_inventario(pedido)

            # Verificar si se debe imprimir
            if request.POST.get('imprimir') == 'true':
                return redirect('imprimir_factura_termica', factura_id=factura.id)

            return redirect('facturacion')

        except IntegrityError as e:
            print(f"Error de integridad al crear factura: {str(e)}")
            messages.error(
                request,
                'No se pudo procesar el pago por un conflicto de numeracion de factura. Intenta nuevamente.'
            )
            return redirect('facturacion')

        except Exception as e:
            print(f"Error al crear factura: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'No se pudo procesar el pago: {str(e)}')
            return redirect('facturacion')

    return redirect('facturacion')


def descontar_bebidas_inventario(pedido):
    """Descontar bebidas del inventario cuando se pague la factura"""
    try:
        items = pedido.get_items_detalle()
        bebidas_descontadas = []

        for item in items:
            # Verificar si el item es de categoría 'bebida'
            if item.get('categoria', '').lower() == 'bebida':
                cantidad = item.get('cantidad', 1)
                nombre_producto = item.get('nombre', 'Bebida')

                # Buscar el producto en el inventario por nombre y categoría bebida
                productos = Producto.objects.filter(
                    nombre__icontains=nombre_producto,
                    categoria='bebida'
                )

                if productos.exists():
                    # Tomar el primer producto que coincida
                    producto = productos.first()
                    if producto.cantidad >= cantidad:
                        # Descontar la cantidad
                        producto.cantidad -= cantidad
                        producto.save()

                        # Actualizar subtotal
                        producto.subtotal = producto.cantidad * producto.precio_compra
                        producto.save()

                        bebidas_descontadas.append(
                            f"{nombre_producto} x{cantidad}")
                        print(
                            f"✅ Descontada bebida: {nombre_producto} x{cantidad} - Stock restante: {producto.cantidad}")
                    else:
                        print(
                            f"⚠️ Stock insuficiente de {nombre_producto}: {producto.cantidad} disponible, se necesita {cantidad}")
                else:
                    print(
                        f"⚠️ Producto de bebida no encontrado en inventario: {nombre_producto}")

        if bebidas_descontadas:
            print(
                f"✅ Total bebidas descontadas del inventario: {', '.join(bebidas_descontadas)}")
        else:
            print(
                "ℹ️ No se descontaron bebidas en este paso (posiblemente ya descontadas al crear el pedido)")

    except Exception as e:
        print(f"❌ Error al descontar bebidas del inventario: {e}")


@csrf_exempt
@login_required
def marcar_factura_pagada(request, factura_id):
    """Marcar una factura como pagada y devolver URL para imprimir"""
    try:
        factura = get_object_or_404(Factura, id=factura_id)

        # Verificar si la factura está pendiente
        if factura.estado != 'pendiente':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'La factura no está en estado pendiente'
                })
            return redirect('facturacion')

        # Marcar como pagada
        factura.estado = 'pagada'
        factura.save()

        # Sincronizar movimientos financieros
        _sincronizar_movimientos_factura(factura)

        # Registrar ingreso financiero — esta factura era de crédito (estado pendiente → pagada)
        MovimientoFinanciero.objects.create(
            tipo="INGRESO",
            origen="VENTA",
            referencia='VENTA_CREDITO',
            monto=factura.total,
            fecha_operacion=timezone.now(),
            factura=factura,
            metodo_pago=factura.metodo_pago,
            creado_por=request.user,
            descripcion=f"Pago de factura {factura.numero_factura}",
        )

        # Actualizar estado del pedido a completado
        if factura.pedido:
            factura.pedido.estado = 'completado'
            factura.pedido.save()

            # LIBERAR MESA si el pedido es de tipo mesa
            if factura.pedido.tipo_pedido == 'mesa' and factura.pedido.mesa:
                factura.pedido.mesa.estado = 'disponible'
                factura.pedido.mesa.save()
                print(f"✅ Mesa {factura.pedido.mesa.numero_display} liberada")

            # Liberar el código de delivery/para llevar si existe
            if factura.pedido.tipo_pedido in ['delivery', 'llevar'] and factura.pedido.codigo_delivery:
                try:
                    config = DeliveryConfig.objects.get(
                        tipo=factura.pedido.tipo_pedido,
                        codigo=factura.pedido.codigo_delivery
                    )
                    config.estado = 'disponible'
                    config.save()
                    print(
                        f"✅ Código {factura.pedido.codigo_delivery} liberado para {factura.pedido.tipo_pedido}")
                except DeliveryConfig.DoesNotExist:
                    print(
                        f"⚠️ Código {factura.pedido.codigo_delivery} no encontrado en DeliveryConfig")
                except Exception as e:
                    print(f"❌ Error al liberar código: {e}")

            # DESCONTAR BEBIDAS DEL INVENTARIO
            descontar_bebidas_inventario(factura.pedido)

        # Si es una petición AJAX, devolver datos actualizados
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Obtener pedidos y facturas actualizados
            pedidos_con_factura_pagada_ids = list(
                Factura.objects.filter(estado='pagada').values_list(
                    'pedido_id', flat=True)
            )
            pedidos_con_factura_pendiente_ids = list(
                Factura.objects.filter(estado='pendiente').values_list(
                    'pedido_id', flat=True)
            )

            # Obtener pedidos listos para facturar
            pedidos_pendientes = Pedido.objects.filter(
                estado__in=['entregado', 'listo', 'completado']
            ).exclude(
                id__in=pedidos_con_factura_pagada_ids
            ).exclude(
                id__in=pedidos_con_factura_pendiente_ids
            ).select_related('mesa').order_by('-fecha_pedido')

            # Preparar datos para JavaScript
            pedidos_json = []

            for pedido in pedidos_pendientes:
                items_data = []
                try:
                    items = pedido.get_items_detalle()
                    if isinstance(items, list):
                        for item in items:
                            items_data.append({
                                'name': item.get('nombre', item.get('name', 'Producto')),
                                'quantity': item.get('cantidad', item.get('quantity', 1)),
                                'price': float(item.get('precio', item.get('price', 0))),
                                'total': float(item.get('subtotal', item.get('total', 0))),
                            })
                except:
                    items_data = []

                numero_mesa_codigo = ''
                if pedido.tipo_pedido == 'mesa' and pedido.mesa:
                    numero_mesa_codigo = pedido.mesa.numero_display
                elif pedido.codigo_delivery:
                    numero_mesa_codigo = pedido.codigo_delivery

                pedido_dict = {
                    'id': pedido.id,
                    'codigo_pedido': pedido.codigo_pedido,
                    'tipo_pedido': pedido.tipo_pedido,
                    'estado': pedido.estado,
                    'total': float(pedido.total),
                    'mesa': {
                        'id': pedido.mesa.id if pedido.mesa else None,
                        'numero': pedido.mesa.numero if pedido.mesa else None,
                        'numero_display': pedido.mesa.numero_display if pedido.mesa else None,
                    } if pedido.mesa else None,
                    'codigo_delivery': pedido.codigo_delivery or '',
                    'nombre_cliente': pedido.nombre_cliente or '',
                    'telefono_cliente': pedido.telefono_cliente or '',
                    'direccion_entrega': pedido.direccion_entrega or '',
                    'items': items_data,
                    'subtotal': float(pedido.subtotal),
                    'envio': float(pedido.envio),
                    'fecha_pedido': pedido.fecha_pedido.isoformat() if pedido.fecha_pedido else None,
                    'es_factura': False,
                }
                pedidos_json.append(pedido_dict)

            # Añadir facturas pendientes restantes
            facturas_pendientes = Factura.objects.filter(
                estado='pendiente').select_related('pedido').all().order_by('-fecha_factura')
            for factura_pendiente in facturas_pendientes:
                try:
                    items_data = factura_pendiente.get_items_detalle()

                    factura_dict = {
                        'id': f"factura_{factura_pendiente.id}",
                        'codigo_pedido': factura_pendiente.pedido.codigo_pedido if factura_pendiente.pedido else 'N/A',
                        'tipo_pedido': factura_pendiente.tipo_pedido,
                        'estado_factura': factura_pendiente.estado,
                        'estado': 'facturado',
                        'total': float(factura_pendiente.total),
                        'mesa': {
                            'numero_display': factura_pendiente.numero_mesa_codigo or '',
                        } if factura_pendiente.tipo_pedido == 'mesa' else None,
                        'codigo_delivery': factura_pendiente.numero_mesa_codigo if factura_pendiente.tipo_pedido in ['delivery', 'llevar'] else '',
                        'nombre_cliente': factura_pendiente.nombre_cliente or '',
                        'telefono_cliente': factura_pendiente.telefono_cliente or '',
                        'direccion_entrega': factura_pendiente.direccion_entrega or '',
                        'items': items_data,
                        'subtotal': float(factura_pendiente.subtotal),
                        'envio': float(factura_pendiente.envio),
                        'fecha_pedido': factura_pendiente.fecha_factura.isoformat() if factura_pendiente.fecha_factura else None,
                        'es_factura': True,
                        'factura_id': factura_pendiente.id,
                        'numero_factura': factura_pendiente.numero_factura,
                        'metodo_pago': factura_pendiente.metodo_pago,
                    }
                    pedidos_json.append(factura_dict)
                except Exception as e:
                    print(
                        f"Error procesando factura {factura_pendiente.id}: {e}")

            return JsonResponse({
                'success': True,
                'message': f'Factura {factura.numero_factura} marcada como pagada',
                'pedidos_actualizados': pedidos_json,
                'imprimir_url': f'/facturacion/imprimir-termica/{factura.id}/'
            })

        # Si no es AJAX, redirigir a impresión por defecto
        return redirect('imprimir_factura_termica', factura_id=factura.id)

    except Exception as e:
        # Si es AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })

        # Si no es AJAX, mostrar error
        messages.error(request, f'Error: {str(e)}')
        return redirect('facturacion')


@csrf_exempt
@login_required
def eliminar_factura(request, factura_id):
    """Eliminar una factura (solo si es pendiente)"""
    try:
        factura = get_object_or_404(Factura, id=factura_id)

        # Solo permitir eliminar facturas pendientes
        if factura.estado != 'pendiente':
            return JsonResponse({
                'success': False,
                'message': 'Solo se pueden eliminar facturas pendientes'
            })

        # Guardar referencia al pedido
        pedido = factura.pedido

        # Eliminar la factura
        factura.delete()

        # Si el pedido estaba marcado como completado por la factura, volver a un estado anterior
        if pedido and pedido.estado == 'completado':
            pedido.estado = 'entregado'
            pedido.save()

        return JsonResponse({
            'success': True,
            'message': 'Factura pendiente eliminada correctamente'
        })

    except Exception as e:
        print(f"Error al eliminar factura: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@login_required
def detalle_factura(request, factura_id):
    """Ver detalle de una factura específica"""
    factura = get_object_or_404(Factura, id=factura_id)

    context = {
        'factura': factura,
        'items': factura.get_items_detalle(),
    }
    return render(request, 'facturacion/detalle_factura.html', context)


@login_required
def imprimir_factura_termica(request, factura_id):
    """Imprimir factura en formato térmico 80mm con hora local de República Dominicana"""
    # Forzar zona horaria de República Dominicana
    import pytz
    from django.utils import timezone

    # Obtener la zona horaria de República Dominicana
    tz_rd = pytz.timezone('America/Santo_Domingo')

    # Obtener la factura
    factura = get_object_or_404(Factura, id=factura_id)

    # Si la factura no tiene fecha, usar la hora actual en RD
    if not factura.fecha_factura:
        factura.fecha_factura = timezone.now().astimezone(tz_rd)
    else:
        # Convertir la fecha existente a zona horaria de RD
        factura.fecha_factura = factura.fecha_factura.astimezone(tz_rd)

    # Marcar como impresa
    factura.marcar_impresa()

    # Obtener items de la factura
    items_original = factura.get_items_detalle()

    # Normalizar items para tener ambas versiones (español e inglés)
    items_normalizados = []
    for item in items_original:
        # Crear un nuevo diccionario con ambas versiones
        normalized_item = {}

        # Si viene con claves en español, copiar y agregar versiones en inglés
        if 'nombre' in item:
            normalized_item['nombre'] = item['nombre']
            normalized_item['name'] = item['nombre']  # Copia a inglés
        elif 'name' in item:
            normalized_item['name'] = item['name']
            normalized_item['nombre'] = item['name']  # Copia a español

        # Hacer lo mismo para cantidad/quantity
        if 'cantidad' in item:
            normalized_item['cantidad'] = item['cantidad']
            normalized_item['quantity'] = item['cantidad']
        elif 'quantity' in item:
            normalized_item['quantity'] = item['quantity']
            normalized_item['cantidad'] = item['quantity']

        # Hacer lo mismo para precio/price
        if 'precio' in item:
            normalized_item['precio'] = item['precio']
            normalized_item['price'] = item['precio']
        elif 'price' in item:
            normalized_item['price'] = item['price']
            normalized_item['precio'] = item['price']

        # Hacer lo mismo para subtotal/total
        if 'subtotal' in item:
            normalized_item['subtotal'] = item['subtotal']
            normalized_item['total'] = item['subtotal']
        elif 'total' in item:
            normalized_item['total'] = item['total']
            normalized_item['subtotal'] = item['total']

        items_normalizados.append(normalized_item)

    # Preparar datos para la plantilla térmica
    context = {
        'factura': factura,
        'items': items_normalizados,  # Usar los items normalizados
        'empresa': {
            'nombre': '402 FASTFOOD',
            'direccion': 'Av. Principal 30 DE MAYO FRENTE A LA BOMBA',
            'telefono': '849-362-1791',
            'ruc': ''
        }
    }

    return render(request, 'facturacion/imprimir_termica.html', context)


@login_required
def imprimir_factura(request, factura_id):
    """Marcar factura como impresa"""
    factura = get_object_or_404(Factura, id=factura_id)
    factura.marcar_impresa()

    # Redirigir de vuelta a la página de facturación
    return redirect('facturacion')


@login_required
def exportar_facturas(request):
    """Exportar facturas a CSV (simplificado)"""
    # Aquí puedes implementar la exportación a CSV
    # Por ahora solo redirigimos
    return redirect('facturacion')


@csrf_exempt
def salida(request):
    # Obtener productos excluyendo bebidas
    productos = Producto.objects.exclude(categoria='bebida')

    # Preparar datos para la plantilla
    productos_list = []
    for producto in productos:
        productos_list.append({
            'id': producto.id,
            'nombre': producto.nombre,
            'codigo': producto.codigo,
            'categoria': producto.categoria,
            'cantidad': float(producto.cantidad),
            'precio_compra': float(producto.precio_compra),
            'subtotal': float(producto.subtotal),
            'descripcion': f"Código: {producto.codigo} | Precio: ${float(producto.precio_compra):.2f}",
            'fecha_creacion': producto.fecha_creacion.strftime('%Y-%m-%d'),
        })

    # Calcular estadísticas
    total_productos = productos.count()
    total_cantidad = productos.aggregate(total=Sum('cantidad'))['total'] or 0

    productos_bajos = productos.filter(
        cantidad__lt=10
    ).count()

    # Obtener salidas de hoy (necesitarías un modelo para registrar salidas)
    context = {
        'productos_list': productos_list,  # Pasar productos al contexto
        'productos_json': json.dumps(productos_list),  # Para JavaScript
        'total_productos': total_productos,
        'total_cantidad': total_cantidad,
        'productos_bajos': productos_bajos,
    }
    return render(request, 'facturacion/salida.html', context)


@csrf_exempt
def obtener_productos_salida(request):
    """Obtener todos los productos excluyendo bebidas para la página de salida"""
    if request.method == 'GET':
        try:
            # Obtener productos excluyendo bebidas
            productos = Producto.objects.exclude(categoria='bebida')

            # Formatear los datos para JSON
            productos_data = []
            for producto in productos:
                productos_data.append({
                    'id': producto.id,
                    'nombre': producto.nombre,
                    'codigo': producto.codigo,
                    'categoria': producto.categoria,
                    'cantidad': float(producto.cantidad),
                    'precio_compra': float(producto.precio_compra),
                    'subtotal': float(producto.subtotal),
                    'fecha_creacion': producto.fecha_creacion.strftime('%Y-%m-%d'),
                    'ultima_salida': None  # Necesitarías un campo para esto
                })

            return JsonResponse({
                'success': True,
                'productos': productos_data
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@csrf_exempt
def registrar_salida(request):
    """Registrar una salida de producto"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            producto_id = data.get('producto_id')
            cantidad = Decimal(str(data.get('cantidad'))
                               )  # Convertir a Decimal
            motivo = data.get('motivo')
            responsable = data.get('responsable')
            observaciones = data.get('observaciones')

            # Obtener el producto
            producto = get_object_or_404(Producto, id=producto_id)

            # Verificar que no sea bebida
            if producto.categoria == 'bebida':
                return JsonResponse({
                    'success': False,
                    'error': 'No se puede registrar salida de bebidas'
                })

            # Verificar que haya suficiente cantidad
            if producto.cantidad < cantidad:
                return JsonResponse({
                    'success': False,
                    'error': f'No hay suficiente stock. Solo hay {producto.cantidad} unidades disponibles'
                })

            # Actualizar la cantidad del producto
            producto.cantidad -= cantidad
            producto.save()

            # Aquí podrías crear un registro en un modelo de Salida si lo tienes
            # Ejemplo: SalidaProducto.objects.create(...)

            return JsonResponse({
                'success': True,
                'nueva_cantidad': float(producto.cantidad),
                'message': f'Salida registrada: {cantidad} {get_unidad_medida(producto.categoria)} de {producto.nombre}'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@csrf_exempt
def reabastecer_producto(request):
    """Reabastecer un producto"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            producto_id = data.get('producto_id')
            cantidad = Decimal(str(data.get('cantidad'))
                               )  # Convertir a Decimal
            motivo = data.get('motivo')
            observaciones = data.get('observaciones')

            producto = get_object_or_404(Producto, id=producto_id)

            # Actualizar la cantidad
            producto.cantidad += cantidad
            producto.save()

            return JsonResponse({
                'success': True,
                'nueva_cantidad': float(producto.cantidad),
                'message': f'Reabastecimiento registrado: {cantidad} {get_unidad_medida(producto.categoria)} de {producto.nombre}'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


def get_unidad_medida(categoria):
    """Función auxiliar para obtener la unidad de medida"""
    unidades = {
        'carne': 'kg',
        'verdura': 'kg',
        'lacteo': 'lt',
        'postre': 'unid',
        'bebida': 'lt',
        'otro': 'unid'
    }
    return unidades.get(categoria, 'unid')


@login_required
@permission_required('auth.change_user', raise_exception=True)
@never_cache
@ensure_csrf_cookie
@csrf_protect
def roles(request):
    """
    Vista de gestión de roles y permisos
    """
    # Inicializar permisos personalizados
    inicializar_permisos()

    # Obtener todos los usuarios
    users = User.objects.all()

    # Crear grupos por defecto si no existen
    grupos_por_defecto = [
        ('Administrador', 'Tiene acceso completo al sistema'),
        ('Gerente', 'Gestiona operaciones del restaurante'),
        ('Cajero', 'Maneja facturación y pagos'),
        ('Mesero', 'Toma pedidos y atiende mesas'),
        ('Cocinero', 'Prepara pedidos en cocina'),
        ('Usuario Normal', 'Acceso a inventario, facturación y pedidos'),
    ]

    for nombre, descripcion in grupos_por_defecto:
        Group.objects.get_or_create(name=nombre)

    # Obtener todos los grupos para mostrar en el formulario
    groups = Group.objects.all()

    # Obtener permisos personalizados para los módulos específicos
    permisos_modulos = Permission.objects.filter(
        codename__in=[
            'access_inventario',
            'access_facturacion',
            'access_pedidos',
            'access_gestion_pedidos'
        ]
    )

    if request.method == 'POST':
        if 'crear_usuario' in request.POST:
            # Crear nuevo usuario
            username = request.POST.get('username')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirmPassword')
            group_id = request.POST.get('role')
            status = request.POST.get('status')

            # Validaciones
            if not username or not password or not confirm_password or not group_id:
                messages.error(
                    request, 'Por favor complete todos los campos obligatorios')
                return redirect('roles')

            if password != confirm_password:
                messages.error(request, 'Las contraseñas no coinciden')
                return redirect('roles')

            if User.objects.filter(username=username).exists():
                messages.error(request, 'El nombre de usuario ya existe')
                return redirect('roles')

            if len(password) < 4:
                messages.error(
                    request, 'La contraseña debe tener al menos 4 caracteres')
                return redirect('roles')

            try:
                with transaction.atomic():
                    # Crear usuario
                    user = User.objects.create_user(
                        username=username,
                        password=password,
                        is_active=(status == 'active')
                    )

                    # Asignar grupo
                    group = Group.objects.get(id=group_id)
                    user.groups.add(group)

                    # Si es "Usuario Normal", asignar permisos específicos
                    if group.name == 'Usuario Normal':
                        # Asignar permisos para los 4 módulos
                        for perm in permisos_modulos:
                            user.user_permissions.add(perm)

                    messages.success(
                        request, f'Usuario {username} creado exitosamente')

            except Exception as e:
                messages.error(request, f'Error al crear usuario: {str(e)}')

            return redirect('roles')

    context = {
        'users': users,
        'groups': groups,
        'permisos_modulos': permisos_modulos,
    }
    return render(request, 'facturacion/roles.html', context)


@login_required
@permission_required('auth.change_user', raise_exception=True)
def edit_user(request, user_id):
    """
    Vista para editar usuario existente
    """
    try:
        user = User.objects.get(id=user_id)

        if request.method == 'POST':
            username = request.POST.get('editUsername')
            group_id = request.POST.get('editRole')
            status = request.POST.get('editStatus')

            # Actualizar datos básicos
            user.username = username
            user.is_active = (status == 'active')

            # Obtener grupo
            group = Group.objects.get(id=group_id)

            # Actualizar grupos (remover todos y agregar el nuevo)
            user.groups.clear()
            user.groups.add(group)

            # Obtener permisos de módulos
            permisos_modulos = Permission.objects.filter(
                codename__in=[
                    'access_inventario',
                    'access_facturacion',
                    'access_pedidos',
                    'access_gestion_pedidos'
                ]
            )

            # Limpiar permisos personalizados
            for perm in permisos_modulos:
                user.user_permissions.remove(perm)

            # Si es "Usuario Normal", asignar permisos específicos
            if group.name == 'Usuario Normal':
                for perm in permisos_modulos:
                    user.user_permissions.add(perm)

            user.save()
            messages.success(
                request, f'Usuario {username} actualizado exitosamente')
            return redirect('roles')

    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('roles')

    except Exception as e:
        messages.error(request, f'Error al actualizar usuario: {str(e)}')
        return redirect('roles')


@login_required
@permission_required('auth.delete_user', raise_exception=True)
def delete_user(request, user_id):
    """
    Vista para eliminar usuario
    """
    try:
        user = User.objects.get(id=user_id)
        username = user.username

        # No permitir eliminar al propio usuario o superusuarios
        if user == request.user:
            messages.error(request, 'No puedes eliminar tu propio usuario')
        elif user.is_superuser:
            messages.error(request, 'No puedes eliminar un superusuario')
        else:
            user.delete()
            messages.success(
                request, f'Usuario {username} eliminado exitosamente')

    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')

    except Exception as e:
        messages.error(request, f'Error al eliminar usuario: {str(e)}')

    return redirect('roles')


def verificar_acceso_modulo(user, modulo):
    """
    Verifica si un usuario tiene acceso a un módulo específico
    """
    # Superusuarios tienen acceso completo
    if user.is_superuser:
        return True

    # Mapeo de módulos a grupos permitidos
    grupos_por_modulo = {
        # Módulos específicos para Usuario Normal
        'inventario': ['Usuario Normal', 'Administrador', 'Gerente'],
        'pedidos': ['Usuario Normal', 'Administrador', 'Gerente', 'Cajero', 'Mesero'],
        'gestiondepedidos': ['Usuario Normal', 'Administrador', 'Gerente', 'Cocinero'],
        'facturacion': ['Usuario Normal', 'Administrador', 'Gerente', 'Cajero'],
        'salida': ['Usuario Normal', 'Administrador', 'Gerente'],

        # Módulos solo para ciertos grupos (no Usuario Normal)
        'entradadeproductos': ['Administrador', 'Gerente'],
        'entradadeplatillos': ['Administrador', 'Gerente'],
        'listadeplatillos': ['Administrador', 'Gerente'],
        # Solo administradores pueden gestionar usuarios
        'roles': ['Administrador'],
    }

    # Verificar si el módulo existe en el mapeo
    if modulo not in grupos_por_modulo:
        return False

    # Verificar si el usuario pertenece a algún grupo permitido
    grupos_permitidos = grupos_por_modulo[modulo]
    return user.groups.filter(name__in=grupos_permitidos).exists()

# Decorador personalizado para verificar acceso


def acceso_modulo_requerido(modulo):
    """
    Decorador para verificar acceso a un módulo
    """
    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if verificar_acceso_modulo(request.user, modulo):
                return view_func(request, *args, **kwargs)
            else:
                messages.error(
                    request, 'No tienes permiso para acceder a este módulo')
                return redirect('index')
        return wrapper
    return decorator


def calcular_costo_real_facturas(facturas_queryset, include_stats=False):
    """Calcula costo real (cantidad vendida x precio de compra) usando los items facturados."""
    costo_total = Decimal('0.00')
    stats = {
        'items_validos': 0,
        'items_mapeados': 0,
        'items_no_mapeados': 0,
    }

    productos = Producto.objects.only(
        'id', 'codigo', 'nombre', 'precio_compra')
    productos_por_id = {producto.id: producto for producto in productos}
    productos_por_codigo = {
        (producto.codigo or '').strip().lower(): producto
        for producto in productos
        if producto.codigo
    }
    productos_por_nombre = {
        (producto.nombre or '').strip().lower(): producto
        for producto in productos
        if producto.nombre
    }

    for factura in facturas_queryset:
        try:
            items = factura.get_items_detalle(enrich_from_db=False)
        except Exception:
            continue

        if not items or not isinstance(items, list):
            continue

        for item in items:
            try:
                cantidad_raw = item.get('quantity', item.get('cantidad', 0))
                cantidad = Decimal(str(cantidad_raw or 0))
            except Exception:
                continue

            if cantidad <= 0:
                continue

            stats['items_validos'] += 1

            producto_db = None

            producto_id = item.get('producto_id') or item.get(
                'product_id') or item.get('id')
            if producto_id is not None:
                try:
                    producto_db = productos_por_id.get(int(producto_id))
                except (TypeError, ValueError):
                    producto_db = None

            if not producto_db:
                codigo = str(item.get('codigo') or item.get(
                    'code') or '').strip().lower()
                if codigo:
                    producto_db = productos_por_codigo.get(codigo)

            if not producto_db:
                nombre = str(item.get('name') or item.get(
                    'nombre') or '').strip().lower()
                if nombre:
                    producto_db = productos_por_nombre.get(nombre)

            if producto_db and producto_db.precio_compra is not None:
                stats['items_mapeados'] += 1
                costo_total += producto_db.precio_compra * cantidad
            else:
                stats['items_no_mapeados'] += 1

    if include_stats:
        return costo_total, stats

    return costo_total


@login_required
def dashbort(request):

    # ── Helpers internos ───────────────────────────────────────────────────
    def _pct(actual, anterior):
        a, b = float(actual or 0), float(anterior or 0)
        if b > 0:
            return ((a - b) / b) * 100
        return 100.0 if a > 0 else 0.0

    def _trend(val):
        return {
            'value':  round(val, 1),
            'icon':   'up' if val > 0 else 'down' if val < 0 else 'neutral',
            'class':  'trend-up' if val > 0 else 'trend-down' if val < 0 else 'trend-neutral',
        }

    # ── Tiempo (forzado a RD) ─────────────────────────────────────────────
    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    hoy_local = ahora_local.date()
    dashboard_debug = bool(settings.DEBUG and request.GET.get('debug') == '1')

    def _aware_rd(fecha, hora):
        return timezone.make_aware(datetime.combine(fecha, hora), tz_rd)

    # ── Cache ──────────────────────────────────────────────────────────────
    if not dashboard_debug:
        bucket = f"{ahora_local.strftime('%Y%m%d%H')}{(ahora_local.minute // 5) * 5:02d}"
        cache_key = f"dashbort:v3:{request.user.id}:{bucket}"
        cached = cache.get(cache_key)
        if cached is not None:
            return render(request, 'facturacion/dashbort.html', cached)

    # ── Definición del día operativo: 6:00 AM → 5:59:59 AM día siguiente ──
    # Esta lógica es fija y no cambia — siempre el mismo rango para cuadre.
    if ahora_local.hour >= 6:
        inicio_dia = _aware_rd(hoy_local, time(6, 0, 0))
        fin_dia = _aware_rd(hoy_local + timedelta(days=1), time(5, 59, 59))
    else:
        inicio_dia = _aware_rd(hoy_local - timedelta(days=1), time(6, 0, 0))
        fin_dia = _aware_rd(hoy_local, time(5, 59, 59))

    inicio_dia_anterior = inicio_dia - timedelta(days=1)
    fin_dia_anterior = fin_dia - timedelta(days=1)

    # ── Mes actual (calendario) ────────────────────────────────────────────
    primer_dia_mes = hoy_local.replace(day=1)
    if hoy_local.month == 12:
        primer_dia_mes_siguiente = hoy_local.replace(
            year=hoy_local.year + 1, month=1, day=1)
    else:
        primer_dia_mes_siguiente = hoy_local.replace(
            month=hoy_local.month + 1, day=1)

    inicio_mes = _aware_rd(primer_dia_mes, time(0, 0, 0))
    fin_mes = _aware_rd(primer_dia_mes_siguiente, time(0, 0, 0))
    # Nota: usamos __lt fin_mes (exclusive) en todas las queries del mes

    # ── Mes anterior ───────────────────────────────────────────────────────
    ultimo_dia_mes_pasado = primer_dia_mes - timedelta(days=1)
    primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
    inicio_mes_pasado = _aware_rd(primer_dia_mes_pasado, time(0, 0, 0))
    fin_mes_pasado = inicio_mes  # exclusive upper bound

    # ── Resúmenes de caja (fuente: MovimientoFinanciero) ───────────────────
    r_dia = _resumen_movimientos_caja(inicio_dia,      fin_dia)
    r_dia_ant = _resumen_movimientos_caja(
        inicio_dia_anterior, fin_dia_anterior)
    r_mes = _resumen_movimientos_caja(inicio_mes,      fin_mes)
    r_mes_ant = _resumen_movimientos_caja(inicio_mes_pasado, fin_mes_pasado)

    venta_dia = r_dia['caja_neta']
    venta_dia_anterior = r_dia_ant['caja_neta']
    venta_mes = r_mes['caja_neta']
    venta_mes_pasado = r_mes_ant['caja_neta']
    gastos_totales = r_mes['egresos_total']
    gastos_mes_pasado = r_mes_ant['egresos_total']
    ganancias_netas = r_mes['caja_neta']
    ganancias_pasadas = r_mes_ant['caja_neta']

    # ── Cards — conteos consolidados en UNA sola query (no 6) ──────────────
    # OPTIMIZACIÓN: Antes: 6 queries de .count()
    #               Después: 2 queries .aggregate() con Case/When
    from django.db.models import Count, Case, When

    conteos_hoy = MovimientoFinanciero.objects.filter(
        fecha_operacion__gte=inicio_dia,
        fecha_operacion__lt=fin_dia,
        estado__in=['ACTIVO', 'INACTIVO'],
    ).aggregate(
        total_facturas=Count(
            Case(When(tipo='INGRESO', origen='VENTA', then=1))),
        total_pagos=Count(
            Case(When(tipo='INGRESO', origen='PAGO_CXC', then=1))),
        total_egresos=Count(
            Case(When(tipo='EGRESO', origen__in=['DEVOLUCION', 'ANULACION'], then=1))),
    )

    conteos_mes = MovimientoFinanciero.objects.filter(
        fecha_operacion__gte=inicio_mes,
        fecha_operacion__lt=fin_mes,
        estado__in=['ACTIVO', 'INACTIVO'],
    ).aggregate(
        total_facturas=Count(
            Case(When(tipo='INGRESO', origen='VENTA', then=1))),
        total_pagos=Count(
            Case(When(tipo='INGRESO', origen='PAGO_CXC', then=1))),
        total_egresos=Count(
            Case(When(tipo='EGRESO', origen__in=['DEVOLUCION', 'ANULACION'], then=1))),
    )

    total_facturas_hoy = conteos_hoy['total_facturas']
    total_facturas_mes = conteos_mes['total_facturas']
    total_pagos_hoy = conteos_hoy['total_pagos']
    total_pagos_mes = conteos_mes['total_pagos']
    total_egresos_hoy = conteos_hoy['total_egresos']
    total_egresos_mes = conteos_mes['total_egresos']

    # ── Pedidos ────────────────────────────────────────────────────────────
    total_pedidos = Pedido.objects.filter(
        fecha_pedido__gte=inicio_dia, fecha_pedido__lt=fin_dia
    ).count()
    total_pedidos_ayer = Pedido.objects.filter(
        fecha_pedido__gte=inicio_dia_anterior, fecha_pedido__lt=fin_dia_anterior
    ).count()

    # ── Clientes activos del mes ───────────────────────────────────────────
    # Contamos clientes del modelo Cliente que tienen facturas pagadas este mes.
    # Fallback: nombres únicos en facturas si no hay modelo Cliente vinculado.
    nuevos_clientes = Cliente.objects.filter(
        fecha_registro__gte=inicio_mes,
        fecha_registro__lt=fin_mes,
        activo=True
    ).count()
    if nuevos_clientes == 0:
        nuevos_clientes = (
            Factura.objects
            .filter(fecha_factura__gte=inicio_mes, fecha_factura__lt=fin_mes, estado='pagada')
            .exclude(nombre_cliente='')
            .values('nombre_cliente').distinct().count()
        )

    nuevos_clientes_mes_pasado = Cliente.objects.filter(
        fecha_registro__gte=inicio_mes_pasado,
        fecha_registro__lt=fin_mes_pasado,
        activo=True
    ).count()
    if nuevos_clientes_mes_pasado == 0:
        nuevos_clientes_mes_pasado = (
            Factura.objects
            .filter(fecha_factura__gte=inicio_mes_pasado, fecha_factura__lt=fin_mes_pasado, estado='pagada')
            .exclude(nombre_cliente='')
            .values('nombre_cliente').distinct().count()
        )

    # ── Actividades recientes ──────────────────────────────────────────────
    actividades_recientes = (
        Factura.objects
        .filter(estado__in=['pagada', 'parcialmente_devuelta'])
        .order_by('-fecha_factura')
        .only('numero_factura', 'fecha_factura', 'nombre_cliente', 'estado', 'total')[:5]
    )

    # ── Productos top del día (desde FacturaDetalle — sin iterar Python) ───
    from django.db.models import Sum as _Sum, FloatField
    from django.db.models.functions import Coalesce as _Coalesce

    facturas_hoy_ids = list(
        Factura.objects.filter(
            fecha_factura__gte=inicio_dia,
            fecha_factura__lt=fin_dia,
            estado__in=['pagada', 'parcialmente_devuelta']
        ).values_list('id', flat=True)
    )

    facturas_ayer_ids = list(
        Factura.objects.filter(
            fecha_factura__gte=inicio_dia_anterior,
            fecha_factura__lt=fin_dia_anterior,
            estado__in=['pagada', 'parcialmente_devuelta']
        ).values_list('id', flat=True)
    )

    # Top hoy desde FacturaDetalle
    productos_hoy_qs = (
        FacturaDetalle.objects
        .filter(factura_id__in=facturas_hoy_ids)
        .values('nombre_producto')
        .annotate(
            cantidad_total=_Sum('cantidad'),
            ingresos_total=_Sum('subtotal'),
        )
        .order_by('-cantidad_total')[:5]
    )

    # Cantidades ayer para tendencia
    productos_ayer_dict = {
        row['nombre_producto']: float(row['cantidad_total'])
        for row in (
            FacturaDetalle.objects
            .filter(factura_id__in=facturas_ayer_ids)
            .values('nombre_producto')
            .annotate(cantidad_total=_Sum('cantidad'))
        )
    }

    productos_top = []
    for row in productos_hoy_qs:
        nombre = row['nombre_producto']
        actual = float(row['cantidad_total'] or 0)
        anterior = productos_ayer_dict.get(nombre, 0)
        cambio = _pct(actual, anterior)
        productos_top.append({
            'nombre':      nombre,
            'cantidad':    actual,
            'ingresos':    float(row['ingresos_total'] or 0),
            'trend_pct':   round(abs(cambio), 1),
            'trend_icon':  'up' if cambio > 0 else 'down' if cambio < 0 else 'neutral',
            'trend_class': 'trend-up' if cambio > 0 else 'trend-down' if cambio < 0 else 'trend-neutral',
        })

    # ── Gráfico ventas últimos 7 días (OPTIMIZADO: 1 query en lugar de 7) ──
    fecha_hace_7 = _aware_rd(hoy_local - timedelta(days=6), time(6, 0, 0))

    movimientos_7_dias = (
        MovimientoFinanciero.objects
        .filter(fecha_operacion__gte=fecha_hace_7, fecha_operacion__lt=fin_dia, estado='ACTIVO')
        .annotate(fecha_dia=TruncDate('fecha_operacion'))
        .values('fecha_dia')
        .annotate(
            ingresos=Coalesce(Sum(Case(When(tipo='INGRESO', then='monto'), default=Decimal(
                '0.00'), output_field=DecimalField())), Decimal('0.00')),
            egresos=Coalesce(Sum(Case(When(tipo='EGRESO', then='monto'), default=Decimal(
                '0.00'), output_field=DecimalField())), Decimal('0.00')),
        )
        .order_by('fecha_dia')
    )

    neto_por_dia_7 = {row['fecha_dia']: row['ingresos'] -
                      row['egresos'] for row in movimientos_7_dias}

    ultimos_7_dias = []
    ventas_7_dias = []
    for i in range(6, -1, -1):
        ref = hoy_local - timedelta(days=i)
        neto = neto_por_dia_7.get(ref, Decimal('0.00'))
        ultimos_7_dias.append('Hoy' if i == 0 else ref.strftime('%a'))
        ventas_7_dias.append(float(neto))

    # ── Gráfico categorías del día (desde FacturaDetalle + Plato) ─────────
    # Resolvemos categoría desde Plato por nombre (join eficiente en memoria)
    plato_cat = {
        nombre.strip().lower(): cat.strip().lower()
        for nombre, cat in Plato.objects.values_list('nombre', 'categoria')
        if nombre
    }
    producto_cat = {
        nombre.strip().lower(): cat.strip().lower()
        for nombre, cat in Producto.objects.values_list('nombre', 'categoria')
        if nombre
    }
    CATEGORIA_LABELS = {
        'entrada': 'Entrada', 'principal': 'Plato Principal',
        'postre': 'Postre', 'bebida': 'Bebida', 'carne': 'Carne',
        'verdura': 'Verdura', 'lacteo': 'Lácteo', 'rapida': 'Comida Rápida',
        'especial': 'Especial', 'otro': 'Otro',
    }

    detalles_hoy = (
        FacturaDetalle.objects
        .filter(factura_id__in=facturas_hoy_ids)
        .values('nombre_producto')
        .annotate(ingreso=_Sum('subtotal'))
    )

    # Si no hay facturas hoy, usar el mes
    if not facturas_hoy_ids:
        facturas_mes_ids = list(
            Factura.objects.filter(
                fecha_factura__gte=inicio_mes,
                fecha_factura__lt=fin_mes,
                estado__in=['pagada', 'parcialmente_devuelta']
            ).values_list('id', flat=True)
        )
        detalles_hoy = (
            FacturaDetalle.objects
            .filter(factura_id__in=facturas_mes_ids)
            .values('nombre_producto')
            .annotate(ingreso=_Sum('subtotal'))
        )

    cat_acumulado = {}
    for row in detalles_hoy:
        nombre_lower = (row['nombre_producto'] or '').strip().lower()
        cat = (
            plato_cat.get(nombre_lower) or
            producto_cat.get(nombre_lower) or
            'otro'
        )
        cat_acumulado[cat] = cat_acumulado.get(cat, Decimal(
            '0.00')) + (row['ingreso'] or Decimal('0.00'))

    categorias_data = [CATEGORIA_LABELS.get(
        c, c.title()) for c in cat_acumulado]
    ventas_categorias_data = [float(v) for v in cat_acumulado.values()]

    # ── Gráfico mensual (OPTIMIZADO: 1 query en lugar de 31) ─────────────────
    movimientos_mes = (
        MovimientoFinanciero.objects
        .filter(fecha_operacion__gte=inicio_mes, fecha_operacion__lt=fin_mes, estado='ACTIVO')
        .annotate(fecha_dia=TruncDate('fecha_operacion'))
        .values('fecha_dia')
        .annotate(
            ingresos=Coalesce(Sum(Case(When(tipo='INGRESO', then='monto'), default=Decimal(
                '0.00'), output_field=DecimalField())), Decimal('0.00')),
            egresos=Coalesce(Sum(Case(When(tipo='EGRESO', then='monto'), default=Decimal(
                '0.00'), output_field=DecimalField())), Decimal('0.00')),
        )
        .order_by('fecha_dia')
    )

    neto_por_dia_mes = {row['fecha_dia']: row['ingresos'] -
                        row['egresos'] for row in movimientos_mes}

    labels_mensuales = []
    proyeccion_mensual = []
    for dia in range(1, hoy_local.day + 1):
        fecha_dia = hoy_local.replace(day=dia)
        neto = neto_por_dia_mes.get(fecha_dia, Decimal('0.00'))
        labels_mensuales.append(fecha_dia.strftime('%d %b'))
        proyeccion_mensual.append(float(neto))

    # ── Gráfico anual (últimos 12 meses, desde MovimientoFinanciero) ───────
    meses_ref = []
    ref_mes = primer_dia_mes
    for _ in range(12):
        meses_ref.append(ref_mes)
        ref_mes = (ref_mes - timedelta(days=1)).replace(day=1)
    meses_ref.reverse()

    inicio_12 = _aware_rd(meses_ref[0], time(0, 0, 0))
    fin_12 = fin_mes  # hasta fin del mes actual

    movimientos_12 = (
        MovimientoFinanciero.objects
        .filter(fecha_operacion__gte=inicio_12, fecha_operacion__lt=fin_12, estado='ACTIVO')
        .annotate(
            anio=Func(F('fecha_operacion'), function='YEAR',
                      output_field=IntegerField()),
            mes=Func(F('fecha_operacion'), function='MONTH',
                     output_field=IntegerField()),
        )
        .values('anio', 'mes')
        .annotate(
            ingresos=Coalesce(Sum(Case(When(tipo='INGRESO', then=F('monto')),
                                       default=Value(0), output_field=DecimalField(max_digits=18, decimal_places=2))), Decimal('0.00')),
            egresos=Coalesce(Sum(Case(When(tipo='EGRESO',  then=F('monto')),
                                      default=Value(0), output_field=DecimalField(max_digits=18, decimal_places=2))), Decimal('0.00')),
        )
    )
    neto_por_mes = {
        (row['anio'], row['mes']): row['ingresos'] - row['egresos']
        for row in movimientos_12 if row.get('anio') and row.get('mes')
    }
    MESES_ESP = ['Ene', 'Feb', 'Mar', 'Abr', 'May',
                 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    labels_anuales = [MESES_ESP[m.month - 1] for m in meses_ref]
    proyeccion_anual = [float(neto_por_mes.get(
        (m.year, m.month), Decimal('0.00'))) for m in meses_ref]

    # ── Gráfico horario, método de pago, tipo de pedido (OPTIMIZADO: 2 queries en lugar de 1 full scan + bucle Python) ──
    # Query 1: Agregación por hora
    horarios_agg = (
        MovimientoFinanciero.objects
        .filter(fecha_operacion__gte=inicio_mes, fecha_operacion__lt=fin_mes,
                tipo='INGRESO', estado='ACTIVO')
        .annotate(hora=Extract('fecha_operacion', 'hour'))
        .values('hora')
        .annotate(total=Coalesce(Sum('monto'), Decimal('0.00')))
    )

    horario_totales = {'Mañana': Decimal('0'), 'Mediodía': Decimal(
        '0'), 'Tarde': Decimal('0'), 'Noche': Decimal('0')}
    for row in horarios_agg:
        hora = row['hora'] or 0
        monto = row['total'] or Decimal('0')
        if 6 <= hora <= 11:
            horario_totales['Mañana'] += monto
        elif 12 <= hora <= 16:
            horario_totales['Mediodía'] += monto
        elif 17 <= hora <= 20:
            horario_totales['Tarde'] += monto
        else:
            horario_totales['Noche'] += monto

    # Query 2: Agregación por método de pago (directo en la query)
    metodo_agg = (
        MovimientoFinanciero.objects
        .filter(fecha_operacion__gte=inicio_mes, fecha_operacion__lt=fin_mes,
                tipo='INGRESO', estado='ACTIVO')
        .values('metodo_pago')
        .annotate(total=Coalesce(Sum('monto'), Decimal('0.00')))
    )

    metodo_totales = {'efectivo': Decimal('0'), 'tarjeta': Decimal(
        '0'), 'transferencia': Decimal('0')}
    for row in metodo_agg:
        metodo = (row['metodo_pago'] or '').lower().strip()
        if metodo in metodo_totales:
            metodo_totales[metodo] += row['total'] or Decimal('0')

    # Query 3: Agregación por tipo de pedido (join con factura)
    tipo_pedido_agg = (
        MovimientoFinanciero.objects
        .filter(fecha_operacion__gte=inicio_mes, fecha_operacion__lt=fin_mes,
                tipo='INGRESO', estado='ACTIVO')
        .values('factura__tipo_pedido')
        .annotate(total=Coalesce(Sum('monto'), Decimal('0.00')))
    )

    tipo_pedido_totales = {'mesa': Decimal(
        '0'), 'delivery': Decimal('0'), 'llevar': Decimal('0')}
    for row in tipo_pedido_agg:
        tp = (row['factura__tipo_pedido'] or '').lower().strip()
        if tp in tipo_pedido_totales:
            tipo_pedido_totales[tp] += row['total'] or Decimal('0')

    # ── Costos (para stats de debug) ───────────────────────────────────────
    facturas_mes_qs = Factura.objects.filter(
        fecha_factura__gte=inicio_mes,
        fecha_factura__lt=fin_mes,
        estado__in=['pagada', 'parcialmente_devuelta']
    )
    _, costo_mes_stats = calcular_costo_real_facturas(
        facturas_mes_qs, include_stats=True)

    # ── Trends ─────────────────────────────────────────────────────────────
    t_dia = _trend(_pct(venta_dia,         venta_dia_anterior))
    t_mes = _trend(_pct(venta_mes,          venta_mes_pasado))
    t_gastos = _trend(_pct(gastos_totales,     gastos_mes_pasado))
    t_ganancias = _trend(_pct(ganancias_netas,    ganancias_pasadas))
    t_pedidos = _trend(_pct(total_pedidos,      total_pedidos_ayer))
    t_clientes = _trend(_pct(nuevos_clientes,    nuevos_clientes_mes_pasado))

    # ── Rango visual para la card de cuadre ────────────────────────────────
    rango_dia_inicio = timezone.localtime(
        inicio_dia).strftime('%d/%m/%Y %H:%M')
    rango_dia_fin = timezone.localtime(fin_dia).strftime('%d/%m/%Y %H:%M')

    context = {
        # Cards principales
        'venta_dia':        venta_dia,
        'venta_mes':        venta_mes,
        'gastos_totales':   gastos_totales,
        'ganancias_netas':  ganancias_netas,
        'total_pedidos':    total_pedidos,
        'nuevos_clientes':  nuevos_clientes,

        # Subtítulos de cards
        'total_facturas_hoy':  total_facturas_hoy,
        'total_facturas_mes':  total_facturas_mes,
        'total_pagos_hoy':     total_pagos_hoy,
        'total_pagos_mes':     total_pagos_mes,
        'total_egresos_hoy':   total_egresos_hoy,
        'total_egresos_mes':   total_egresos_mes,

        # Rango del día operativo (siempre igual)
        'rango_dia_inicio':  rango_dia_inicio,
        'rango_dia_fin':     rango_dia_fin,
        'definicion_dia':    '6:00 AM — 5:59 AM (día siguiente)',

        # Actividades
        'actividades':     actividades_recientes,
        'productos_top':   productos_top,

        # Gráficos
        'dias_grafico':                 json.dumps(ultimos_7_dias),
        'ventas_grafico':               json.dumps(ventas_7_dias),
        'categorias_grafico':           json.dumps(categorias_data),
        'ventas_categorias_grafico':    json.dumps(ventas_categorias_data),
        'labels_mensuales_json':        json.dumps(labels_mensuales),
        'proyeccion_mensual_json':      json.dumps(proyeccion_mensual),
        'labels_anuales_json':          json.dumps(labels_anuales),
        'proyeccion_anual_json':        json.dumps(proyeccion_anual),
        'horarios_grafico':             json.dumps(['Mañana', 'Mediodía', 'Tarde', 'Noche']),
        'ventas_horarios_grafico':      json.dumps([float(horario_totales[k]) for k in ['Mañana', 'Mediodía', 'Tarde', 'Noche']]),
        'metodos_pago_grafico':         json.dumps(['Efectivo', 'Tarjeta', 'Transferencia']),
        'ventas_metodos_pago_grafico':  json.dumps([float(metodo_totales['efectivo']), float(metodo_totales['tarjeta']), float(metodo_totales['transferencia'])]),
        'tipos_pedido_grafico':         json.dumps(['Mesa', 'Delivery', 'Llevar']),
        'ventas_tipos_pedido_grafico':  json.dumps([float(tipo_pedido_totales['mesa']), float(tipo_pedido_totales['delivery']), float(tipo_pedido_totales['llevar'])]),

        # Trends
        'trend_venta_dia':       t_dia['value'],
        'trend_venta_dia_icon':  t_dia['icon'],
        'trend_venta_dia_class': t_dia['class'],
        'trend_venta_mes':       t_mes['value'],
        'trend_venta_mes_icon':  t_mes['icon'],
        'trend_venta_mes_class': t_mes['class'],
        'trend_gastos':          t_gastos['value'],
        'trend_gastos_icon':     t_gastos['icon'],
        'trend_gastos_class':    t_gastos['class'],
        'trend_ganancias':       t_ganancias['value'],
        'trend_ganancias_icon':  t_ganancias['icon'],
        'trend_ganancias_class': t_ganancias['class'],
        'trend_pedidos':         t_pedidos['value'],
        'trend_pedidos_icon':    t_pedidos['icon'],
        'trend_pedidos_class':   t_pedidos['class'],
        'trend_clientes':        t_clientes['value'],
        'trend_clientes_icon':   t_clientes['icon'],
        'trend_clientes_class':  t_clientes['class'],

        # Debug / stats
        'fecha_actual':             ahora_local.strftime('%A, %d de %B de %Y'),
        'hora_actual':              ahora_local.strftime('%I:%M:%S'),
        'hoy':                      hoy_local,
        'now_utc':                  timezone.now(),
        'venta_mes_pasado':         venta_mes_pasado,
        'mes_pasado_nombre':        primer_dia_mes_pasado.strftime('%B %Y'),
        'costos_items_validos':     costo_mes_stats['items_validos'],
        'costos_items_mapeados':    costo_mes_stats['items_mapeados'],
        'costos_items_no_mapeados': costo_mes_stats['items_no_mapeados'],
        'dashboard_debug':          dashboard_debug,

        # Datos crudos para diagnóstico en template
        'datos_semana_raw':    list(zip(ultimos_7_dias, ventas_7_dias)),
        'datos_categorias_raw': list(zip(categorias_data, ventas_categorias_data)),
        'datos_mensual_raw':   list(zip(labels_mensuales, proyeccion_mensual)),
        'datos_anual_raw':     list(zip(labels_anuales, proyeccion_anual)),
    }

    if not dashboard_debug:
        cache.set(cache_key, context, 60)

    return render(request, 'facturacion/dashbort.html', context)


@login_required
def dashboard_stats(request):
    """Vista API JSON para actualización en tiempo real del dashboard."""
    try:
        scope = (request.GET.get('scope') or 'full').strip().lower()
        full_refresh = scope == 'full'
        dashboard_debug = bool(
            settings.DEBUG and request.GET.get('debug') == '1')

        # ── Cache ──────────────────────────────────────────────────────────
        tz_rd = pytz.timezone('America/Santo_Domingo')
        ahora_local = timezone.now().astimezone(tz_rd)
        hoy_local = ahora_local.date()

        def _aware_rd(fecha, hora):
            return timezone.make_aware(datetime.combine(fecha, hora), tz_rd)
        if full_refresh:
            bucket = f"{ahora_local.strftime('%Y%m%d%H')}{(ahora_local.minute // 5) * 5:02d}"
        else:
            bucket = f"{ahora_local.strftime('%Y%m%d%H%M')}{(ahora_local.second // 15) * 15:02d}"

        cache_key = f"dashboard_stats:v3:{scope}:{request.user.id}:{bucket}"
        if not dashboard_debug:
            cached = cache.get(cache_key)
            if cached is not None:
                return JsonResponse(cached)

        # ── Helpers ────────────────────────────────────────────────────────
        def _pct(actual, anterior):
            a, b = float(actual or 0), float(anterior or 0)
            if b > 0:
                return ((a - b) / b) * 100
            return 100.0 if a > 0 else 0.0

        def _trend(val):
            return {
                'value':  round(val, 1),
                'icon':   'up' if val > 0 else 'down' if val < 0 else 'neutral',
                'class':  'trend-up' if val > 0 else 'trend-down' if val < 0 else 'trend-neutral',
            }

        # ── Rangos de tiempo ───────────────────────────────────────────────
        if ahora_local.hour >= 6:
            inicio_dia = _aware_rd(hoy_local, time(6, 0, 0))
            fin_dia = _aware_rd(hoy_local + timedelta(days=1), time(5, 59, 59))
        else:
            inicio_dia = _aware_rd(
                hoy_local - timedelta(days=1), time(6, 0, 0))
            fin_dia = _aware_rd(hoy_local, time(5, 59, 59))

        inicio_dia_anterior = inicio_dia - timedelta(days=1)
        fin_dia_anterior = fin_dia - timedelta(days=1)

        primer_dia_mes = hoy_local.replace(day=1)
        if hoy_local.month == 12:
            primer_dia_mes_siguiente = hoy_local.replace(
                year=hoy_local.year + 1, month=1, day=1)
        else:
            primer_dia_mes_siguiente = hoy_local.replace(
                month=hoy_local.month + 1, day=1)

        inicio_mes = _aware_rd(primer_dia_mes, time(0, 0, 0))
        fin_mes = _aware_rd(primer_dia_mes_siguiente, time(0, 0, 0))

        ultimo_dia_mes_pasado = primer_dia_mes - timedelta(days=1)
        primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
        inicio_mes_pasado = _aware_rd(primer_dia_mes_pasado, time(0, 0, 0))
        fin_mes_pasado = inicio_mes

        # ── Resúmenes de caja ──────────────────────────────────────────────
        r_dia = _resumen_movimientos_caja(inicio_dia,     fin_dia)
        r_dia_ant = _resumen_movimientos_caja(
            inicio_dia_anterior, fin_dia_anterior)
        r_mes = _resumen_movimientos_caja(inicio_mes,     fin_mes)
        r_mes_ant = _resumen_movimientos_caja(
            inicio_mes_pasado, fin_mes_pasado)

        venta_dia = r_dia['caja_neta']
        venta_dia_ant = r_dia_ant['caja_neta']
        venta_mes = r_mes['caja_neta']
        venta_mes_ant = r_mes_ant['caja_neta']
        gastos_totales = r_mes['egresos_total']
        gastos_ant = r_mes_ant['egresos_total']
        ganancias_netas = r_mes['caja_neta']
        ganancias_ant = r_mes_ant['caja_neta']

        # Cards conteos consolidados en UNA sola query (no 6)
        conteos_hoy = MovimientoFinanciero.objects.filter(
            fecha_operacion__gte=inicio_dia,
            fecha_operacion__lt=fin_dia,
            estado__in=['ACTIVO', 'INACTIVO'],
        ).aggregate(
            total_facturas=Count(
                Case(When(tipo='INGRESO', origen='VENTA', then=1))),
            total_pagos=Count(
                Case(When(tipo='INGRESO', origen='PAGO_CXC', then=1))),
            total_egresos=Count(
                Case(When(tipo='EGRESO', origen__in=['DEVOLUCION', 'ANULACION'], then=1))),
        )
        conteos_mes = MovimientoFinanciero.objects.filter(
            fecha_operacion__gte=inicio_mes,
            fecha_operacion__lt=fin_mes,
            estado__in=['ACTIVO', 'INACTIVO'],
        ).aggregate(
            total_facturas=Count(
                Case(When(tipo='INGRESO', origen='VENTA', then=1))),
            total_pagos=Count(
                Case(When(tipo='INGRESO', origen='PAGO_CXC', then=1))),
            total_egresos=Count(
                Case(When(tipo='EGRESO', origen__in=['DEVOLUCION', 'ANULACION'], then=1))),
        )

        total_facturas_hoy = conteos_hoy['total_facturas']
        total_facturas_mes = conteos_mes['total_facturas']
        total_pagos_hoy = conteos_hoy['total_pagos']
        total_pagos_mes = conteos_mes['total_pagos']
        total_egresos_hoy = conteos_hoy['total_egresos']
        total_egresos_mes = conteos_mes['total_egresos']

        # Pedidos
        total_pedidos = Pedido.objects.filter(
            fecha_pedido__gte=inicio_dia, fecha_pedido__lt=fin_dia).count()
        total_pedidos_ayer = Pedido.objects.filter(
            fecha_pedido__gte=inicio_dia_anterior, fecha_pedido__lt=fin_dia_anterior).count()

        # Clientes
        nuevos_clientes = Cliente.objects.filter(
            fecha_registro__gte=inicio_mes, fecha_registro__lt=fin_mes, activo=True).count()
        if nuevos_clientes == 0:
            nuevos_clientes = Factura.objects.filter(fecha_factura__gte=inicio_mes, fecha_factura__lt=fin_mes, estado='pagada').exclude(
                nombre_cliente='').values('nombre_cliente').distinct().count()

        nuevos_clientes_ant = Cliente.objects.filter(
            fecha_registro__gte=inicio_mes_pasado, fecha_registro__lt=fin_mes_pasado, activo=True).count()
        if nuevos_clientes_ant == 0:
            nuevos_clientes_ant = Factura.objects.filter(fecha_factura__gte=inicio_mes_pasado, fecha_factura__lt=fin_mes_pasado, estado='pagada').exclude(
                nombre_cliente='').values('nombre_cliente').distinct().count()

        # Trends
        t_dia = _trend(_pct(venta_dia, venta_dia_ant))
        t_mes = _trend(_pct(venta_mes, venta_mes_ant))
        t_gastos = _trend(_pct(gastos_totales, gastos_ant))
        t_ganancias = _trend(_pct(ganancias_netas, ganancias_ant))
        t_pedidos = _trend(_pct(total_pedidos, total_pedidos_ayer))
        t_clientes = _trend(_pct(nuevos_clientes, nuevos_clientes_ant))

        # Actividades recientes
        actividades_recientes = Factura.objects.filter(
            estado__in=['pagada', 'parcialmente_devuelta']
        ).order_by('-fecha_factura').only('numero_factura', 'fecha_factura', 'nombre_cliente', 'estado', 'total')[:5]

        actividades_json = [
            {
                'numero_factura': f.numero_factura,
                'fecha':  timezone.localtime(f.fecha_factura).strftime('%d/%m/%Y %H:%M'),
                'cliente': f.nombre_cliente or 'No especificado',
                'estado':  f.estado,
                'total':   float(f.total or 0),
            }
            for f in actividades_recientes
        ]

        # ── Solo en full_refresh: gráficos y productos top ─────────────────
        productos_top_json = []
        ultimos_7_dias = []
        ventas_7_dias = []
        categorias_data = []
        ventas_categorias_data = []
        labels_mensuales = []
        proyeccion_mensual = []
        labels_anuales = []
        proyeccion_anual = []
        ventas_horarios_data = [0, 0, 0, 0]
        ventas_metodos_data = [0, 0, 0]
        ventas_tipos_pedido_data = [0, 0, 0]

        if full_refresh:
            from django.db.models import Sum as _Sum

            # Productos top desde FacturaDetalle
            fac_hoy_ids = list(Factura.objects.filter(
                fecha_factura__gte=inicio_dia, fecha_factura__lt=fin_dia,
                estado__in=['pagada', 'parcialmente_devuelta']
            ).values_list('id', flat=True))

            fac_ayer_ids = list(Factura.objects.filter(
                fecha_factura__gte=inicio_dia_anterior, fecha_factura__lt=fin_dia_anterior,
                estado__in=['pagada', 'parcialmente_devuelta']
            ).values_list('id', flat=True))

            top_hoy = (
                FacturaDetalle.objects.filter(factura_id__in=fac_hoy_ids)
                .values('nombre_producto')
                .annotate(cant=_Sum('cantidad'), ing=_Sum('subtotal'))
                .order_by('-cant')[:5]
            )
            ayer_dict = {
                row['nombre_producto']: float(row['cant'] or 0)
                for row in FacturaDetalle.objects.filter(factura_id__in=fac_ayer_ids)
                .values('nombre_producto').annotate(cant=_Sum('cantidad'))
            }
            for row in top_hoy:
                nombre = row['nombre_producto']
                actual = float(row['cant'] or 0)
                anterior = ayer_dict.get(nombre, 0)
                cambio = _pct(actual, anterior)
                productos_top_json.append({
                    'nombre':      nombre,
                    'cantidad':    actual,
                    'ingresos':    float(row['ing'] or 0),
                    'trend_pct':   round(abs(cambio), 1),
                    'trend_icon':  'up' if cambio > 0 else 'down' if cambio < 0 else 'neutral',
                    'trend_class': 'trend-up' if cambio > 0 else 'trend-down' if cambio < 0 else 'trend-neutral',
                })

            # Gráfico 7 días
            for i in range(6, -1, -1):
                ref = hoy_local - timedelta(days=i)
                di = _aware_rd(ref, time(6, 0, 0))
                df = _aware_rd(ref + timedelta(days=1), time(5, 59, 59))
                neto = _resumen_movimientos_caja(di, df)['caja_neta']
                ultimos_7_dias.append('Hoy' if i == 0 else ref.strftime('%a'))
                ventas_7_dias.append(float(neto))

            # Categorías desde FacturaDetalle
            plato_cat = {n.strip().lower(): c.strip().lower()
                         for n, c in Plato.objects.values_list('nombre', 'categoria') if n}
            prod_cat = {n.strip().lower(): c.strip().lower(
            ) for n, c in Producto.objects.values_list('nombre', 'categoria') if n}
            CLABELS = {'entrada': 'Entrada', 'principal': 'Plato Principal', 'postre': 'Postre', 'bebida': 'Bebida', 'carne': 'Carne',
                       'verdura': 'Verdura', 'lacteo': 'Lácteo', 'rapida': 'Comida Rápida', 'especial': 'Especial', 'otro': 'Otro'}

            src_ids = fac_hoy_ids or list(Factura.objects.filter(fecha_factura__gte=inicio_mes, fecha_factura__lt=fin_mes, estado__in=[
                                          'pagada', 'parcialmente_devuelta']).values_list('id', flat=True))
            cat_acc = {}
            for row in FacturaDetalle.objects.filter(factura_id__in=src_ids).values('nombre_producto').annotate(ing=_Sum('subtotal')):
                nl = (row['nombre_producto'] or '').strip().lower()
                cat = plato_cat.get(nl) or prod_cat.get(nl) or 'otro'
                cat_acc[cat] = cat_acc.get(cat, 0) + float(row['ing'] or 0)
            categorias_data = [CLABELS.get(c, c.title()) for c in cat_acc]
            ventas_categorias_data = list(cat_acc.values())

            # Gráfico mensual con la MISMA lógica que la card mensual
            for d in range(1, hoy_local.day + 1):
                fd = hoy_local.replace(day=d)
                di = _aware_rd(fd, time(0, 0, 0))
                df = _aware_rd(fd + timedelta(days=1), time(0, 0, 0))
                neto = _resumen_movimientos_caja(di, df)['caja_neta']
                labels_mensuales.append(fd.strftime('%d %b'))
                proyeccion_mensual.append(float(neto))

            # Gráfico anual
            meses_ref = []
            rm = primer_dia_mes
            for _ in range(12):
                meses_ref.append(rm)
                rm = (rm - timedelta(days=1)).replace(day=1)
            meses_ref.reverse()
            inicio_12 = _aware_rd(meses_ref[0], time(0, 0, 0))
            mov_12 = (
                MovimientoFinanciero.objects
                .filter(fecha_operacion__gte=inicio_12, fecha_operacion__lt=fin_mes, estado='ACTIVO')
                .annotate(anio=Func(F('fecha_operacion'), function='YEAR', output_field=IntegerField()), mes=Func(F('fecha_operacion'), function='MONTH', output_field=IntegerField()))
                .values('anio', 'mes')
                .annotate(
                    ing=Coalesce(Sum(Case(When(tipo='INGRESO', then=F('monto')), default=Value(
                        0), output_field=DecimalField(max_digits=18, decimal_places=2))), Decimal('0.00')),
                    egr=Coalesce(Sum(Case(When(tipo='EGRESO',  then=F('monto')), default=Value(
                        0), output_field=DecimalField(max_digits=18, decimal_places=2))), Decimal('0.00')),
                )
            )
            neto_mes = {(r['anio'], r['mes']): r['ing'] - r['egr']
                        for r in mov_12 if r.get('anio') and r.get('mes')}
            MESP = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            labels_anuales = [MESP[m.month - 1] for m in meses_ref]
            proyeccion_anual = [
                float(neto_mes.get((m.year, m.month), Decimal('0.00'))) for m in meses_ref]

            # Horario, método, tipo de pedido
            ht = {'Mañana': 0.0, 'Mediodía': 0.0, 'Tarde': 0.0, 'Noche': 0.0}
            mt = {'efectivo': 0.0, 'tarjeta': 0.0, 'transferencia': 0.0}
            tt = {'mesa': 0.0, 'delivery': 0.0, 'llevar': 0.0}
            for mov in MovimientoFinanciero.objects.filter(
                fecha_operacion__gte=inicio_mes, fecha_operacion__lt=fin_mes,
                tipo='INGRESO', estado='ACTIVO'
            ).select_related('factura').only('fecha_operacion', 'monto', 'metodo_pago', 'factura__tipo_pedido'):
                hora = timezone.localtime(mov.fecha_operacion).hour
                monto = float(mov.monto or 0)
                if 6 <= hora <= 11:
                    ht['Mañana'] += monto
                elif 12 <= hora <= 16:
                    ht['Mediodía'] += monto
                elif 17 <= hora <= 20:
                    ht['Tarde'] += monto
                else:
                    ht['Noche'] += monto
                m = (mov.metodo_pago or '').lower().strip()
                if m in mt:
                    mt[m] += monto
                tp = ((mov.factura.tipo_pedido if mov.factura else '')
                      or '').lower().strip()
                if tp in tt:
                    tt[tp] += monto

            ventas_horarios_data = [ht['Mañana'],
                                    ht['Mediodía'], ht['Tarde'], ht['Noche']]
            ventas_metodos_data = [mt['efectivo'],
                                   mt['tarjeta'], mt['transferencia']]
            ventas_tipos_pedido_data = [
                tt['mesa'], tt['delivery'], tt['llevar']]

        # Costos
        _, costo_stats = calcular_costo_real_facturas(
            Factura.objects.filter(fecha_factura__gte=inicio_mes, fecha_factura__lt=fin_mes, estado__in=[
                                   'pagada', 'parcialmente_devuelta']),
            include_stats=True
        )

        payload = {
            'status': 'success',
            # Cards
            'venta_dia':       float(venta_dia),
            'venta_mes':       float(venta_mes),
            'gastos_totales':  float(gastos_totales),
            'ganancias_netas': float(ganancias_netas),
            'total_pedidos':   total_pedidos,
            'nuevos_clientes': nuevos_clientes,
            # Subtítulos
            'total_facturas_hoy': total_facturas_hoy,
            'total_facturas_mes': total_facturas_mes,
            'total_pagos_hoy':    total_pagos_hoy,
            'total_pagos_mes':    total_pagos_mes,
            'total_egresos_hoy':  total_egresos_hoy,
            'total_egresos_mes':  total_egresos_mes,
            # Trends
            'trend_venta_dia':       t_dia['value'],  'trend_venta_dia_icon':  t_dia['icon'],  'trend_venta_dia_class':  t_dia['class'],
            'trend_venta_mes':       t_mes['value'],  'trend_venta_mes_icon':  t_mes['icon'],  'trend_venta_mes_class':  t_mes['class'],
            'trend_gastos':          t_gastos['value'],   'trend_gastos_icon':     t_gastos['icon'],   'trend_gastos_class':     t_gastos['class'],
            'trend_ganancias':       t_ganancias['value'], 'trend_ganancias_icon':  t_ganancias['icon'], 'trend_ganancias_class':  t_ganancias['class'],
            'trend_pedidos':         t_pedidos['value'],   'trend_pedidos_icon':    t_pedidos['icon'],   'trend_pedidos_class':    t_pedidos['class'],
            'trend_clientes':        t_clientes['value'],  'trend_clientes_icon':   t_clientes['icon'],  'trend_clientes_class':   t_clientes['class'],
            # Gráficos
            'dias_grafico':               ultimos_7_dias,
            'ventas_grafico':             ventas_7_dias,
            'categorias_grafico':         categorias_data,
            'ventas_categorias_grafico':  ventas_categorias_data,
            'labels_mensuales':           labels_mensuales,
            'proyeccion_mensual':         proyeccion_mensual,
            'labels_anuales':             labels_anuales,
            'proyeccion_anual':           proyeccion_anual,
            'horarios_grafico':           ['Mañana', 'Mediodía', 'Tarde', 'Noche'],
            'ventas_horarios_grafico':    ventas_horarios_data,
            'metodos_pago_grafico':       ['Efectivo', 'Tarjeta', 'Transferencia'],
            'ventas_metodos_pago_grafico': ventas_metodos_data,
            'tipos_pedido_grafico':       ['Mesa', 'Delivery', 'Llevar'],
            'ventas_tipos_pedido_grafico': ventas_tipos_pedido_data,
            # Actividades
            'actividades': actividades_json,
            'productos_top': productos_top_json,
            # Meta
            'fecha_actual': ahora_local.strftime('%A, %d de %B de %Y'),
            'hora_actual':  ahora_local.strftime('%H:%M:%S'),
            'costos_items_validos':     costo_stats['items_validos'],
            'costos_items_mapeados':    costo_stats['items_mapeados'],
            'costos_items_no_mapeados': costo_stats['items_no_mapeados'],
        }

        cache_timeout = 300 if full_refresh else 20
        if not dashboard_debug:
            cache.set(cache_key, payload, cache_timeout)

        return JsonResponse(payload)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)})

# ==========================================================================================================
#                                GENERAL PDF CUADRE DE CAJA
# ==========================================================================================================


def _ticket_nueva_pagina(c, alto_pagina):
    c.showPage()
    c.setFont("Helvetica", 8)
    return alto_pagina - 10 * mm


def _ticket_hora_12h(fecha, tz_rd):
    if not fecha:
        return "--:--"
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.utc)
    fecha = fecha.astimezone(tz_rd)
    return fecha.strftime('%I:%M')


def _ticket_ref_corta(valor):
    valor = str(valor or "-")
    return "..." + valor[-8:] if len(valor) > 8 else valor


def _ticket_cliente_corto(valor):
    texto = str(valor or "CLIENTE")
    return texto[:10] + "." if len(texto) > 10 else texto


def draw_tabla_documentos(c, y, ancho_pagina, alto_pagina, titulo, rows, total):
    if not rows:
        return y

    if y < 30 * mm:
        y = _ticket_nueva_pagina(c, alto_pagina)

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(ancho_pagina / 2, y, titulo)
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(5 * mm, y, "FACTURA")
    c.drawString(30 * mm, y, "HORA")
    c.drawString(42 * mm, y, "CLIENTE")
    c.drawRightString(ancho_pagina - 5 * mm, y, "MONTO")
    y -= 4 * mm

    c.setFont("Helvetica", 7)
    for row in rows:
        if y < 25 * mm:
            y = _ticket_nueva_pagina(c, alto_pagina)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(5 * mm, y, "FACTURA")
            c.drawString(30 * mm, y, "HORA")
            c.drawString(42 * mm, y, "CLIENTE")
            c.drawRightString(ancho_pagina - 5 * mm, y, "MONTO")
            y -= 4 * mm
            c.setFont("Helvetica", 7)

        c.drawString(5 * mm, y, f"#{_ticket_ref_corta(row['factura'])}")
        c.drawString(30 * mm, y, row['hora'])
        c.drawString(42 * mm, y, _ticket_cliente_corto(row['cliente']))
        c.drawRightString(ancho_pagina - 5 * mm, y,
                          f"{Decimal(str(row['monto'])):,.2f}")
        y -= 3.5 * mm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(5 * mm, y, "TOTAL:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${Decimal(str(total or 0)):,.2f}")
    y -= 4 * mm

    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 6 * mm
    return y


def draw_tabla_movimientos(c, y, ancho_pagina, alto_pagina, titulo, rows, total):
    if not rows:
        return y

    if y < 30 * mm:
        y = _ticket_nueva_pagina(c, alto_pagina)

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(ancho_pagina / 2, y, titulo)
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(5 * mm, y, "COMP.")
    c.drawString(22 * mm, y, "HORA")
    c.drawString(32 * mm, y, "CLIENTE")
    c.drawRightString(ancho_pagina - 5 * mm, y, "MONTO")
    y -= 4 * mm

    c.setFont("Helvetica", 7)
    for row in rows:
        if y < 25 * mm:
            y = _ticket_nueva_pagina(c, alto_pagina)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(5 * mm, y, "COMP.")
            c.drawString(22 * mm, y, "HORA")
            c.drawString(32 * mm, y, "CLIENTE")
            c.drawRightString(ancho_pagina - 5 * mm, y, "MONTO")
            y -= 4 * mm
            c.setFont("Helvetica", 7)

        c.drawString(5 * mm, y, f"#{_ticket_ref_corta(row['comp'])}")
        c.drawString(22 * mm, y, row['hora'])
        c.drawString(32 * mm, y, _ticket_cliente_corto(row['cliente']))
        c.drawRightString(ancho_pagina - 5 * mm, y,
                          f"{Decimal(str(row['monto'])):,.2f}")
        y -= 3.5 * mm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(5 * mm, y, "TOTAL:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${Decimal(str(total or 0)):,.2f}")
    y -= 4 * mm

    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 6 * mm
    return y


@login_required
def generar_pdf_cuadre_caja(request):
    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    hoy_local = ahora_local.date()

    if ahora_local.hour >= 6:
        inicio_dia = timezone.make_aware(datetime.combine(
            hoy_local, datetime(2000, 1, 1, 6, 0, 0).time()))
        fin_dia = timezone.make_aware(datetime.combine(
            hoy_local + timedelta(days=1), datetime(2000, 1, 1, 5, 59, 59).time()))
    else:
        inicio_dia = timezone.make_aware(datetime.combine(
            hoy_local - timedelta(days=1), datetime(2000, 1, 1, 6, 0, 0).time()))
        fin_dia = timezone.make_aware(datetime.combine(
            hoy_local, datetime(2000, 1, 1, 5, 59, 59).time()))

    periodo_texto = f"{inicio_dia.astimezone(tz_rd).strftime('%d/%m/%Y %H:%M')} - {fin_dia.astimezone(tz_rd).strftime('%d/%m/%Y %H:%M')}"

    credito_q = Q(factura__cuenta_por_cobrar__isnull=False) | Q(
        factura__pedido__notas__contains='TIPO_PAGO_PEDIDO=credito')

    # Para el ticket de cuadre se muestran TODOS los movimientos con monto
    # (activos e inactivos) para mantener trazabilidad completa del turno.
    # Solo se excluyen ajustes manuales revertidos.
    movimientos = MovimientoFinanciero.objects.filter(
        fecha_operacion__gte=inicio_dia,
        fecha_operacion__lt=fin_dia,
        estado__in=['ACTIVO', 'INACTIVO'],
    )

    ingreso_venta_contado_qs = movimientos.filter(tipo='INGRESO', origen='VENTA').exclude(
        credito_q
    )
    ingreso_venta_credito_qs = movimientos.filter(
        tipo='INGRESO', origen='VENTA').filter(credito_q)
    ingreso_pago_credito_qs = movimientos.filter(
        tipo='INGRESO', origen='PAGO_CXC')
    egreso_devolucion_contado_qs = movimientos.filter(
        tipo='EGRESO', origen='DEVOLUCION').exclude(referencia='EXCEDENTE_DEVOLUCION')
    egreso_excedente_qs = movimientos.filter(
        tipo='EGRESO', origen='DEVOLUCION', referencia='EXCEDENTE_DEVOLUCION')
    egreso_anulacion_qs = movimientos.filter(tipo='EGRESO', origen='ANULACION')

    total_ingreso_venta_contado = ingreso_venta_contado_qs.aggregate(
        total=Sum('monto'))['total'] or Decimal('0.00')
    total_ingreso_venta_credito = ingreso_venta_credito_qs.aggregate(
        total=Sum('monto'))['total'] or Decimal('0.00')
    total_ingreso_pago_credito = ingreso_pago_credito_qs.aggregate(
        total=Sum('monto'))['total'] or Decimal('0.00')
    total_egreso_devolucion_contado = egreso_devolucion_contado_qs.aggregate(
        total=Sum('monto'))['total'] or Decimal('0.00')
    total_egreso_excedente = egreso_excedente_qs.aggregate(
        total=Sum('monto'))['total'] or Decimal('0.00')
    total_egreso_anulacion = egreso_anulacion_qs.aggregate(
        total=Sum('monto'))['total'] or Decimal('0.00')

    total_ventas_contado = total_ingreso_venta_contado
    total_ventas_credito = total_ingreso_venta_credito
    total_anulaciones_doc = total_egreso_anulacion
    total_devoluciones_doc = total_egreso_devolucion_contado + total_egreso_excedente

    total_ingresos = total_ingreso_venta_contado + total_ingreso_pago_credito
    total_egresos = total_egreso_devolucion_contado + \
        total_egreso_excedente + total_egreso_anulacion
    caja_neta = total_ingresos - total_egresos

    rows_ventas_contado = []
    for mov in ingreso_venta_contado_qs.select_related('factura').order_by('fecha_operacion'):
        factura = mov.factura
        rows_ventas_contado.append({
            'factura': factura.numero_factura if factura else (mov.referencia or '-'),
            'hora': _ticket_hora_12h(mov.fecha_operacion, tz_rd),
            'cliente': (factura.nombre_cliente if factura else 'CLIENTE') or 'CLIENTE',
            'monto': mov.monto or Decimal('0.00'),
        })

    rows_ventas_credito = []
    for mov in ingreso_venta_credito_qs.select_related('factura').order_by('fecha_operacion'):
        factura = mov.factura
        rows_ventas_credito.append({
            'factura': factura.numero_factura if factura else (mov.referencia or '-'),
            'hora': _ticket_hora_12h(mov.fecha_operacion, tz_rd),
            'cliente': (factura.nombre_cliente if factura else 'CLIENTE') or 'CLIENTE',
            'monto': mov.monto or Decimal('0.00'),
        })

    rows_devoluciones = []
    for mov in egreso_devolucion_contado_qs.select_related('factura').order_by('fecha_operacion'):
        factura = mov.factura
        rows_devoluciones.append({
            'factura': factura.numero_factura if factura else (mov.referencia or '-'),
            'hora': _ticket_hora_12h(mov.fecha_operacion, tz_rd),
            'cliente': (factura.nombre_cliente if factura else 'CLIENTE') or 'CLIENTE',
            'monto': mov.monto or Decimal('0.00'),
        })

    rows_anulaciones = []
    for mov in egreso_anulacion_qs.select_related('factura').order_by('fecha_operacion'):
        factura = mov.factura
        rows_anulaciones.append({
            'factura': factura.numero_factura if factura else (mov.referencia or '-'),
            'hora': _ticket_hora_12h(mov.fecha_operacion, tz_rd),
            'cliente': (factura.nombre_cliente if factura else 'CLIENTE') or 'CLIENTE',
            'monto': mov.monto or Decimal('0.00'),
        })

    rows_pagos = []
    for pago in PagoCuentaCobrar.objects.filter(fecha_pago__gte=inicio_dia, fecha_pago__lte=fin_dia).select_related('cuenta_por_cobrar__cliente').order_by('fecha_pago'):
        cliente_obj = pago.cuenta_por_cobrar.cliente if pago.cuenta_por_cobrar and hasattr(
            pago.cuenta_por_cobrar, 'cliente') else None
        nombre_cliente = (
            getattr(cliente_obj, 'razon_social', None)
            or getattr(cliente_obj, 'nombre_completo', None)
            or str(cliente_obj)
            if cliente_obj else 'CLIENTE'
        )
        rows_pagos.append({
            'comp': pago.numero_comprobante or '-',
            'hora': _ticket_hora_12h(pago.fecha_pago, tz_rd),
            'cliente': nombre_cliente,
            'monto': pago.monto or Decimal('0.00'),
        })

    rows_excedentes = []
    for mov in egreso_excedente_qs.select_related('factura').order_by('fecha_operacion'):
        factura = mov.factura
        rows_excedentes.append({
            'comp': (factura.numero_factura if factura else mov.referencia or '-'),
            'hora': _ticket_hora_12h(mov.fecha_operacion, tz_rd),
            'cliente': (factura.nombre_cliente if factura else 'CLIENTE') or 'CLIENTE',
            'monto': mov.monto or Decimal('0.00'),
        })

    buffer = io.BytesIO()
    ancho_pagina = 80 * mm
    alto_pagina = 297 * mm
    c = canvas.Canvas(buffer, pagesize=(ancho_pagina, alto_pagina))
    c.setFont("Helvetica", 8)
    y = alto_pagina - 10 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho_pagina / 2, y, "404 FASTFOOD")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(ancho_pagina / 2, y, "CUADRE DE CAJA")
    y -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(5 * mm, y, "Fecha/Hora:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      ahora_local.strftime('%d/%m/%Y %I:%M'))
    y -= 4 * mm
    c.drawString(5 * mm, y, "Periodo:")
    c.drawRightString(ancho_pagina - 5 * mm, y, periodo_texto)
    y -= 5 * mm
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 4 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(ancho_pagina / 2, y, "INFORMACION")
    y -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(5 * mm, y, "Ventas contado:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_ventas_contado:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Ventas credito:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_ventas_credito:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Anulaciones:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_anulaciones_doc:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Devoluciones (visual):")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_devoluciones_doc:,.2f}")
    y -= 5 * mm
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 5 * mm

    y = draw_tabla_documentos(c, y, ancho_pagina, alto_pagina,
                              "VENTAS CONTADO", rows_ventas_contado, total_ventas_contado)
    y = draw_tabla_documentos(c, y, ancho_pagina, alto_pagina,
                              "VENTAS CREDITO", rows_ventas_credito, total_ventas_credito)
    y = draw_tabla_documentos(c, y, ancho_pagina, alto_pagina, "DEVOLUCIONES",
                              rows_devoluciones, total_egreso_devolucion_contado)
    y = draw_tabla_documentos(c, y, ancho_pagina, alto_pagina,
                              "ANULACIONES", rows_anulaciones, total_anulaciones_doc)

    y = draw_tabla_movimientos(c, y, ancho_pagina, alto_pagina,
                               "PAGOS DE CUENTAS POR COBRAR", rows_pagos, total_ingreso_pago_credito)
    y = draw_tabla_movimientos(c, y, ancho_pagina, alto_pagina,
                               "EXCEDENTES", rows_excedentes, total_egreso_excedente)

    if y < 50 * mm:
        y = _ticket_nueva_pagina(c, alto_pagina)

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(ancho_pagina / 2, y, "CAJA REAL")
    y -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(5 * mm, y, "Ingreso venta contado:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_ingreso_venta_contado:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Ingreso pago credito:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_ingreso_pago_credito:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Egreso devolucion contado:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_egreso_devolucion_contado:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Egreso excedente:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_egreso_excedente:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Egreso anulacion:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      f"RD${total_egreso_anulacion:,.2f}")
    y -= 4 * mm
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 3.5 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(5 * mm, y, "Total ingresos:")
    c.drawRightString(ancho_pagina - 5 * mm, y, f"RD${total_ingresos:,.2f}")
    y -= 3.5 * mm
    c.drawString(5 * mm, y, "Total egresos:")
    c.drawRightString(ancho_pagina - 5 * mm, y, f"RD${total_egresos:,.2f}")
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(5 * mm, y, "TOTAL EN CAJA:")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(ancho_pagina - 5 * mm, y, f"RD${caja_neta:,.2f}")
    y -= 6 * mm
    c.setLineWidth(0.8)
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 1.5 * mm
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    c.setLineWidth(1)
    y -= 6 * mm

    if y < 20 * mm:
        y = _ticket_nueva_pagina(c, alto_pagina)

    c.setFont("Helvetica", 8)
    c.drawCentredString(ancho_pagina / 2, y, "*** GRACIAS POR SU VISITA ***")

    c.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response[
        'Content-Disposition'] = f"inline; filename=\"cuadre_caja_{ahora_local.strftime('%Y%m%d_%H%M')}.pdf\""
    return response


@login_required
def generar_pdf_ticket_dia(request):
    return generar_pdf_cuadre_caja(request)

# ==========================================================================================================
#                         PRODUCTOS VENDIDOS EN EL DÍA Y REPORTE DE PRODUCTOS VENDIDOS
# ==========================================================================================================


@login_required
def productos_vendidos_dia(request):
    """Vista para mostrar los productos vendidos en el día"""
    # Obtener hora local actual
    ahora_local = timezone.localtime()
    hoy_local = ahora_local.date()

    # DEFINICIÓN DEL "DÍA": De 6:00 AM a 5:59 AM del día siguiente
    if ahora_local.hour >= 6:
        inicio_dia = timezone.make_aware(
            datetime.combine(hoy_local, datetime(2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(hoy_local + timedelta(days=1),
                             datetime(2000, 1, 1, 5, 59, 59).time())
        )
    else:
        inicio_dia = timezone.make_aware(
            datetime.combine(hoy_local - timedelta(days=1),
                             datetime(2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(hoy_local, datetime(2000, 1, 1, 5, 59, 59).time())
        )

    # Obtener facturas del período
    facturas_hoy = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia,
        estado='pagada'
    )

    # Obtener productos vendidos en el día
    productos_vendidos = {}

    for factura in facturas_hoy:
        try:
            items = factura.get_items_detalle()
            if items and isinstance(items, list):
                for item in items:
                    nombre = item.get('name', '').strip()
                    if not nombre:
                        nombre = item.get('nombre', '').strip()

                    if not nombre:
                        continue

                    cantidad = float(item.get('quantity', 0))
                    if cantidad <= 0:
                        continue

                    precio = float(item.get('price', 0))

                    if nombre in productos_vendidos:
                        productos_vendidos[nombre]['cantidad'] += cantidad
                        productos_vendidos[nombre]['ingresos'] += Decimal(
                            str(cantidad * precio))
                        # Actualizar precio unitario (promedio)
                        productos_vendidos[nombre]['precio_unitario'] = productos_vendidos[nombre]['ingresos'] / Decimal(
                            str(productos_vendidos[nombre]['cantidad']))
                    else:
                        productos_vendidos[nombre] = {
                            'nombre': nombre,
                            'cantidad': cantidad,
                            'precio_unitario': Decimal(str(precio)),
                            'ingresos': Decimal(str(cantidad * precio))
                        }
        except Exception as e:
            print(
                f"Error procesando items de factura {factura.numero_factura}: {e}")
            continue

    # Ordenar por cantidad descendente
    productos_dia_detalle = sorted(
        productos_vendidos.values(),
        key=lambda x: x['cantidad'],
        reverse=True
    )

    # Calcular totales
    total_unidades = sum([p['cantidad'] for p in productos_dia_detalle])
    total_ventas = sum([p['ingresos'] for p in productos_dia_detalle])

    # Obtener venta del día
    venta_bruta_dia = facturas_hoy.aggregate(total_dia=Sum('total'))[
        'total_dia'] or Decimal('0.00')
    total_devuelto_dia = facturas_hoy.aggregate(
        total_devuelto=Sum('devoluciones__monto_devuelto')
    )['total_devuelto'] or Decimal('0.00')
    venta_dia = venta_bruta_dia - total_devuelto_dia

    context = {
        'productos_dia_detalle': productos_dia_detalle,
        'total_unidades': total_unidades,
        'total_ventas': total_ventas,
        'venta_dia': venta_dia,
        'fecha_actual': ahora_local.strftime('%A, %d de %B de %Y'),
        'hora_actual': ahora_local.strftime('%H:%M:%S'),
        'rango_inicio': inicio_dia,
        'rango_fin': fin_dia,
        'facturas_hoy': facturas_hoy.count(),
        'hoy': hoy_local,
    }

    return render(request, 'facturacion/productos_vendidos_dia.html', context)


@login_required
def reporte_productos_vendidos(request):
    """Vista para mostrar reporte de productos vendidos"""
    # Obtener parámetros de fecha
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Si no se especifican fechas, usar el día actual (de 6:00 a 5:59 del día siguiente)
    if not fecha_inicio or not fecha_fin:
        ahora_local = timezone.localtime()
        hoy_local = ahora_local.date()

        # DEFINICIÓN DEL "DÍA": De 6:00 AM a 5:59 AM del día siguiente
        if ahora_local.hour >= 6:
            fecha_inicio = hoy_local
            fecha_fin = hoy_local + timedelta(days=1)
        else:
            fecha_inicio = hoy_local - timedelta(days=1)
            fecha_fin = hoy_local

    # Convertir fechas string a objetos date
    try:
        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

        # Ajustar horas para el período (6:00 AM a 5:59 AM del día siguiente)
        inicio_dia = timezone.make_aware(
            datetime.combine(fecha_inicio_obj, datetime(
                2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(fecha_fin_obj, datetime(
                2000, 1, 1, 5, 59, 59).time())
        )

    except (ValueError, TypeError):
        # Si hay error en el formato, usar día actual
        ahora_local = timezone.localtime()
        hoy_local = ahora_local.date()

        if ahora_local.hour >= 6:
            fecha_inicio_obj = hoy_local
            fecha_fin_obj = hoy_local + timedelta(days=1)
        else:
            fecha_inicio_obj = hoy_local - timedelta(days=1)
            fecha_fin_obj = hoy_local

        inicio_dia = timezone.make_aware(
            datetime.combine(fecha_inicio_obj, datetime(
                2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(fecha_fin_obj, datetime(
                2000, 1, 1, 5, 59, 59).time())
        )

    # CONSULTA 1: Obtener productos vendidos directamente desde las facturas
    facturas = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia,
        estado='pagada'
    )

    productos_vendidos = {}

    for factura in facturas:
        items = factura.get_items_detalle()

        for item in items:
            nombre = item.get('nombre', '').strip()
            if not nombre:
                continue

            cantidad = float(item.get('cantidad', 0))
            if cantidad <= 0:
                continue

            precio = float(item.get('precio', 0))

            # Buscar producto en la base de datos por nombre o código
            producto_db = None
            producto_id = item.get('producto_id')
            codigo = item.get('codigo', '')

            if producto_id:
                try:
                    producto_db = Producto.objects.filter(
                        id=producto_id).first()
                except:
                    pass

            if not producto_db and codigo:
                try:
                    producto_db = Producto.objects.filter(
                        codigo=codigo).first()
                except:
                    pass

            if not producto_db and nombre:
                try:
                    producto_db = Producto.objects.filter(
                        Q(nombre__iexact=nombre) |
                        Q(nombre__icontains=nombre)
                    ).first()
                except:
                    pass

            # Agregar a productos vendidos
            if nombre in productos_vendidos:
                productos_vendidos[nombre]['cantidad'] += cantidad
                productos_vendidos[nombre]['ingresos'] += Decimal(
                    str(cantidad * precio))
                productos_vendidos[nombre]['precio_unitario'] = productos_vendidos[nombre]['ingresos'] / \
                    Decimal(str(productos_vendidos[nombre]['cantidad']))
                productos_vendidos[nombre]['facturas'].add(
                    factura.numero_factura)
            else:
                productos_vendidos[nombre] = {
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'precio_unitario': Decimal(str(precio)),
                    'ingresos': Decimal(str(cantidad * precio)),
                    'producto_db': producto_db,
                    'categoria': item.get('categoria', 'otro'),
                    'codigo': codigo,
                    'facturas': set([factura.numero_factura])
                }

    # CONSULTA 2: Obtener productos más vendidos por categoría
    productos_por_categoria = {}
    for nombre, datos in productos_vendidos.items():
        categoria = datos['categoria']
        if categoria not in productos_por_categoria:
            productos_por_categoria[categoria] = []

        productos_por_categoria[categoria].append({
            'nombre': nombre,
            'cantidad': datos['cantidad'],
            'precio_unitario': datos['precio_unitario'],
            'ingresos': datos['ingresos']
        })

    # Ordenar por cantidad descendente en cada categoría
    for categoria in productos_por_categoria:
        productos_por_categoria[categoria].sort(
            key=lambda x: x['cantidad'], reverse=True)

    # CONSULTA 3: Totales generales
    total_unidades = sum([p['cantidad'] for p in productos_vendidos.values()])
    total_ventas = sum([p['ingresos'] for p in productos_vendidos.values()])

    # CONSULTA 4: Productos que no se han vendido (en stock)
    productos_stock = Producto.objects.all()
    productos_no_vendidos = []
    for producto in productos_stock:
        if producto.nombre not in productos_vendidos:
            productos_no_vendidos.append({
                'nombre': producto.nombre,
                'codigo': producto.codigo,
                'categoria': producto.get_category_label(),
                'stock': producto.cantidad,
                'precio_compra': producto.precio_compra,
                'subtotal': producto.subtotal
            })

    # Ordenar productos vendidos por cantidad
    productos_dia_detalle = sorted(
        productos_vendidos.values(),
        key=lambda x: x['cantidad'],
        reverse=True
    )

    # Convertir set de facturas a lista
    for producto in productos_dia_detalle:
        producto['facturas'] = list(producto['facturas'])
        producto['num_facturas'] = len(producto['facturas'])

    # Preparar datos para el template
    context = {
        'productos': productos_dia_detalle,
        'productos_por_categoria': productos_por_categoria,
        'productos_no_vendidos': productos_no_vendidos,
        'total_unidades': total_unidades,
        'total_ventas': total_ventas,
        'fecha_inicio': fecha_inicio_obj.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin_obj.strftime('%Y-%m-%d'),
        'periodo_texto': f"{fecha_inicio_obj.strftime('%d/%m/%Y')} 06:00 - {fecha_fin_obj.strftime('%d/%m/%Y')} 05:59",
        'num_facturas': facturas.count(),
        'venta_total_dia': facturas.aggregate(total_dia=Sum('total'))['total_dia'] or Decimal('0.00'),
        'num_productos_distintos': len(productos_dia_detalle),
    }

    return render(request, 'reportes/productos_vendidos.html', context)


@login_required
def reporte_productos_vendidos_json(request):
    """API para obtener productos vendidos en formato JSON"""
    # Parámetros
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    categoria = request.GET.get('categoria')
    limite = int(request.GET.get('limite', 50))

    # Configurar fechas
    if not fecha_inicio or not fecha_fin:
        ahora_local = timezone.localtime()
        hoy_local = ahora_local.date()

        if ahora_local.hour >= 6:
            fecha_inicio_obj = hoy_local
            fecha_fin_obj = hoy_local + timedelta(days=1)
        else:
            fecha_inicio_obj = hoy_local - timedelta(days=1)
            fecha_fin_obj = hoy_local
    else:
        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

    # Ajustar horas para el período
    inicio_dia = timezone.make_aware(
        datetime.combine(fecha_inicio_obj, datetime(
            2000, 1, 1, 6, 0, 0).time())
    )
    fin_dia = timezone.make_aware(
        datetime.combine(fecha_fin_obj, datetime(2000, 1, 1, 5, 59, 59).time())
    )

    # Obtener facturas
    facturas = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia,
        estado='pagada'
    )

    # Procesar productos vendidos
    productos_vendidos = {}

    for factura in facturas:
        items = factura.get_items_detalle()

        for item in items:
            nombre = item.get('nombre', '').strip()
            if not nombre:
                continue

            # Filtrar por categoría si se especifica
            item_categoria = item.get('categoria', 'otro').lower()
            if categoria and categoria != 'todas' and item_categoria != categoria:
                continue

            cantidad = float(item.get('cantidad', 0))
            if cantidad <= 0:
                continue

            precio = float(item.get('precio', 0))

            if nombre in productos_vendidos:
                productos_vendidos[nombre]['cantidad'] += cantidad
                productos_vendidos[nombre]['ingresos'] += Decimal(
                    str(cantidad * precio))
                productos_vendidos[nombre]['precio_unitario'] = productos_vendidos[nombre]['ingresos'] / \
                    Decimal(str(productos_vendidos[nombre]['cantidad']))
            else:
                productos_vendidos[nombre] = {
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'precio_unitario': Decimal(str(precio)),
                    'ingresos': Decimal(str(cantidad * precio)),
                    'categoria': item_categoria,
                    'codigo': item.get('codigo', '')
                }

    # Ordenar y limitar
    productos_lista = sorted(
        productos_vendidos.values(),
        key=lambda x: x['cantidad'],
        reverse=True
    )[:limite]

    # Calcular totales
    total_unidades = sum([p['cantidad'] for p in productos_lista])
    total_ventas = sum([p['ingresos'] for p in productos_lista])

    # Preparar respuesta JSON
    response_data = {
        'success': True,
        'data': {
            'productos': productos_lista,
            'totales': {
                'unidades_vendidas': total_unidades,
                'venta_total': float(total_ventas),
                'num_productos': len(productos_lista)
            },
            'periodo': {
                'inicio': inicio_dia.strftime('%Y-%m-%d %H:%M:%S'),
                'fin': fin_dia.strftime('%Y-%m-%d %H:%M:%S'),
                'texto': f"{fecha_inicio_obj.strftime('%d/%m/%Y')} 06:00 - {fecha_fin_obj.strftime('%d/%m/%Y')} 05:59"
            },
            'filtros': {
                'categoria': categoria or 'todas',
                'limite': limite
            }
        }
    }

    return JsonResponse(response_data)


@login_required
def detalle_producto_vendido(request, producto_nombre):
    """Vista para ver el detalle de ventas de un producto específico"""
    # Obtener parámetros de fecha
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Configurar fechas por defecto (últimos 30 días)
    if not fecha_inicio or not fecha_fin:
        fecha_fin_obj = timezone.localtime().date()
        fecha_inicio_obj = fecha_fin_obj - timedelta(days=30)
    else:
        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

    # Ajustar horas para el período
    inicio_dia = timezone.make_aware(
        datetime.combine(fecha_inicio_obj, datetime(
            2000, 1, 1, 6, 0, 0).time())
    )
    fin_dia = timezone.make_aware(
        datetime.combine(fecha_fin_obj, datetime(2000, 1, 1, 5, 59, 59).time())
    )

    # Obtener todas las facturas en el período
    facturas = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia,
        estado='pagada'
    )

    # Buscar producto en la base de datos
    producto_db = None
    try:
        producto_db = Producto.objects.filter(
            Q(nombre__iexact=producto_nombre) |
            Q(nombre__icontains=producto_nombre) |
            Q(codigo__iexact=producto_nombre)
        ).first()
    except:
        pass

    # Recolectar todas las ventas de este producto
    ventas_producto = []
    total_cantidad = Decimal('0.00')
    total_ingresos = Decimal('0.00')

    for factura in facturas:
        items = factura.get_items_detalle()

        for item in items:
            nombre_item = item.get('nombre', '').strip()
            # Buscar coincidencias (exacta o parcial)
            if (producto_nombre.lower() in nombre_item.lower() or
                nombre_item.lower() in producto_nombre.lower() or
                    (producto_db and producto_db.nombre.lower() in nombre_item.lower())):

                cantidad = Decimal(str(item.get('cantidad', 0)))
                precio = Decimal(str(item.get('precio', 0)))
                subtotal = cantidad * precio

                ventas_producto.append({
                    'factura': factura.numero_factura,
                    'fecha': factura.fecha_factura,
                    'cantidad': cantidad,
                    'precio_unitario': precio,
                    'subtotal': subtotal,
                    'cliente': factura.nombre_cliente or 'Sin nombre',
                    'metodo_pago': factura.get_metodo_pago_display(),
                    'tipo_pedido': factura.tipo_pedido
                })

                total_cantidad += cantidad
                total_ingresos += subtotal

    # Ordenar por fecha
    ventas_producto.sort(key=lambda x: x['fecha'], reverse=True)

    # Calcular estadísticas
    if ventas_producto:
        precios = [v['precio_unitario'] for v in ventas_producto]
        precio_promedio = sum(precios) / len(precios)
        precio_min = min(precios)
        precio_max = max(precios)
    else:
        precio_promedio = Decimal('0.00')
        precio_min = Decimal('0.00')
        precio_max = Decimal('0.00')

    context = {
        'producto_nombre': producto_nombre,
        'producto_db': producto_db,
        'ventas': ventas_producto,
        'total_cantidad': total_cantidad,
        'total_ingresos': total_ingresos,
        'precio_promedio': precio_promedio,
        'precio_min': precio_min,
        'precio_max': precio_max,
        'num_ventas': len(ventas_producto),
        'fecha_inicio': fecha_inicio_obj,
        'fecha_fin': fecha_fin_obj,
        'periodo_dias': (fecha_fin_obj - fecha_inicio_obj).days,
    }

    return render(request, 'reportes/detalle_producto.html', context)


@login_required
def generar_reporte_productos_excel(request):
    """Generar reporte de productos vendidos en formato Excel/CSV"""
    # Obtener parámetros de fecha
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Configurar fechas
    if not fecha_inicio or not fecha_fin:
        ahora_local = timezone.localtime()
        hoy_local = ahora_local.date()

        if ahora_local.hour >= 6:
            fecha_inicio_obj = hoy_local
            fecha_fin_obj = hoy_local + timedelta(days=1)
        else:
            fecha_inicio_obj = hoy_local - timedelta(days=1)
            fecha_fin_obj = hoy_local
    else:
        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

    # Ajustar horas para el período
    inicio_dia = timezone.make_aware(
        datetime.combine(fecha_inicio_obj, datetime(
            2000, 1, 1, 6, 0, 0).time())
    )
    fin_dia = timezone.make_aware(
        datetime.combine(fecha_fin_obj, datetime(2000, 1, 1, 5, 59, 59).time())
    )

    # Obtener facturas
    facturas = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia,
        estado='pagada'
    )

    # Procesar productos vendidos
    productos_vendidos = {}

    for factura in facturas:
        items = factura.get_items_detalle()

        for item in items:
            nombre = item.get('nombre', '').strip()
            if not nombre:
                continue

            cantidad = float(item.get('cantidad', 0))
            if cantidad <= 0:
                continue

            precio = float(item.get('precio', 0))

            if nombre in productos_vendidos:
                productos_vendidos[nombre]['cantidad'] += cantidad
                productos_vendidos[nombre]['ingresos'] += Decimal(
                    str(cantidad * precio))
                productos_vendidos[nombre]['precio_unitario'] = productos_vendidos[nombre]['ingresos'] / \
                    Decimal(str(productos_vendidos[nombre]['cantidad']))
                productos_vendidos[nombre]['facturas'].add(
                    factura.numero_factura)
            else:
                productos_vendidos[nombre] = {
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'precio_unitario': Decimal(str(precio)),
                    'ingresos': Decimal(str(cantidad * precio)),
                    'categoria': item.get('categoria', 'otro'),
                    'codigo': item.get('codigo', ''),
                    'facturas': set([factura.numero_factura])
                }

    # Ordenar por cantidad
    productos_lista = sorted(
        productos_vendidos.values(),
        key=lambda x: x['cantidad'],
        reverse=True
    )

    # Convertir set de facturas a string
    for producto in productos_lista:
        producto['facturas'] = ', '.join(list(producto['facturas'])[
                                         :5])  # Limitar a 5 facturas
        if len(producto['facturas']) > 50:  # Si es muy largo, truncar
            producto['facturas'] = producto['facturas'][:50] + '...'

    # Crear CSV
    import csv

    response = HttpResponse(content_type='text/csv')
    filename = f"productos_vendidos_{fecha_inicio_obj.strftime('%Y%m%d')}_{fecha_fin_obj.strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Escribir encabezados
    writer.writerow(['REPORTE DE PRODUCTOS VENDIDOS'])
    writer.writerow(
        [f'Período: {fecha_inicio_obj.strftime("%d/%m/%Y")} 06:00 - {fecha_fin_obj.strftime("%d/%m/%Y")} 05:59'])
    writer.writerow(
        [f'Generado: {timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")}'])
    writer.writerow([])

    # Escribir encabezados de datos
    writer.writerow(['#', 'PRODUCTO', 'CÓDIGO', 'CATEGORÍA',
                    'CANTIDAD', 'PRECIO UNITARIO', 'INGRESOS', 'FACTURAS'])

    # Escribir datos
    for i, producto in enumerate(productos_lista, 1):
        writer.writerow([
            i,
            producto['nombre'][:50],  # Limitar a 50 caracteres
            producto['codigo'],
            producto['categoria'],
            f"{producto['cantidad']:,.2f}",
            f"${producto['precio_unitario']:,.2f}",
            f"${producto['ingresos']:,.2f}",
            producto['facturas']
        ])

    # Totales
    writer.writerow([])
    total_unidades = sum([p['cantidad'] for p in productos_lista])
    total_ventas = sum([p['ingresos'] for p in productos_lista])

    writer.writerow(['TOTALES:', '', '', '',
                    f'{total_unidades:,.2f}', '', f'${total_ventas:,.2f}', ''])
    writer.writerow(['TOTAL FACTURAS:', '', '', '',
                    facturas.count(), '', '', ''])

    return response


@login_required
def generar_pdf_productos_dia_a4(request):
    """Generar PDF de productos vendidos en el día en formato A4"""
    # Obtener hora local actual
    ahora_local = timezone.localtime()
    hoy_local = ahora_local.date()

    # DEFINICIÓN DEL "DÍA": De 6:00 AM a 5:59 AM del día siguiente
    if ahora_local.hour >= 6:
        inicio_dia = timezone.make_aware(
            datetime.combine(hoy_local, datetime(2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(hoy_local + timedelta(days=1),
                             datetime(2000, 1, 1, 5, 59, 59).time())
        )
        periodo_texto = f"{hoy_local.strftime('%d/%m/%Y')} 06:00 - {(hoy_local + timedelta(days=1)).strftime('%d/%m/%Y')} 05:59"
        periodo_corto = f"{hoy_local.strftime('%d/%m')} 06:00 a {(hoy_local + timedelta(days=1)).strftime('%d/%m')} 06:00"
    else:
        inicio_dia = timezone.make_aware(
            datetime.combine(hoy_local - timedelta(days=1),
                             datetime(2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(hoy_local, datetime(2000, 1, 1, 5, 59, 59).time())
        )
        periodo_texto = f"{(hoy_local - timedelta(days=1)).strftime('%d/%m/%Y')} 06:00 - {hoy_local.strftime('%d/%m/%Y')} 05:59"
        periodo_corto = f"{(hoy_local - timedelta(days=1)).strftime('%d/%m')} 06:00 a {hoy_local.strftime('%d/%m')} 06:00"

    # Obtener facturas del período
    facturas_hoy = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia,
        estado__in=['pagada', 'parcialmente_devuelta']
    ).prefetch_related('detalles')

    venta_bruta_dia = facturas_hoy.aggregate(total_dia=Sum('total'))[
        'total_dia'] or Decimal('0.00')

    total_devuelto_dia = facturas_hoy.aggregate(
        total_devuelto=Sum('devoluciones__monto_devuelto')
    )['total_devuelto'] or Decimal('0.00')

    venta_dia = venta_bruta_dia - total_devuelto_dia

    print(
        f"🔍 DEBUG: Encontradas {facturas_hoy.count()} facturas en el período")
    print(f"🔍 DEBUG: Venta bruta del día: ${venta_bruta_dia}")
    print(f"🔍 DEBUG: Total devuelto del día: ${total_devuelto_dia}")

    # Obtener productos vendidos en el día (neto: venta - devolución)
    productos_vendidos = {}

    for factura in facturas_hoy:
        try:
            vendidos_por_producto = {}

            def _acumular_vendido(nombre, cantidad, ingresos):
                nombre = str(nombre or '').strip()
                if not nombre or nombre.lower() == 'desconocido':
                    return
                cantidad = float(cantidad or 0)
                if cantidad <= 0:
                    return

                key = nombre.lower()
                ingresos = Decimal(str(ingresos or 0))
                if key not in vendidos_por_producto:
                    vendidos_por_producto[key] = {
                        'nombre': nombre,
                        'cantidad': 0.0,
                        'ingresos': Decimal('0.00'),
                    }
                vendidos_por_producto[key]['cantidad'] += cantidad
                vendidos_por_producto[key]['ingresos'] += ingresos

            detalles_reales = list(factura.detalles.all())
            if detalles_reales:
                print(
                    f"🔍 DEBUG: Factura {factura.numero_factura} usando detalle real ({len(detalles_reales)} items)")
                for detalle in detalles_reales:
                    cantidad = float(detalle.cantidad or 0)
                    precio = Decimal(str(detalle.precio_unitario or 0))
                    subtotal_detalle = detalle.subtotal if detalle.subtotal is not None else (
                        Decimal(str(cantidad)) * precio)
                    _acumular_vendido(detalle.nombre_producto,
                                      cantidad, subtotal_detalle)
            else:
                items = factura.get_items_detalle(enrich_from_db=False)
                print(
                    f"🔍 DEBUG: Factura {factura.numero_factura} sin detalle real; usando JSON ({len(items)} items)")
                if items and isinstance(items, list):
                    for item in items:
                        nombre = item.get('nombre', '').strip() or item.get('name', '').strip(
                        ) or item.get('producto', '').strip() or item.get('product', '').strip()

                        cantidad = 0
                        for key_cantidad in ('cantidad', 'quantity', 'qty'):
                            if key_cantidad in item:
                                try:
                                    cantidad = float(item[key_cantidad])
                                    break
                                except (ValueError, TypeError):
                                    pass

                        precio = 0
                        for key_precio in ('precio', 'price', 'unit_price'):
                            if key_precio in item:
                                try:
                                    precio = float(item[key_precio])
                                    break
                                except (ValueError, TypeError):
                                    pass

                        _acumular_vendido(nombre, cantidad,
                                          Decimal(str(cantidad * precio)))

            # Devoluciones por producto de la misma factura
            devueltos_por_producto = {}
            devoluciones = factura.devoluciones.prefetch_related(
                'detalles').all()
            for devolucion in devoluciones:
                detalles_dev = list(devolucion.detalles.all())
                if detalles_dev:
                    for det_dev in detalles_dev:
                        nombre_dev = str(
                            det_dev.nombre_producto or '').strip().lower()
                        if not nombre_dev:
                            continue
                        devueltos_por_producto[nombre_dev] = devueltos_por_producto.get(
                            nombre_dev, 0.0) + float(det_dev.cantidad or 0)
                    continue

                # Fallback legacy JSON de devolución
                if devolucion.productos_devueltos:
                    for prod_dev in devolucion.productos_devueltos:
                        nombre_dev = str(prod_dev.get(
                            'nombre', '')).strip().lower()
                        if not nombre_dev:
                            continue
                        devueltos_por_producto[nombre_dev] = devueltos_por_producto.get(
                            nombre_dev, 0.0) + float(prod_dev.get('cantidad', 0) or 0)

            # Aplicar deducción neta por producto
            for key_prod, data_vendida in vendidos_por_producto.items():
                cantidad_vendida = float(data_vendida['cantidad'] or 0)
                if cantidad_vendida <= 0:
                    continue

                cantidad_devuelta = float(
                    devueltos_por_producto.get(key_prod, 0) or 0)
                cantidad_neta = max(cantidad_vendida - cantidad_devuelta, 0.0)
                if cantidad_neta <= 0:
                    continue

                ingresos_vendidos = Decimal(str(data_vendida['ingresos'] or 0))
                precio_promedio = (ingresos_vendidos / Decimal(str(cantidad_vendida))
                                   ) if cantidad_vendida > 0 else Decimal('0.00')
                ingresos_netos = precio_promedio * Decimal(str(cantidad_neta))

                nombre_mostrar = data_vendida['nombre']
                if nombre_mostrar in productos_vendidos:
                    productos_vendidos[nombre_mostrar]['cantidad'] += cantidad_neta
                    productos_vendidos[nombre_mostrar]['ingresos'] += ingresos_netos
                    productos_vendidos[nombre_mostrar]['precio_unitario'] = (
                        productos_vendidos[nombre_mostrar]['ingresos'] /
                        Decimal(
                            str(productos_vendidos[nombre_mostrar]['cantidad']))
                    )
                else:
                    productos_vendidos[nombre_mostrar] = {
                        'nombre': nombre_mostrar,
                        'cantidad': cantidad_neta,
                        'precio_unitario': precio_promedio,
                        'ingresos': ingresos_netos,
                    }

        except Exception as e:
            print(
                f"❌ ERROR procesando items de factura {factura.numero_factura}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"🔍 DEBUG: Total productos encontrados: {len(productos_vendidos)}")

    # Ordenar por cantidad descendente
    productos_dia_detalle = sorted(
        productos_vendidos.values(),
        key=lambda x: x['cantidad'],
        reverse=True
    )

    # Calcular totales
    total_unidades = sum([p['cantidad'] for p in productos_dia_detalle])
    total_ventas = sum([p['ingresos'] for p in productos_dia_detalle])

    print(f"🔍 DEBUG: Total unidades: {total_unidades}")
    print(f"🔍 DEBUG: Total ventas productos: ${total_ventas}")

    # Crear un buffer para el PDF
    buffer = io.BytesIO()

    # Configurar el tamaño de la página para A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=1,  # Centrado
        spaceAfter=12
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=12,
        alignment=1,
        spaceAfter=6
    )

    normal_style = styles['Normal']

    # Contenido del documento
    story = []

    # 1. LOGO ENCIMA DEL TÍTULO
    try:
        # Buscar el logo en diferentes ubicaciones posibles
        posibles_rutas = [
            os.path.join(settings.STATIC_ROOT or settings.BASE_DIR,
                         'static', 'img', 'fastfood.png'),
            os.path.join(settings.BASE_DIR, 'static', 'img', 'fastfood.png'),
            os.path.join(settings.STATIC_ROOT or settings.BASE_DIR,
                         'img', 'fastfood.png'),
            os.path.join(settings.BASE_DIR, 'img', 'fastfood.png'),
            os.path.join(
                settings.STATIC_ROOT or settings.BASE_DIR, 'fastfood.png'),
        ]

        logo_encontrado = False
        logo_path = None

        for ruta in posibles_rutas:
            if os.path.exists(ruta):
                logo_path = ruta
                logo_encontrado = True
                print(f"✅ Logo encontrado en: {ruta}")
                break

        if logo_encontrado and logo_path:
            # Crear una tabla de una celda para centrar el logo
            logo = Image(logo_path, width=30*mm, height=30*mm)
            # Ancho completo de la página
            logo_table = Table([[logo]], colWidths=[doc.width])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (0, 0), 5),
            ]))
            story.append(logo_table)
            story.append(Spacer(1, 5))
        else:
            print("⚠️ Logo no encontrado. Se mostrará sin logo.")

    except Exception as e:
        print(f"❌ Error al cargar el logo: {e}")
        # Continuar sin logo si hay error

    # 2. TÍTULOS DESPUÉS DEL LOGO
    story.append(Paragraph("404 FASTFOOD", title_style))
    story.append(Paragraph("REPORTE DE PRODUCTOS VENDIDOS", subtitle_style))
    story.append(Paragraph(f"Período: {periodo_corto}", normal_style))
    story.append(
        Paragraph("(De 6:00 AM a 5:59 AM del día siguiente)", normal_style))
    story.append(Spacer(1, 15))

    # Información del reporte
    info_data = [
        ["Fecha De Generación:", ahora_local.strftime('%d/%m/%Y %I:%M:%S')],
        ["Período Del Reporte:", periodo_texto],
        ["Total De Facturas:", str(facturas_hoy.count())],
        ["Venta Total Del Día:", f"RD$ {venta_dia:,.2f}"],
        ["Total De Productos Distintos:", str(len(productos_dia_detalle))],
        ["Total de Undidades Vendidas:", f"{total_unidades:,.2f}"],
    ]

    info_table = Table(info_data, colWidths=[200, 240])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # Tabla de productos vendidos
    if productos_dia_detalle:
        # Encabezados de la tabla
        encabezados = ['#', 'PRODUCTO', 'CANTIDAD',
                       'P. UNITARIO RD$', 'TOTAL RD$']

        # Datos de la tabla
        datos = [encabezados]
        for i, producto in enumerate(productos_dia_detalle, 1):
            datos.append([
                str(i),
                producto['nombre'][:50],  # Limitar a 50 caracteres
                f"{producto['cantidad']:,.2f}",
                f"{producto['precio_unitario']:,.2f}",
                f"{producto['ingresos']:,.2f}"
            ])

        # Crear tabla
        tabla = Table(datos, colWidths=[30, 230, 60, 95, 90])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

            # Estilo para filas de datos
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Columna #
            # Columnas numéricas alineadas a la derecha
            ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#f9f9f9')]),
        ]))

        story.append(tabla)
        story.append(Spacer(1, 20))

    # Pie de página
    story.append(
        Paragraph("*** SISTEMA DE GESTIÓN DE RESTAURANTES ***", normal_style))
    story.append(Paragraph("Reporte generado automáticamente", normal_style))
    story.append(
        Paragraph("404 FASTFOOD - Todos los derechos reservados", normal_style))

    # Construir el PDF
    doc.build(story)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Configurar respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    filename = f"productos_vendidos_{ahora_local.strftime('%Y%m%d_%H%M')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response.write(pdf)

    return response


# ========================================================================================================
#                           FUNCIONES DE GESTIÓN DE STOCK - SOLO BEBIDAS
# ========================================================================================================

@login_required
@login_required
def anulacionydevolucion(request):
    """Vista principal para anulación y devolución de facturas"""
    factura = None
    items = []
    items_json = '[]'
    productos_devueltos_json = '[]'
    productos_disponibles_json = '[]'

    numero_factura = request.GET.get('numero_factura', '').strip()
    ultima_factura = request.GET.get('ultima') == 'true'

    try:
        if ultima_factura:
            factura = Factura.objects.order_by('-fecha_creacion').first()
            if factura:
                messages.success(
                    request, f'Última factura cargada: {factura.numero_factura}')
            else:
                messages.error(request, 'No hay facturas registradas')

        elif numero_factura:
            factura = Factura.objects.filter(
                numero_factura__iexact=numero_factura).first()
            if not factura:
                factura = Factura.objects.filter(
                    numero_factura__icontains=numero_factura).first()

            if factura:
                messages.success(
                    request, f'Factura {factura.numero_factura} encontrada')
            else:
                messages.error(
                    request, f'Factura {numero_factura} no encontrada')

        if factura:
            # Obtener items detallados
            items = factura.get_items_detalle()
            items_json = json.dumps(items, cls=DjangoJSONEncoder)

            # Obtener productos disponibles para devolución
            productos_disponibles = factura.get_productos_disponibles_devolucion()
            productos_disponibles_json = json.dumps(
                productos_disponibles, cls=DjangoJSONEncoder)

            # Obtener resumen de devoluciones
            resumen_devoluciones = factura.get_resumen_devoluciones()

            # Obtener todas las devoluciones para el historial
            devoluciones = factura.devoluciones.all()
            todos_productos_devueltos = []

            for devolucion in devoluciones:
                if devolucion.productos_devueltos:
                    todos_productos_devueltos.extend(
                        devolucion.productos_devueltos)

            productos_devueltos_json = json.dumps(
                todos_productos_devueltos, cls=DjangoJSONEncoder)

            print(f"\n📄 FACTURA: {factura.numero_factura}")
            print(f"📦 Items totales: {len(items)}")
            print(
                f"✅ Productos disponibles para devolver: {len(productos_disponibles)}")
            print(
                f"💰 Total devuelto: ${resumen_devoluciones['total_devuelto']}")

    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        import traceback
        traceback.print_exc()

    context = {
        'factura': factura,
        'items': items,
        'items_json': items_json,
        'productos_devueltos_json': productos_devueltos_json,
        'productos_disponibles_json': productos_disponibles_json,
    }

    return render(request, 'facturacion/anulacionydevolucion.html', context)


def buscar_producto_por_identificador(identificador):
    """
    Buscar producto por código o nombre con validación mejorada.
    """
    if not identificador:
        return None

    identificador = str(identificador).strip()

    if not identificador:  # Si después del strip está vacío
        return None

    # 1. Buscar por código exacto (case-insensitive)
    producto = Producto.objects.filter(codigo__iexact=identificador).first()
    if producto:
        print(f"✅ Producto encontrado por código exacto: {producto.nombre}")
        return producto

    # 2. Buscar por nombre exacto (case-insensitive)
    producto = Producto.objects.filter(nombre__iexact=identificador).first()
    if producto:
        print(f"✅ Producto encontrado por nombre exacto: {producto.nombre}")
        return producto

    # 3. Buscar por código que contenga
    producto = Producto.objects.filter(codigo__icontains=identificador).first()
    if producto:
        print(f"✅ Producto encontrado por código parcial: {producto.nombre}")
        return producto

    # 4. Buscar por nombre que contenga
    producto = Producto.objects.filter(nombre__icontains=identificador).first()
    if producto:
        print(f"✅ Producto encontrado por nombre parcial: {producto.nombre}")
        return producto

    print(f"❌ Producto no encontrado con identificador: '{identificador}'")
    return None


def reponer_stock_producto(identificador, cantidad):
    """
    Aumentar stock de un producto SOLO SI ES BEBIDA
    """
    try:
        producto = buscar_producto_por_identificador(identificador)

        if producto:
            # Verificar que sea bebida
            if producto.categoria.lower() != 'bebida':
                print(
                    f"⚠️  Producto '{producto.nombre}' no es bebida (categoría: {producto.categoria})")
                return False

            # Reponer stock
            stock_anterior = producto.cantidad
            producto.cantidad += Decimal(str(cantidad))
            producto.save()

            print(f"📈 Stock repuesto: {producto.nombre} ({producto.codigo})")
            print(
                f"   Antes: {stock_anterior}, Añadido: {cantidad}, Después: {producto.cantidad}")

            return True

        return False

    except Exception as e:
        print(f"❌ Error al reponer stock: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def disminuir_stock_producto(identificador, cantidad):
    """
    Disminuir stock de un producto.
    """
    try:
        producto = buscar_producto_por_identificador(identificador)

        if producto:
            # Verificar que hay suficiente stock
            if producto.cantidad >= Decimal(str(cantidad)):
                producto.cantidad -= Decimal(str(cantidad))
                producto.save()
                print(
                    f"📉 Stock disminuido: {producto.nombre} ({producto.codigo})")
                return True
            else:
                print(
                    f"⚠️  Stock insuficiente: {producto.cantidad} < {cantidad}")
                return False

        return False

    except Exception as e:
        print(f"❌ Error al disminuir stock: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# =========================================================================================================
#                                   NORMALIZACIÓN DE ITEMS
# =========================================================================================================


def normalizar_items_factura(factura):
    """Normalizar los items de la factura para tener una estructura consistente"""
    items_normalizados = []
    items_detalle = factura.get_items_detalle()

    for i, item in enumerate(items_detalle):
        # Extraer datos con múltiples posibles claves
        nombre = item.get('nombre') or item.get(
            'name') or item.get('producto') or f'Producto {i+1}'
        cantidad = float(item.get('cantidad') or item.get('quantity') or 1)
        precio = float(item.get('precio') or item.get('price') or 0)
        subtotal = float(item.get('subtotal') or item.get(
            'total') or (cantidad * precio))
        categoria = item.get('categoria') or item.get('category') or ''

        # INTENTAR OBTENER EL CÓDIGO DEL PRODUCTO DESDE LA BASE DE DATOS
        codigo = ''
        producto_id = item.get('producto_id') or item.get('id')

        # Buscar producto por ID
        if producto_id:
            try:
                producto = Producto.objects.filter(id=producto_id).first()
                if producto:
                    codigo = producto.codigo
                    # Si no hay categoría en el item, usar la del producto
                    if not categoria or categoria.lower() == 'otro':
                        categoria = producto.categoria
            except Exception as e:
                print(f"Error al buscar producto por ID {producto_id}: {e}")

        # Si no se encontró por ID, buscar por nombre
        if not codigo and nombre:
            try:
                producto = Producto.objects.filter(
                    nombre__iexact=nombre.strip()).first()
                if producto:
                    codigo = producto.codigo
                    categoria = producto.categoria
            except Exception as e:
                print(f"Error al buscar producto por nombre {nombre}: {e}")

        items_normalizados.append({
            'id': producto_id or (i + 1),
            'producto_id': producto_id,
            'codigo': codigo,
            'nombre': nombre,
            'cantidad': cantidad,
            'precio': precio,
            'subtotal': subtotal,
            'categoria': categoria,
        })

    return items_normalizados


def buscar_item_por_nombre(items, nombre_buscar):
    """
    Buscar un item en la lista de items por nombre.
    """
    nombre_buscar_lower = nombre_buscar.lower().strip()

    for item in items:
        item_nombre = item.get('nombre', '').lower().strip()
        if item_nombre == nombre_buscar_lower:
            return item

        # Buscar por similitud
        if item_nombre.replace(' ', '') == nombre_buscar_lower.replace(' ', ''):
            return item

    # Si no se encuentra exacto, buscar por nombre que contenga
    for item in items:
        item_nombre = item.get('nombre', '').lower()
        if nombre_buscar_lower in item_nombre:
            return item

    return None


# ========================================================================================================
#                                        DEVOLUCIÓN TOTAL
# ========================================================================================================
@login_required
def procesar_devolucion_total(request):
    """Funcionalidad deshabilitada: la devolución total fue eliminada."""
    messages.warning(
        request, 'La opción de devolución total fue eliminada. Usa devolución parcial o anulación de factura.')
    return redirect('anulacionydevolucion')

# ========================================================================================================
#                                               DEVOLUCIÓN PARCIAL
# ========================================================================================================


@login_required
def procesar_devolucion_parcial(request):
    """
    Procesa la devolución parcial de productos de una factura.

    Devuelve JSON en todos los casos (el frontend usa fetch).

    Flujo:
      1. Valida productos y cantidades.
      2. Repone stock de bebidas.
      3. Crea Devolucion + DetalleDevolucion.
      4. Ajusta CxC si es crédito.
      5. Actualiza estado de la factura.

        Casos de respuesta:
            - Contado              → {"ok": true, "mensaje": "..."} y registra EGRESO automático
            - Crédito con excedente→ {"requiere_decision": true, "tipo": "excedente", "excedente": X,       "devolucion_id": N}
            - Crédito sin excedente→ {"ok": true, "mensaje": "..."}
      - Error                → {"error": "..."}  (status 400)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        # Compatibilidad: si el frontend envió form-encoded en lugar de JSON
        body = request.POST

    numero_factura = body.get('numero_factura', '')
    productos_json = body.get('productos_devueltos', '[]')

    if not numero_factura:
        return JsonResponse({'error': 'Número de factura requerido'}, status=400)

    try:
        factura = get_object_or_404(Factura, numero_factura=numero_factura)
    except Exception:
        return JsonResponse({'error': f'Factura {numero_factura} no encontrada'}, status=400)

    if factura.estado not in ['pagada', 'pendiente', 'parcialmente_devuelta']:
        return JsonResponse(
            {'error': f'Estado inválido para devolución: {factura.get_estado_display()}'},
            status=400
        )

    # Parsear productos si llegaron como string
    if isinstance(productos_json, str):
        try:
            productos_devueltos = json.loads(productos_json)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Formato inválido de productos'}, status=400)
    else:
        productos_devueltos = productos_json

    if not isinstance(productos_devueltos, list) or not productos_devueltos:
        return JsonResponse({'error': 'Debes seleccionar al menos un producto'}, status=400)

    try:
        with transaction.atomic():
            factura = Factura.objects.select_for_update().get(numero_factura=numero_factura)

            items_factura = factura.get_items_detalle()
            productos_procesados = []
            monto_total_devuelto = Decimal('0.00')
            bebidas_repuestas = 0

            # ── Validar y calcular cada producto devuelto ──────────────────
            for producto_data in productos_devueltos:
                producto_nombre = producto_data.get('nombre', '')
                producto_id = producto_data.get('producto_id')
                producto_codigo = str(producto_data.get('codigo', '')).strip()
                cantidad_devolver = float(producto_data.get('cantidad', 0))
                categoria = producto_data.get('categoria', '')

                # Buscar item en factura: id > codigo > nombre
                item_factura = None
                if producto_id not in (None, '', 'null'):
                    item_factura = next(
                        (i for i in items_factura
                         if str(i.get('producto_id', '')) == str(producto_id)),
                        None
                    )
                if not item_factura and producto_codigo:
                    item_factura = next(
                        (i for i in items_factura
                         if str(i.get('codigo', '')).strip().lower() == producto_codigo.lower()),
                        None
                    )
                if not item_factura:
                    item_factura = buscar_item_por_nombre(
                        items_factura, producto_nombre)

                if not item_factura:
                    return JsonResponse(
                        {'error': f'Producto "{producto_nombre}" no encontrado en la factura'},
                        status=400
                    )

                cantidad_original = float(item_factura.get('cantidad', 0))
                cantidad_ya_devuelta = factura.get_cantidad_ya_devuelta(
                    producto_nombre)
                cantidad_disponible = cantidad_original - cantidad_ya_devuelta

                if cantidad_devolver > cantidad_disponible:
                    return JsonResponse(
                        {'error': (
                            f'"{producto_nombre}": intentas devolver {cantidad_devolver} '
                            f'pero solo hay {cantidad_disponible:.0f} disponible '
                            f'(ya devuelto: {cantidad_ya_devuelta:.0f})'
                        )},
                        status=400
                    )

                precio = Decimal(str(item_factura.get('precio', 0)))
                subtotal = precio * Decimal(str(cantidad_devolver))
                codigo = item_factura.get('codigo', '')
                producto_id_resuelto = item_factura.get('producto_id')

                if not producto_id_resuelto:
                    if codigo:
                        pm = Producto.objects.filter(
                            codigo__iexact=codigo.strip()).first()
                        if pm:
                            producto_id_resuelto = pm.id
                    if not producto_id_resuelto and producto_nombre:
                        pm = Producto.objects.filter(
                            nombre__iexact=producto_nombre.strip()).first()
                        if pm:
                            producto_id_resuelto = pm.id

                # Reponer stock solo para bebidas
                if categoria.lower() == 'bebida':
                    identificador = codigo if codigo and codigo.strip() else producto_nombre
                    if reponer_stock_producto(identificador, cantidad_devolver):
                        bebidas_repuestas += 1

                monto_total_devuelto += subtotal
                productos_procesados.append({
                    'producto_id':    producto_id_resuelto,
                    'codigo':         codigo,
                    'nombre':         producto_nombre,
                    'cantidad':       cantidad_devolver,
                    'precio':         float(precio),
                    'precio_unitario': float(precio),
                    'subtotal':       float(subtotal),
                    'categoria':      categoria,
                })

            # ── Detectar tipo de venta ─────────────────────────────────────
            notas_pedido = (
                factura.pedido.notas or '') if factura.pedido else ''
            # hasattr(factura, 'cuenta_por_cobrar') siempre es True en Django
            # porque el descriptor existe aunque no haya CxC. Usar try/except.
            _tiene_cxc = False
            try:
                _ = factura.cuenta_por_cobrar
                _tiene_cxc = True
            except Exception:
                _tiene_cxc = False
            es_credito = (
                ('TIPO_PAGO_PEDIDO=credito' in notas_pedido)
                or _tiene_cxc
                or factura.pagos_cxc.exists()
            )

            # ── CONTADO: límite al monto efectivamente cobrado ─────────────
            if not es_credito:
                # En contado normalmente no existen pagos CxC, por lo que
                # get_total_pagado() sería 0 y bloquearía devoluciones válidas.
                total_pagado = (
                    factura.get_total_neto()
                    if hasattr(factura, 'get_total_neto')
                    else Decimal(str(factura.total or 0))
                )
                ya_devuelto = factura.get_total_devuelto()
                monto_maximo = max(total_pagado - ya_devuelto, Decimal('0.00'))

                if monto_maximo <= Decimal('0.00'):
                    return JsonResponse(
                        {'error': 'No hay monto disponible para devolver. El total ya fue devuelto.'},
                        status=400
                    )
                if monto_total_devuelto > monto_maximo:
                    monto_total_devuelto = monto_maximo

            # ── Crear Devolucion + DetalleDevolucion ───────────────────────
            devolucion = Devolucion.objects.create(
                factura=factura,
                tipo_devolucion='parcial',
                productos_devueltos=productos_procesados,
                monto_devuelto=monto_total_devuelto,
                motivo='Devolución parcial procesada',
                procesado_por=request.user,
            )

            for producto in productos_procesados:
                DetalleDevolucion.objects.create(
                    devolucion=devolucion,
                    nombre_producto=str(producto.get('nombre') or 'Producto'),
                    cantidad=Decimal(str(producto.get('cantidad', 0) or 0)),
                    precio_unitario=Decimal(
                        str(producto.get('precio_unitario', producto.get('precio', 0)) or 0)),
                    monto=Decimal(str(producto.get('subtotal', 0) or 0)),
                )

            # ── Ajustar CxC si es crédito ──────────────────────────────────
            if es_credito and _tiene_cxc:
                cxc = factura.cuenta_por_cobrar
                if cxc.estado not in ('pagada', 'anulada'):
                    nuevo_saldo = max(
                        cxc.saldo_pendiente - monto_total_devuelto,
                        Decimal('0.00')
                    )
                    cxc.saldo_pendiente = nuevo_saldo
                    cxc.estado = 'pagada' if nuevo_saldo <= Decimal(
                        '0.00') else 'parcial'
                    cxc.save(update_fields=['saldo_pendiente', 'estado'])

            # ── Actualizar estado de la factura ────────────────────────────
            if factura.estado in ['pagada', 'pendiente']:
                factura.estado = 'parcialmente_devuelta'

            if not factura.get_productos_disponibles_devolucion():
                factura.estado = 'totalmente_devuelta'

            factura.fecha_devolucion = timezone.now()
            factura.save()

            # Sincronizar movimientos financieros (para marcar INACTIVO si totalmente devuelta)
            _sincronizar_movimientos_factura(factura)

            # ── DECISIÓN FINANCIERA ────────────────────────────────────────
            # CONTADO: sale dinero de caja y se devuelven los productos.
            if not es_credito:
                MovimientoFinanciero.objects.create(
                    tipo='EGRESO',
                    origen='DEVOLUCION',
                    monto=monto_total_devuelto,
                    fecha_operacion=timezone.now(),
                    factura=factura,
                    devolucion=devolucion,
                    metodo_pago=factura.metodo_pago,
                    creado_por=request.user,
                    descripcion=(
                        f'Devolución de contado con egreso automático. '
                        f'Factura: {factura.numero_factura}. '
                        f'Monto: RD${monto_total_devuelto:.2f}.'
                    ),
                    referencia='DEVOLUCION_CONTADO_AUTOMATICA',
                )

                return JsonResponse({
                    'ok': True,
                    'mensaje': (
                        f'Devolución de contado procesada correctamente. '
                        f'Se devolvió dinero por RD${monto_total_devuelto:.2f}. '
                        f'Bebidas repuestas: {bebidas_repuestas}.'
                    ),
                    'numero_factura': factura.numero_factura,
                    'bebidas_repuestas': bebidas_repuestas,
                })

            # CRÉDITO: calcular balance post-devolución
            balance = factura.balance()

            if balance < Decimal('0.00'):
                # Excedente: el cliente pagó más de lo que debe tras la devolución.
                # El frontend pedirá la decisión (devolver dinero o saldo a favor).
                cliente_para_saldo = None
                try:
                    if factura.cuenta_por_cobrar.cliente:
                        cliente_para_saldo = factura.cuenta_por_cobrar.cliente
                except Exception:
                    pass
                if not cliente_para_saldo:
                    for cliente in Cliente.objects.all():
                        if _cliente_coincide_con_factura(cliente, factura):
                            cliente_para_saldo = cliente
                            break

                return JsonResponse({
                    'requiere_decision': True,
                    'tipo':             'excedente',
                    'excedente':        float(abs(balance)),
                    'devolucion_id':    devolucion.id,
                    'factura_id':       factura.id,
                    'puede_usar_saldo': bool(cliente_para_saldo),
                    'bebidas_repuestas': bebidas_repuestas,
                })

            # CRÉDITO SIN EXCEDENTE: la deuda bajó, no sale dinero de caja.
            # Se registra como AJUSTE para trazabilidad pero NO afecta el flujo de caja.
            MovimientoFinanciero.objects.create(
                tipo='EGRESO',
                origen='AJUSTE',
                monto=monto_total_devuelto,
                fecha_operacion=timezone.now(),
                factura=factura,
                devolucion=devolucion,
                metodo_pago=getattr(factura, 'metodo_pago', None),
                creado_por=request.user,
                descripcion=(
                    f'Devolución de productos en venta a crédito. '
                    f'Deuda reducida en RD${monto_total_devuelto:.2f}. '
                    f'No representa salida de caja. '
                    f'Factura: {factura.numero_factura}.'
                ),
                referencia='DEVOLUCION_CREDITO_AJUSTE',
            )

            return JsonResponse({
                'ok':      True,
                'mensaje': (
                    f'Devolución procesada correctamente. '
                    f'Monto ajustado en deuda: RD${monto_total_devuelto:.2f}. '
                    f'Bebidas repuestas: {bebidas_repuestas}.'
                ),
                'numero_factura': factura.numero_factura,
                'bebidas_repuestas': bebidas_repuestas,
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Error interno: {str(e)}'}, status=500)

# ============================================================
# RESOLVER EXCEDENTE DE DEVOLUCIÓN
# ============================================================


@login_required
@require_POST
def resolver_excedente_devolucion(request):
    """
    Segunda fase del flujo de devolución: ejecuta la decisión financiera
    cuando la devolución generó dinero a favor del cliente.

    Recibe JSON:
        factura_id    (int)   — ID de la factura
        devolucion_id (int)   — ID de la Devolucion ya creada
        accion        (str)   — 'devolver' | 'saldo'
        tipo          (str)   — 'contado'  | 'excedente'
        monto         (float) — solo requerido cuando tipo == 'contado'

    Acciones:
        devolver → crea MovimientoFinanciero EGRESO (sale dinero de caja)
        saldo    → crea SaldoAFavor (queda pendiente para el cliente)
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Body JSON inválido'}, status=400)

    factura_id = body.get('factura_id')
    devolucion_id = body.get('devolucion_id')
    accion = body.get('accion', '')
    tipo = body.get('tipo', '')

    # ── Validaciones básicas ───────────────────────────────────────────────
    if not factura_id or not devolucion_id:
        return JsonResponse({'error': 'factura_id y devolucion_id son requeridos'}, status=400)

    if accion not in ('devolver', 'saldo'):
        return JsonResponse({'error': 'Acción inválida. Usa "devolver" o "saldo"'}, status=400)

    if tipo not in ('contado', 'excedente'):
        return JsonResponse({'error': 'Tipo inválido. Usa "contado" o "excedente"'}, status=400)

    try:
        with transaction.atomic():
            factura = Factura.objects.select_for_update().get(id=factura_id)
            devolucion = Devolucion.objects.get(
                id=devolucion_id, factura=factura)

            # ── Calcular monto a mover ─────────────────────────────────────
            if tipo == 'contado':
                # Para contado el monto viene explícito porque balance() no aplica
                monto_raw = body.get('monto')
                if monto_raw is None:
                    return JsonResponse(
                        {'error': 'monto es requerido para tipo contado'},
                        status=400
                    )
                monto = Decimal(str(monto_raw))
                if monto <= Decimal('0.00'):
                    return JsonResponse({'error': 'El monto debe ser mayor a cero'}, status=400)
                referencia = 'DEVOLUCION_CONTADO'

            else:  # excedente
                balance = factura.balance()
                if balance >= Decimal('0.00'):
                    return JsonResponse(
                        {'error': 'No hay excedente en esta factura'},
                        status=400
                    )
                monto = abs(balance)
                referencia = 'EXCEDENTE_DEVOLUCION'

            # ── Ejecutar acción elegida por el usuario ─────────────────────
            if accion == 'devolver':
                # Sale dinero de caja
                movimiento = MovimientoFinanciero.objects.create(
                    tipo='EGRESO',
                    origen='DEVOLUCION',
                    monto=monto,
                    fecha_operacion=timezone.now(),
                    factura=factura,
                    devolucion=devolucion,
                    metodo_pago=factura.metodo_pago,
                    creado_por=request.user,
                    descripcion=(
                        f'Devolución de dinero al cliente. '
                        f'Factura: {factura.numero_factura}. '
                        f'Tipo: {tipo}. Monto: RD${monto}.'
                    ),
                    referencia=referencia,
                )
                mensaje = f'Egreso de RD${monto:.2f} registrado en caja.'

            else:  # saldo
                # El dinero queda a favor del cliente, sin salir de caja
                cliente_saldo = None
                if hasattr(factura, 'cuenta_por_cobrar') and factura.cuenta_por_cobrar.cliente:
                    cliente_saldo = factura.cuenta_por_cobrar.cliente
                else:
                    for cliente in Cliente.objects.all():
                        if _cliente_coincide_con_factura(cliente, factura):
                            cliente_saldo = cliente
                            break

                if not cliente_saldo:
                    return JsonResponse(
                        {
                            'error': (
                                'No se puede registrar saldo a favor porque la factura no tiene '
                                'cliente vinculado. Usa "devolver" o vincula un cliente primero.'
                            )
                        },
                        status=400
                    )

                SaldoAFavor.objects.create(
                    cliente=cliente_saldo,
                    factura_origen=factura,
                    devolucion=devolucion,
                    monto=monto,
                    motivo=(
                        'Devolución en efectivo convertida en saldo a favor'
                        if tipo == 'contado'
                        else 'Excedente por devolución en crédito'
                    ),
                    creado_por=request.user,
                )
                mensaje = f'Saldo a favor de RD${monto:.2f} registrado para el cliente.'

            return JsonResponse({
                'ok':             True,
                'mensaje':        mensaje,
                'numero_factura': factura.numero_factura,
            })

    except Factura.DoesNotExist:
        return JsonResponse({'error': 'Factura no encontrada'}, status=404)
    except Devolucion.DoesNotExist:
        return JsonResponse({'error': 'Devolución no encontrada o no pertenece a esta factura'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Error interno: {str(e)}'}, status=500)

# ============================================================
# ANULACIÓN DE FACTURA
# ============================================================


@login_required
def procesar_anulacion_factura(request):
    """Procesar anulación de una factura con reposición de inventario y ajuste de pagos."""
    if request.method == 'POST':
        numero_factura = request.POST.get('numero_factura')
        motivo = request.POST.get('motivo', '')

        if not numero_factura:
            messages.error(request, 'Número de factura requerido')
            return redirect('anulacionydevolucion')

        try:
            factura = get_object_or_404(Factura, numero_factura=numero_factura)

            if factura.estado not in ['pagada', 'pendiente']:
                messages.error(
                    request,
                    f'Solo se pueden anular facturas pagadas o pendientes. Estado actual: {factura.get_estado_display()}'
                )
                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

            with transaction.atomic():
                # Usar el método del modelo para obtener items
                items = factura.get_items_detalle()
                bebidas_repuestas = 0

                notas_pedido = (
                    factura.pedido.notas or '') if factura.pedido else ''
                _tiene_cxc = False
                try:
                    _ = factura.cuenta_por_cobrar
                    _tiene_cxc = True
                except Exception:
                    _tiene_cxc = False
                es_credito = (
                    ('TIPO_PAGO_PEDIDO=credito' in notas_pedido)
                    or _tiene_cxc
                    or factura.pagos_cxc.exists()
                )

                monto_devuelto = Decimal('0.00')
                pagos_eliminados = 0

                print(f"\n❌ PROCESANDO ANULACIÓN DE FACTURA")

                # REPONER stock para productos bebida
                for item in items:
                    nombre = item.get('nombre', '')
                    codigo = item.get('codigo', '')
                    cantidad = item.get('cantidad', 0)
                    categoria = item.get('categoria', '')

                    print(f"\n📦 Procesando item: {nombre}")
                    print(f"   Código: '{codigo}'")
                    print(f"   Categoría: '{categoria}'")

                    if categoria.lower() == 'bebida':
                        # Usar código si está disponible, sino usar nombre
                        identificador = codigo if codigo and codigo.strip() else nombre
                        print(
                            f"   🍺 ES BEBIDA - Reponiendo stock con: '{identificador}'")

                        if reponer_stock_producto(identificador, cantidad):
                            bebidas_repuestas += 1
                            print(f"   ✅ Stock repuesto exitosamente")

                # Ajustes financieros según tipo de venta
                if es_credito:
                    pagos_qs = factura.pagos_cxc.all()
                    monto_devuelto = pagos_qs.aggregate(total=Sum('monto'))[
                        'total'] or Decimal('0.00')
                    pagos_eliminados = pagos_qs.count()
                    if pagos_eliminados:
                        pagos_qs.delete()

                    try:
                        cuenta = factura.cuenta_por_cobrar
                        cuenta.estado = 'anulada'
                        cuenta.saldo_pendiente = Decimal('0.00')
                        cuenta.save(update_fields=[
                                    'estado', 'saldo_pendiente'])
                    except Exception:
                        pass
                else:
                    # En contado se devuelve el total de la factura
                    monto_devuelto = Decimal(str(factura.total or 0))

                # Registrar devolución total por anulación y guardar detalle por renglón.
                devolucion = Devolucion.objects.create(
                    factura=factura,
                    tipo_devolucion='total',
                    productos_devueltos=items,
                    monto_devuelto=monto_devuelto,
                    motivo=motivo or 'Anulación de factura',
                    procesado_por=request.user
                )

                for item in items:
                    cantidad = Decimal(str(item.get('cantidad', 0) or 0))
                    precio_unitario = Decimal(str(item.get('precio', 0) or 0))
                    monto = cantidad * precio_unitario

                    DetalleDevolucion.objects.create(
                        devolucion=devolucion,
                        nombre_producto=str(item.get('nombre') or 'Producto'),
                        cantidad=cantidad,
                        precio_unitario=precio_unitario,
                        monto=monto,
                    )

                factura.estado = 'anulada'
                factura.motivo_anulacion = motivo
                factura.fecha_anulacion = timezone.now()
                factura.usuario_anulacion = request.user
                factura.fecha_devolucion = timezone.now()
                factura.save(update_fields=[
                    'estado',
                    'motivo_anulacion',
                    'fecha_anulacion',
                    'usuario_anulacion',
                    'fecha_devolucion',
                ])

                # Sincronizar movimientos financieros (marca INACTIVO los originales)
                _sincronizar_movimientos_factura(factura)

                # Registrar egreso financiero por anulación.
                # REGLA: solo se genera un egreso real de caja si hubo un ingreso
                # real previo. Anular una factura "pendiente" (nunca cobrada) no
                # mueve dinero, por lo que NO debe registrarse ningún egreso.
                #
                #  · Contado  → verificar que exista un MovimientoFinanciero de
                #               INGRESO/VENTA vinculado a esta factura.
                #  · Crédito  → el egreso equivale a los pagos CxC eliminados;
                #               solo aplica si efectivamente se eliminaron pagos.
                if monto_devuelto > 0:
                    _registrar_egreso = False

                    if es_credito:
                        # Solo si se eliminaron pagos ya cobrados
                        _registrar_egreso = pagos_eliminados > 0
                    else:
                        # Contado: solo si la factura tenía un ingreso registrado
                        # (es decir, ya había sido cobrada antes de la anulación)
                        _registrar_egreso = MovimientoFinanciero.objects.filter(
                            factura=factura,
                            tipo='INGRESO',
                            origen='VENTA',
                        ).exists()

                    if _registrar_egreso:
                        referencia_anulacion = 'ANULACION_CREDITO' if es_credito else 'ANULACION_CONTADO'
                        MovimientoFinanciero.objects.create(
                            tipo="EGRESO",
                            origen="ANULACION",
                            referencia=referencia_anulacion,
                            monto=monto_devuelto,
                            fecha_operacion=timezone.now(),
                            factura=factura,
                            devolucion=devolucion,
                            metodo_pago=factura.metodo_pago,
                            creado_por=request.user,
                            descripcion=(
                                f"Anulación factura {factura.numero_factura}. "
                                f"Motivo: {motivo or 'Sin motivo'}. "
                                + (f"Pagos CxC eliminados: {pagos_eliminados}." if es_credito else "")
                            ),
                        )

                # Cerrar el ciclo en este mismo flujo: evitar que reaparezca en gestión/facturación.
                if factura.pedido:
                    factura.pedido.estado = 'cancelado'
                    factura.pedido.save(update_fields=['estado'])
                    if factura.pedido.mesa:
                        factura.pedido.mesa.estado = 'disponible'
                        factura.pedido.mesa.save(update_fields=['estado'])

                print(f"\n✅ ANULACIÓN COMPLETADA")
                print(f"   Bebidas repuestas: {bebidas_repuestas}")
                print(f"   Monto devuelto: {monto_devuelto}")
                if es_credito:
                    print(f"   Pagos CxC eliminados: {pagos_eliminados}")

                messages.success(
                    request,
                    (
                        f'✅ Factura {factura.numero_factura} anulada. '
                        f'Bebidas repuestas: {bebidas_repuestas}. '
                        f'Monto devuelto: ${monto_devuelto:.2f}.'
                        + (f' Pagos eliminados: {pagos_eliminados}.' if es_credito else '')
                    )
                )

                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

        except Exception as e:
            messages.error(request, f'❌ Error al anular factura: {str(e)}')
            import traceback
            traceback.print_exc()
            return redirect('anulacionydevolucion')

    return redirect('anulacionydevolucion')


# ==========================================================================================================
#
# ==========================================================================================================
def gestiondeclientes(request):
    """Vista para gestión/listado de clientes con filtros y paginación."""
    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    search = (request.GET.get('search') or '').strip()
    estado = (request.GET.get('estado') or '').strip()
    credito = (request.GET.get('credito') or '').strip()
    fecha = (request.GET.get('fecha') or '').strip()
    sort_by = (request.GET.get('sort') or 'nombre').strip()
    page = request.GET.get('page', 1)

    clientes_qs = Cliente.objects.all()

    if search:
        clientes_qs = clientes_qs.filter(
            Q(cedula__icontains=search)
            | Q(nombre_completo__icontains=search)
            | Q(telefono_principal__icontains=search)
            | Q(telefono_alternativo__icontains=search)
        )

    if estado == 'activo':
        clientes_qs = clientes_qs.filter(activo=True)
    elif estado == 'inactivo':
        clientes_qs = clientes_qs.filter(activo=False)

    if fecha:
        # Filtro por rangos de fecha-hora en zona RD para evitar desfases por timezone.
        inicio_hoy = ahora_local.replace(
            hour=0, minute=0, second=0, microsecond=0)
        fin_hoy = inicio_hoy + timedelta(days=1)
        inicio_mes_actual = inicio_hoy.replace(day=1)

        if fecha == 'hoy':
            clientes_qs = clientes_qs.filter(
                fecha_registro__gte=inicio_hoy, fecha_registro__lt=fin_hoy)
        elif fecha == 'ayer':
            inicio_ayer = inicio_hoy - timedelta(days=1)
            clientes_qs = clientes_qs.filter(
                fecha_registro__gte=inicio_ayer, fecha_registro__lt=inicio_hoy)
        elif fecha in ['semana', 'semana_actual']:
            inicio_semana = inicio_hoy - timedelta(days=ahora_local.weekday())
            clientes_qs = clientes_qs.filter(
                fecha_registro__gte=inicio_semana, fecha_registro__lt=fin_hoy)
        elif fecha in ['mes', 'este_mes']:
            clientes_qs = clientes_qs.filter(
                fecha_registro__gte=inicio_mes_actual, fecha_registro__lt=fin_hoy)

    sort_map = {
        'nombre': 'nombre_completo',
        'nombre_desc': '-nombre_completo',
        'cedula': 'cedula',
        'fecha_desc': '-fecha_registro',
        'fecha_asc': 'fecha_registro',
        'credito_desc': '-limite_credito',
        'credito_asc': 'limite_credito',
    }
    clientes_qs = clientes_qs.order_by(
        sort_map.get(sort_by, 'nombre_completo'))

    facturas_pendientes = list(Factura.objects.filter(
        estado='pendiente').prefetch_related('pagos_cxc'))

    # Filtros que dependen de cálculo de saldo real.
    if credito in ('agotado', 'excedido'):
        clientes_filtrados = []
        for cliente in clientes_qs:
            limite = cliente.limite_credito or Decimal('0.00')
            saldo_actual = _calcular_saldo_credito_cliente(
                cliente, facturas_pendientes)
            saldo_disponible = limite - saldo_actual

            # Reutilizable por la tabla sin recalcular durante el render de la página.
            cliente.saldo_actual = saldo_actual
            cliente.saldo_disponible = saldo_disponible

            if credito == 'agotado' and saldo_disponible == 0:
                clientes_filtrados.append(cliente)
            elif credito == 'excedido' and saldo_disponible < 0:
                clientes_filtrados.append(cliente)
        clientes_qs = clientes_filtrados
    elif credito == 'con_credito':
        clientes_qs = clientes_qs.filter(limite_credito__gt=0)
    elif credito == 'sin_credito':
        clientes_qs = clientes_qs.filter(limite_credito__lte=0)

    paginator = Paginator(clientes_qs, 12)
    page_obj = paginator.get_page(page)

    for cliente in page_obj.object_list:
        limite = cliente.limite_credito or Decimal('0.00')
        saldo_actual = _calcular_saldo_credito_cliente(
            cliente, facturas_pendientes)
        cliente.saldo_actual = saldo_actual
        cliente.saldo_disponible = limite - saldo_actual

    inicio_hoy = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_hoy = inicio_hoy + timedelta(days=1)
    estadisticas = {
        'total_clientes': Cliente.objects.count(),
        'clientes_activos': Cliente.objects.filter(activo=True).count(),
        'credito_total': Cliente.objects.aggregate(total=Sum('limite_credito')).get('total') or Decimal('0.00'),
        'clientes_hoy': Cliente.objects.filter(fecha_registro__gte=inicio_hoy, fecha_registro__lt=fin_hoy).count(),
    }

    context = {
        'clientes': page_obj,
        'paginator': page_obj,
        'estadisticas': estadisticas,
        'filtros': {
            'search': search,
            'estado': estado,
            'credito': credito,
            'fecha': fecha,
            'sort': sort_by,
        },
    }
    return render(request, 'facturacion/gestiondeclientes.html', context)


def _estadisticas_clientes():
    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    inicio_hoy = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_hoy = inicio_hoy + timedelta(days=1)
    return {
        'total_clientes': Cliente.objects.count(),
        'clientes_activos': Cliente.objects.filter(activo=True).count(),
        'credito_total': Cliente.objects.aggregate(total=Coalesce(Sum('limite_credito'), Decimal('0.00'), output_field=DecimalField()))['total'],
        'clientes_hoy': Cliente.objects.filter(fecha_registro__gte=inicio_hoy, fecha_registro__lt=fin_hoy).count(),
    }


def _cliente_json(cliente):
    limite_credito = cliente.limite_credito or Decimal('0.00')
    saldo_actual = _calcular_saldo_credito_cliente(cliente)
    saldo_disponible = limite_credito - saldo_actual
    dinero_fondo = SaldoAFavor.objects.filter(
        cliente=cliente,
        estado='pendiente',
        activo=True
    ).aggregate(total=Sum('monto')).get('total') or Decimal('0.00')

    return {
        'id': cliente.id,
        'cedula': cliente.cedula,
        'nombre_completo': cliente.nombre_completo,
        'direccion': cliente.direccion,
        'telefono_principal': cliente.telefono_principal,
        'telefono_alternativo': cliente.telefono_alternativo or '',
        'limite_credito': float(limite_credito),
        'dias_credito': cliente.dias_credito,
        'notas_credito': cliente.notas_credito or '',
        'notas_generales': '',
        'correo_electronico': '',
        'activo': cliente.activo,
        'saldo_actual': float(saldo_actual),
        'saldo_disponible': float(saldo_disponible),
        'dinero_fondo': float(dinero_fondo),
        'fecha_registro': cliente.fecha_registro.isoformat() if cliente.fecha_registro else None,
        'fecha_actualizacion': cliente.fecha_actualizacion.isoformat() if cliente.fecha_actualizacion else None,
        'usuario_registro': (cliente.registrado_por.username if getattr(cliente, 'registrado_por', None) else 'Sistema'),
    }


@csrf_exempt
def detalle_cliente(request, cliente_id):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    cliente = get_object_or_404(Cliente, pk=cliente_id)
    return JsonResponse(_cliente_json(cliente))


@csrf_exempt
def editar_cliente(request, cliente_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    cliente = get_object_or_404(Cliente, pk=cliente_id)

    try:
        cedula = (request.POST.get('cedula') or '').strip()
        nombre_completo = (request.POST.get('nombre_completo') or '').strip()
        direccion = (request.POST.get('direccion') or '').strip()
        telefono_principal = (request.POST.get(
            'telefono_principal') or '').strip()
        telefono_alternativo = (request.POST.get(
            'telefono_alternativo') or '').strip()
        limite_credito_str = (request.POST.get(
            'limite_credito') or '0').strip()
        dias_credito_str = (request.POST.get('dias_credito') or '30').strip()
        notas_credito = (request.POST.get('notas_credito') or '').strip()
        activo_str = (request.POST.get('activo') or 'true').strip().lower()

        cedula_limpia = ''.join(filter(str.isdigit, cedula))
        tel_principal_limpio = ''.join(filter(str.isdigit, telefono_principal))
        tel_alt_limpio = ''.join(
            filter(str.isdigit, telefono_alternativo)) if telefono_alternativo else ''

        if len(cedula_limpia) != 11:
            return JsonResponse({'success': False, 'error': 'La cédula debe tener exactamente 11 dígitos'})
        if len(tel_principal_limpio) != 10:
            return JsonResponse({'success': False, 'error': 'El teléfono principal debe tener 10 dígitos'})
        if tel_alt_limpio and len(tel_alt_limpio) != 10:
            return JsonResponse({'success': False, 'error': 'El teléfono alternativo debe tener 10 dígitos'})
        if len(nombre_completo) < 5:
            return JsonResponse({'success': False, 'error': 'El nombre debe tener al menos 5 caracteres'})
        if len(direccion) < 10:
            return JsonResponse({'success': False, 'error': 'La dirección debe tener al menos 10 caracteres'})

        try:
            limite_credito = Decimal(limite_credito_str)
        except Exception:
            limite_credito = Decimal('0.00')

        try:
            dias_credito = int(dias_credito_str)
        except Exception:
            dias_credito = 30

        if limite_credito < 0:
            return JsonResponse({'success': False, 'error': 'El límite de crédito no puede ser negativo'})
        if limite_credito > 1000000:
            return JsonResponse({'success': False, 'error': 'El límite de crédito máximo es $1,000,000'})
        if dias_credito < 0 or dias_credito > 365:
            return JsonResponse({'success': False, 'error': 'Los días de crédito deben estar entre 0 y 365'})

        if Cliente.objects.exclude(pk=cliente.id).filter(cedula=cedula_limpia).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe otro cliente con esa cédula'})

        cliente.cedula = cedula_limpia
        cliente.nombre_completo = nombre_completo
        cliente.direccion = direccion
        cliente.telefono_principal = tel_principal_limpio
        cliente.telefono_alternativo = tel_alt_limpio or None
        cliente.limite_credito = limite_credito
        cliente.dias_credito = dias_credito
        cliente.notas_credito = notas_credito or None
        cliente.activo = activo_str in ('true', '1', 'yes', 'si', 'on')
        cliente.save()

        return JsonResponse({
            'success': True,
            'mensaje': 'Cliente actualizado correctamente',
            'cliente': _cliente_json(cliente),
            'estadisticas': _estadisticas_clientes(),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al actualizar cliente: {str(e)}'})


@csrf_exempt
def eliminar_cliente(request, cliente_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    cliente = get_object_or_404(Cliente, pk=cliente_id)
    nombre = cliente.nombre_completo
    cliente.delete()

    return JsonResponse({
        'success': True,
        'mensaje': f'Cliente "{nombre}" eliminado correctamente',
        'estadisticas': _estadisticas_clientes(),
    })


@csrf_exempt
def historial_cliente(request, cliente_id):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    cliente = get_object_or_404(Cliente, pk=cliente_id)

    filtros = Q(nombre_cliente__iexact=cliente.nombre_completo) | Q(
        telefono_cliente=cliente.telefono_principal)
    if cliente.telefono_alternativo:
        filtros |= Q(telefono_cliente=cliente.telefono_alternativo)

    facturas = Factura.objects.filter(filtros).order_by('-fecha_factura')[:30]

    historial = [
        {
            'numero_factura': f.numero_factura,
            'fecha_factura': f.fecha_factura.isoformat() if f.fecha_factura else None,
            'estado': f.estado,
            'metodo_pago': f.metodo_pago,
            'tipo_pedido': f.tipo_pedido,
            'total': float(f.total or 0),
        }
        for f in facturas
    ]

    return JsonResponse({
        'success': True,
        'cliente': {
            'id': cliente.id,
            'nombre_completo': cliente.nombre_completo,
            'cedula': cliente.cedula,
            'telefono_principal': cliente.telefono_principal,
        },
        'historial': historial,
    })


@login_required
def reporte_clientes_pdf(request):
    """
    Genera PDF A4 con reporte de clientes.
    URL: path('gestiondeclientes/exportar-pdf/', views.reporte_clientes_pdf, name='reporte_clientes_pdf'),
    Botón HTML: window.open('/gestiondeclientes/exportar-pdf/', '_blank');
    Acepta filtros: ?search= ?estado=activo|inactivo ?credito=con|sin
    """

    # ── Paleta ────────────────────────────────────────────────────────────────
    GRIS_OSCURO = colors.HexColor('#2C3E50')
    GRIS_MEDIO = colors.HexColor('#5D6D7E')
    GRIS_CLARO = colors.HexColor('#ECF0F1')
    GRIS_BORDE = colors.HexColor('#BDC3C7')
    ACENTO = colors.HexColor('#4A90A4')
    ACENTO_CLARO = colors.HexColor('#EAF4F7')
    VERDE = colors.HexColor('#27AE60')
    VERDE_CLR = colors.HexColor('#EAFAF1')
    ROJO = colors.HexColor('#C0392B')
    ROJO_CLR = colors.HexColor('#FDEDEC')
    AMARILLO = colors.HexColor('#D4A017')
    AMARILLO_CLR = colors.HexColor('#FEF9E7')
    BLANCO = colors.white

    # ── Filtros ───────────────────────────────────────────────────────────────
    search = request.GET.get('search',  '').strip()
    estado = request.GET.get('estado',  '')
    credito = request.GET.get('credito', '')

    qs = Cliente.objects.all().order_by('nombre_completo')
    if search:
        qs = qs.filter(
            Q(nombre_completo__icontains=search) |
            Q(cedula__icontains=search) |
            Q(telefono_principal__icontains=search)
        )
    if estado == 'activo':
        qs = qs.filter(activo=True)
    elif estado == 'inactivo':
        qs = qs.filter(activo=False)
    if credito == 'con':
        qs = qs.filter(limite_credito__gt=0)
    elif credito == 'sin':
        qs = qs.filter(limite_credito=0)

    clientes = list(qs)

    # ── Estadísticas ──────────────────────────────────────────────────────────
    total_clientes = len(clientes)
    activos = sum(1 for c in clientes if c.activo)
    inactivos = total_clientes - activos
    con_credito = sum(1 for c in clientes if float(c.limite_credito or 0) > 0)
    credito_total = sum(float(c.limite_credito or 0) for c in clientes)

    # ── Buffer y documento ────────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=15*mm,   bottomMargin=18*mm,
    )
    ancho = doc.width  # ~170mm

    styles = getSampleStyleSheet()

    def sty(name, **kw):
        base = kw.pop('parent', styles['Normal'])
        return ParagraphStyle(name, parent=base, **kw)

    bold_sty = sty('ecB',  fontName='Helvetica-Bold', fontSize=9)
    cell_sty = sty('ecC',  fontSize=8,  leading=11)
    cell_b_sty = sty('ecCB', fontSize=8,  leading=11,
                     fontName='Helvetica-Bold', textColor=GRIS_OSCURO)
    cell_d_sty = sty('ecCD', fontSize=8,  leading=11, textColor=GRIS_OSCURO)
    hdr_sty = sty('ecH',  fontSize=8,  leading=10,
                  fontName='Helvetica-Bold', alignment=1, textColor=BLANCO)
    small_sty = sty('ecSM', fontSize=8)

    story = []

    # ── Logo ──────────────────────────────────────────────────────────────────
    try:
        logo_path = os.path.join(
            settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'img', 'fastfood.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(
                settings.BASE_DIR, 'static', 'img', 'fastfood.png')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=30*mm, height=30*mm)
            logo_table = Table([[logo]], colWidths=[doc.width])
            logo_table.setStyle(TableStyle(
                [('ALIGN', (0, 0), (0, 0), 'CENTER')]))
            story.append(logo_table)
            story.append(Spacer(1, 4))
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════════════
    hdr_data = [[
        Paragraph('402 FASTFOOD',
                  sty('ecEMP', fontSize=12, fontName='Helvetica-Bold', textColor=BLANCO)),
        Paragraph('REPORTE DE CLIENTES',
                  sty('ecTIT', fontSize=13, fontName='Helvetica-Bold', textColor=BLANCO, alignment=1)),
        Paragraph(
            f'Emitido el {date.today().strftime("%d/%m/%Y")}<br/>'
            f'<font size="7.5">Castanuelas, calle 30 de mayo</font>',
            sty('ecFEC', fontSize=8.5, textColor=GRIS_CLARO, alignment=2)
        ),
    ]]
    thdr = Table(hdr_data, colWidths=[ancho*0.27, ancho*0.46, ancho*0.27])
    thdr.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), GRIS_OSCURO),
        ('VALIGN',        (0, 0), (-1, 0), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('LEFTPADDING',   (0, 0), (0, 0),  10),
        ('RIGHTPADDING',  (-1, 0), (-1, 0), 10),
        ('LINEAFTER',     (0, 0), (0, 0),  4, ACENTO),
    ]))
    story.append(thdr)
    story.append(Spacer(1, 7))

    # ══════════════════════════════════════════════════════════════════════════
    # TARJETAS DE RESUMEN
    # ══════════════════════════════════════════════════════════════════════════
    card_defs = [
        ('TOTAL\nCLIENTES',    str(total_clientes),          GRIS_OSCURO, GRIS_CLARO),
        ('ACTIVOS',            str(activos),
         VERDE,       VERDE_CLR),
        ('INACTIVOS',          str(inactivos),                ROJO,        ROJO_CLR),
        ('CON\nCRÉDITO',      str(con_credito),
         ACENTO,      ACENTO_CLARO),
        ('CRÉDITO\nOTORGADO',
         f'RD$ {credito_total:,.0f}',  AMARILLO,    AMARILLO_CLR),
    ]
    card_w = ancho / 5
    card_cells = []
    card_bgs = []
    for lbl, val, vc, bg in card_defs:
        inner = Table(
            [[Paragraph(lbl, sty(f'ecCL{lbl[:3]}', fontSize=7, fontName='Helvetica-Bold',
                                 textColor=GRIS_MEDIO, alignment=1, leading=9))],
             [Paragraph(val, sty(f'ecCV{lbl[:3]}', fontSize=15, fontName='Helvetica-Bold',
                                 textColor=vc, alignment=1))]],
            colWidths=[card_w - 4*mm],
        )
        inner.setStyle(TableStyle([
            ('TOPPADDING',    (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        card_cells.append(inner)
        card_bgs.append(bg)

    tcards = Table([card_cells], colWidths=[card_w]*5)
    card_ts = [
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (0, 0), (-1, -1), 2),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
    ]
    for i, bg in enumerate(card_bgs):
        card_ts += [('BACKGROUND', (i, 0), (i, 0), bg),
                    ('BOX', (i, 0), (i, 0), 0.5, GRIS_BORDE)]
    tcards.setStyle(TableStyle(card_ts))
    story.append(tcards)
    story.append(Spacer(1, 11))

    # ══════════════════════════════════════════════════════════════════════════
    # TABLA DE CLIENTES
    # Anchos: 24+37+20+33+22+11+14+9 = 170mm
    CW = [24*mm, 37*mm, 20*mm, 33*mm, 22*mm, 11*mm, 14*mm, 9*mm]

    hdrs = ['Cédula', 'Nombre Completo', 'Teléfono(s)', 'Dirección',
            'Límite Crédito', 'Días', 'Estado', 'Registro']
    data = [[Paragraph(h, hdr_sty) for h in hdrs]]

    row_styles = []
    for idx, c in enumerate(clientes):
        ri = idx + 1

        # Límite crédito (sin redundar días plazo)
        if float(c.limite_credito or 0) > 0:
            cred_txt = f'RD$ {float(c.limite_credito):,.2f}'
            cred_color = ACENTO
        else:
            cred_txt = 'Sin crédito'
            cred_color = GRIS_MEDIO

        # Días
        if int(c.dias_credito or 0) > 0:
            dias_txt = f'{c.dias_credito}d.'
            dias_color = ACENTO
        else:
            dias_txt = 'Cont.'
            dias_color = GRIS_MEDIO

        # Estado
        est_txt = 'Activo' if c.activo else 'Inactivo'
        est_color = VERDE if c.activo else ROJO

        # Teléfono(s)
        tel_txt = c.telefono_principal or '-'
        if c.telefono_alternativo:
            tel_txt += f'<br/><font size="7" color="#718096">Alt: {c.telefono_alternativo}</font>'

        # Dirección — legible, truncada
        dir_raw = c.direccion or '-'
        dir_txt = dir_raw[:45] + ('…' if len(dir_raw) > 45 else '')

        fila = [
            Paragraph(c.cedula or '-',          cell_b_sty),
            Paragraph(c.nombre_completo or '-', cell_b_sty),
            Paragraph(tel_txt,                  cell_sty),
            Paragraph(dir_txt,                  cell_d_sty),
            Paragraph(cred_txt, sty(f'ecCR{ri}', fontSize=8, fontName='Helvetica-Bold',
                                    textColor=cred_color, alignment=1)),
            Paragraph(dias_txt, sty(f'ecD{ri}',  fontSize=8, fontName='Helvetica-Bold',
                                    textColor=dias_color, alignment=1)),
            Paragraph(est_txt,  sty(f'ecE{ri}',  fontSize=8, fontName='Helvetica-Bold',
                                    textColor=est_color,  alignment=1)),
            Paragraph(
                c.fecha_registro.strftime(
                    '%d/%m/%Y') if c.fecha_registro else '-',
                sty(f'ecR{ri}', fontSize=6.5,
                    alignment=1, textColor=GRIS_MEDIO)
            ),
        ]
        data.append(fila)

        if c.activo:
            bg_row = ACENTO_CLARO if idx % 2 == 0 else BLANCO
        else:
            bg_row = ROJO_CLR if idx % 2 == 0 else colors.HexColor('#FDF2F0')

        row_styles += [
            ('BACKGROUND', (0, ri), (-1, ri), bg_row),
            ('LINEBELOW',  (0, ri), (-1, ri), 0.3, GRIS_BORDE),
        ]

    tclientes = Table(data, colWidths=CW, repeatRows=1)
    tclientes.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), GRIS_OSCURO),
        ('ALIGN',         (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
    ] + row_styles))

    story.append(Paragraph('<b>LISTADO DE CLIENTES</b>', bold_sty))
    story.append(Spacer(1, 5))
    story.append(tclientes)
    story.append(Spacer(1, 9))

    # ══════════════════════════════════════════════════════════════════════════
    # PIE DEL REPORTE
    # ══════════════════════════════════════════════════════════════════════════
    usuario = request.user.get_full_name() or request.user.username
    pie_data = [[
        Paragraph(f'Total registros: <b>{total_clientes}</b>', small_sty),
        Paragraph(
            f'Activos: <b><font color="#27AE60">{activos}</font></b>   '
            f'Inactivos: <b><font color="#C0392B">{inactivos}</font></b>   '
            f'Con crédito: <b><font color="#4A90A4">{con_credito}</font></b>',
            sty('ecP2', fontSize=8, alignment=1)
        ),
        Paragraph(f'Generado por: {usuario}',
                  sty('ecP3', fontSize=8, alignment=2, textColor=GRIS_MEDIO)),
    ]]
    tpie = Table(pie_data, colWidths=[ancho*0.33]*3)
    tpie.setStyle(TableStyle([
        ('LINEABOVE',     (0, 0), (-1, 0), 0.5, GRIS_BORDE),
        ('TOPPADDING',    (0, 0), (-1, 0), 6),
        ('VALIGN',        (0, 0), (-1, 0), 'MIDDLE'),
    ]))
    story.append(tpie)
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        '<b>NOTAS:</b>  Este reporte refleja el estado actual de los clientes registrados '
        'en el sistema al momento de su generación. La columna "Límite Crédito" muestra '
        'el crédito autorizado. Clientes inactivos aparecen resaltados en rojo.',
        sty('ecN', fontSize=7, textColor=GRIS_MEDIO)
    ))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="reporte_clientes_{date.today().strftime("%Y%m%d")}.pdf"'
    )
    response.write(pdf)
    return response


def registrodeclientes(request):
    """Vista para el registro de clientes"""
    # Si es POST y es AJAX
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Obtener datos del formulario
            cedula = request.POST.get('cedula', '').strip()
            nombre_completo = request.POST.get('nombre_completo', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            telefono_principal = request.POST.get(
                'telefono_principal', '').strip()
            telefono_alternativo = request.POST.get(
                'telefono_alternativo', '').strip()

            # Obtener valores numéricos
            limite_credito = request.POST.get('limite_credito', '0')
            dias_credito = request.POST.get('dias_credito', '30')

            # Convertir a tipos correctos
            try:
                limite_credito_decimal = Decimal(limite_credito)
            except:
                limite_credito_decimal = Decimal('0.00')

            try:
                dias_credito_int = int(dias_credito)
            except:
                dias_credito_int = 30

            notas_credito = request.POST.get('notas_credito', '').strip()

            # === VALIDACIONES DEL BACKEND ===

            # Validar cédula
            if not cedula:
                return JsonResponse({
                    'success': False,
                    'error': 'La cédula es requerida'
                })

            # Limpiar cédula (solo números)
            cedula_limpia = ''.join(filter(str.isdigit, cedula))
            if len(cedula_limpia) != 11:
                return JsonResponse({
                    'success': False,
                    'error': 'La cédula debe tener exactamente 11 dígitos'
                })

            # Validar nombre
            if not nombre_completo or len(nombre_completo) < 5:
                return JsonResponse({
                    'success': False,
                    'error': 'El nombre debe tener al menos 5 caracteres'
                })

            # Validar dirección
            if not direccion or len(direccion) < 10:
                return JsonResponse({
                    'success': False,
                    'error': 'La dirección debe tener al menos 10 caracteres'
                })

            # Validar teléfono principal
            telefono_principal_limpio = ''.join(
                filter(str.isdigit, telefono_principal))
            if not telefono_principal_limpio or len(telefono_principal_limpio) != 10:
                return JsonResponse({
                    'success': False,
                    'error': 'El teléfono principal debe tener 10 dígitos'
                })

            # Validar teléfono alternativo si existe
            if telefono_alternativo:
                telefono_alt_limpio = ''.join(
                    filter(str.isdigit, telefono_alternativo))
                if telefono_alt_limpio and len(telefono_alt_limpio) != 10:
                    return JsonResponse({
                        'success': False,
                        'error': 'El teléfono alternativo debe tener 10 dígitos'
                    })
                telefono_alternativo = telefono_alt_limpio
            else:
                telefono_alternativo = None

            # Validar límite de crédito
            if limite_credito_decimal < 0:
                return JsonResponse({
                    'success': False,
                    'error': 'El límite de crédito no puede ser negativo'
                })

            if limite_credito_decimal > 1000000:
                return JsonResponse({
                    'success': False,
                    'error': 'El límite de crédito máximo es $1,000,000'
                })

            # Validar días de crédito
            if dias_credito_int < 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Los días de crédito no pueden ser negativos'
                })

            if dias_credito_int > 365:
                return JsonResponse({
                    'success': False,
                    'error': 'Los días de crédito máximo son 365'
                })

            # Verificar si la cédula ya existe
            if Cliente.objects.filter(cedula=cedula_limpia).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Ya existe un cliente con la cédula {cedula_limpia}'
                })

            # === CREAR CLIENTE ===
            cliente = Cliente.objects.create(
                cedula=cedula_limpia,
                nombre_completo=nombre_completo,
                direccion=direccion,
                telefono_principal=telefono_principal_limpio,
                telefono_alternativo=telefono_alternativo,
                limite_credito=limite_credito_decimal,
                dias_credito=dias_credito_int,
                notas_credito=notas_credito if notas_credito else None,
                registrado_por=request.user if request.user.is_authenticated else None
            )

            # Respuesta exitosa
            return JsonResponse({
                'success': True,
                'mensaje': f'✅ Cliente "{nombre_completo}" registrado exitosamente',
                'cliente': {
                    'id': cliente.id,
                    'cedula': cliente.cedula,
                    'nombre': cliente.nombre_completo,
                    'limite_credito': str(cliente.limite_credito),
                    'dias_credito': cliente.dias_credito
                }
            })

        except IntegrityError as e:
            return JsonResponse({
                'success': False,
                'error': f'Error de integridad en la base de datos: {str(e)}'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error inesperado: {str(e)}'
            })

    # Si es GET, mostrar el formulario
    return render(request, 'facturacion/registrodeclientes.html')


@login_required
def cuentaporcobrar(request):
    """Vista base del módulo de cuentas por cobrar."""
    return render(request, 'facturacion/cuentaporcobrar.html')


def _telefono_solo_digitos(valor):
    return ''.join(ch for ch in str(valor or '') if ch.isdigit())


def _cliente_coincide_con_factura(cliente, factura):
    telefonos_cliente = {
        _telefono_solo_digitos(cliente.telefono_principal),
        _telefono_solo_digitos(cliente.telefono_alternativo),
    }
    telefonos_cliente.discard('')

    telefono_factura = _telefono_solo_digitos(factura.telefono_cliente)
    if telefono_factura and telefono_factura in telefonos_cliente:
        return True

    nombre_cliente = (cliente.nombre_completo or '').strip().lower()
    nombre_factura = (factura.nombre_cliente or '').strip().lower()
    return bool(nombre_cliente and nombre_factura and nombre_cliente == nombre_factura)


def _factura_es_credito(factura):
    """Determina si una factura pertenece al flujo de crédito."""
    notas_pedido = (factura.pedido.notas or '') if getattr(
        factura, 'pedido', None) else ''
    return (
        ('TIPO_PAGO_PEDIDO=credito' in notas_pedido)
        or hasattr(factura, 'cuenta_por_cobrar')
        or factura.pagos_cxc.exists()
    )


def _calcular_saldo_factura_cxc(factura):
    """Saldo real de una factura: ventas - devoluciones - pagos, con piso en cero."""
    total_factura = factura.get_total_neto() if hasattr(
        factura, 'get_total_neto') else Decimal(str(factura.total or 0))
    total_pagado = PagoCuentaCobrar.objects.filter(
        factura=factura
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    total_devuelto = factura.get_total_devuelto() if hasattr(
        factura, 'get_total_devuelto') else Decimal('0.00')

    saldo = total_factura - total_devuelto - total_pagado
    return saldo if saldo > Decimal('0.00') else Decimal('0.00')


def _resumen_movimientos_caja(inicio, fin):
    """
    Resume el movimiento real de caja en un rango de fechas.
    Fuente única de verdad: MovimientoFinanciero.

    PERFORMANCE MEJORADO (v2):
    - Eliminada query secundaria de crédito usando __contains (full table scan)
    - Ahora usa el campo tipo_pago en Factura para detectar crédito (indexado)
    - Reducción de 2 queries a 1 para resumen de caja
    - Llamada 4 veces por request → de ~12-16 queries a 4
    """
    from django.db.models import Sum, Count, Case, When, IntegerField, Q, Exists, OuterRef
    from django.db.models import DecimalField as DField
    from django.db.models.functions import Coalesce
    from django.utils import timezone
    from decimal import Decimal

    if timezone.is_naive(inicio):
        inicio = timezone.make_aware(inicio, timezone.get_current_timezone())
    if timezone.is_naive(fin):
        fin = timezone.make_aware(fin, timezone.get_current_timezone())

    inicio = timezone.localtime(inicio)
    fin = timezone.localtime(fin)

    # ── Query única con Case/When — 1 round-trip al DB ────────────────────
    _Z = Decimal('0.00')
    _D = DField()
    _I = IntegerField()

    # ─ NUEVO: usar tipo_pago en Factura para distinguir crédito (indexado)
    agg = MovimientoFinanciero.objects.filter(
        fecha_operacion__gte=inicio,
        fecha_operacion__lt=fin,
        estado='ACTIVO',
    ).aggregate(
        # INGRESO/VENTA contado — usa tipo_pago indexado
        _iv_contado_total=Coalesce(Sum(Case(
            When(tipo='INGRESO', origen='VENTA',
                 factura__tipo_pago='contado', then='monto'),
            default=_Z, output_field=_D,
        )), _Z),
        _iv_contado_count=Coalesce(Sum(Case(
            When(tipo='INGRESO', origen='VENTA',
                 factura__tipo_pago='contado', then=1),
            default=0, output_field=_I,
        )), 0),
        # INGRESO/VENTA crédito — usa tipo_pago indexado
        _iv_credito_total=Coalesce(Sum(Case(
            When(tipo='INGRESO', origen='VENTA',
                 factura__tipo_pago='credito', then='monto'),
            default=_Z, output_field=_D,
        )), _Z),
        _iv_credito_count=Coalesce(Sum(Case(
            When(tipo='INGRESO', origen='VENTA',
                 factura__tipo_pago='credito', then=1),
            default=0, output_field=_I,
        )), 0),
        # INGRESO/PAGO_CXC
        _ip_total=Coalesce(Sum(Case(
            When(tipo='INGRESO', origen='PAGO_CXC', then='monto'),
            default=_Z, output_field=_D,
        )), _Z),
        _ip_count=Coalesce(Sum(Case(
            When(tipo='INGRESO', origen='PAGO_CXC', then=1),
            default=0, output_field=_I,
        )), 0),
        # EGRESO/DEVOLUCION contado (excluye excedente)
        _edc_total=Coalesce(Sum(Case(
            When(tipo='EGRESO', origen='DEVOLUCION', then=Case(
                When(referencia='EXCEDENTE_DEVOLUCION', then=_Z),
                default='monto', output_field=_D,
            )),
            default=_Z, output_field=_D,
        )), _Z),
        _edc_count=Coalesce(Sum(Case(
            When(tipo='EGRESO', origen='DEVOLUCION', then=Case(
                When(referencia='EXCEDENTE_DEVOLUCION', then=0),
                default=1, output_field=_I,
            )),
            default=0, output_field=_I,
        )), 0),
        # EGRESO/DEVOLUCION excedente
        _ede_total=Coalesce(Sum(Case(
            When(tipo='EGRESO', origen='DEVOLUCION',
                 referencia='EXCEDENTE_DEVOLUCION', then='monto'),
            default=_Z, output_field=_D,
        )), _Z),
        _ede_count=Coalesce(Sum(Case(
            When(tipo='EGRESO', origen='DEVOLUCION',
                 referencia='EXCEDENTE_DEVOLUCION', then=1),
            default=0, output_field=_I,
        )), 0),
        # EGRESO/ANULACION
        _ea_total=Coalesce(Sum(Case(
            When(tipo='EGRESO', origen='ANULACION', then='monto'),
            default=_Z, output_field=_D,
        )), _Z),
        _ea_count=Coalesce(Sum(Case(
            When(tipo='EGRESO', origen='ANULACION', then=1),
            default=0, output_field=_I,
        )), 0),
    )

    # ── Derivar totales ────────────────────────────────────────────────────
    ingreso_venta_contado_total = agg['_iv_contado_total']
    ingreso_venta_contado_count = agg['_iv_contado_count']
    ingreso_venta_credito_total = agg['_iv_credito_total']
    ingreso_venta_credito_count = agg['_iv_credito_count']
    ingreso_venta_total = ingreso_venta_contado_total + ingreso_venta_credito_total
    ingreso_venta_count = ingreso_venta_contado_count + ingreso_venta_credito_count

    ingreso_pagos_total = agg['_ip_total']
    ingreso_pagos_count = agg['_ip_count']
    egreso_dev_contado_total = agg['_edc_total']
    egreso_dev_contado_count = agg['_edc_count']
    egreso_dev_excedente_total = agg['_ede_total']
    egreso_dev_excedente_count = agg['_ede_count']
    egreso_anulacion_total = agg['_ea_total']
    egreso_anulacion_count = agg['_ea_count']

    egreso_dev_total = egreso_dev_contado_total + egreso_dev_excedente_total
    egreso_dev_count = egreso_dev_contado_count + egreso_dev_excedente_count

    ingresos_total = ingreso_venta_total + ingreso_pagos_total
    egresos_total = egreso_dev_total + egreso_anulacion_total
    caja_neta = ingresos_total - egresos_total

    # ── Datos de documentos (para PDF cuadre) — query a Factura ───────────
    facturas_periodo = Factura.objects.filter(
        fecha_factura__gte=inicio,
        fecha_factura__lt=fin,
    )
    doc_agg = facturas_periodo.aggregate(
        contado_pagadas=Coalesce(Sum(Case(
            When(tipo_pago='contado', estado__in=[
                 'pagada', 'parcialmente_devuelta'], then='total'),
            default=_Z, output_field=_D,
        )), _Z),
        credito_pagadas=Coalesce(Sum(Case(
            When(tipo_pago='credito', estado__in=[
                 'pagada', 'parcialmente_devuelta'], then='total'),
            default=_Z, output_field=_D,
        )), _Z),
        anuladas=Coalesce(Sum(Case(
            When(estado='anulada', then='total'),
            default=_Z, output_field=_D,
        )), _Z),
        devueltas=Coalesce(Sum(Case(
            When(estado__in=['parcialmente_devuelta',
                 'totalmente_devuelta'], then='total'),
            default=_Z, output_field=_D,
        )), _Z),
    )

    return {
        # ── Para cards del dashboard ───────────────────────────────────────
        'caja_neta':                            caja_neta,
        'ingresos_total':                       ingresos_total,
        'egresos_total':                        egresos_total,
        'ingreso_venta_total':                  ingreso_venta_total,
        'ingreso_pagos_total':                  ingreso_pagos_total,
        'egreso_devoluciones_total':            egreso_dev_total,
        'egreso_devoluciones_contado_total':    egreso_dev_contado_total,
        'egreso_devoluciones_excedente_total':  egreso_dev_excedente_total,
        'egreso_anulaciones_total':             egreso_anulacion_total,
        # ── Conteos (para subtítulo de cards) ─────────────────────────────
        'ingreso_venta_count':                  ingreso_venta_count,
        'ingreso_pagos_count':                  ingreso_pagos_count,
        'egreso_devoluciones_contado_count':    egreso_dev_contado_count,
        'egreso_devoluciones_excedente_count':  egreso_dev_excedente_count,
        'egreso_devoluciones_count':            egreso_dev_count,
        'egreso_anulaciones_count':             egreso_anulacion_count,
        # ── Para PDF de cuadre (datos de documentos) ──────────────────────
        'total_ventas_contado_doc':             doc_agg['contado_pagadas'],
        'total_ventas_credito_doc':             doc_agg['credito_pagadas'],
        'total_anulaciones_doc':                doc_agg['anuladas'],
        'total_devoluciones_doc':               doc_agg['devueltas'],
    }


def _sincronizar_movimientos_factura(factura):
    """
    Sincroniza los MovimientoFinanciero con el estado actual de la factura.

    Reglas:
    - Si factura es 'anulada' o 'totalmente_devuelta': marca movimientos INACTIVOS
    - Si factura es 'pagada' o 'parcialmente_devuelta': marca movimientos ACTIVOS
    - Si cambió el monto: actualiza cantidad en movimiento de VENTA
    """
    if not factura or not hasattr(factura, 'id'):
        return

    movimientos = MovimientoFinanciero.objects.filter(factura=factura)

    if factura.estado in ['anulada', 'totalmente_devuelta']:
        # Marcar como inactivos para excluir del dashboard
        movimientos.update(estado='INACTIVO')
    else:
        # Para facturas activas (pagada, parcialmente_devuelta, pendiente):
        # Solo reactivar los que estén INACTIVO — nunca tocar el monto,
        # porque cada movimiento ya tiene su monto correcto (venta, pago, devolución, etc.)
        movimientos.filter(estado='INACTIVO').update(estado='ACTIVO')


def _resumen_movimientos_caja_cached(inicio, fin):
    return _resumen_movimientos_caja(inicio, fin)


def _facturas_que_cuentan_en_cards(queryset):
    """
    Facturas que deben contarse en las cards del dashboard.

    SOLO incluyen:
    - Ventas a CONTADO estado 'pagada'
    - Ventas a CONTADO estado 'parcialmente_devuelta'

    EXCLUYEN:
    - Todas las ventas a CRÉDITO (sin importar estado)
    - Facturas anuladas
    - Facturas totalmente devueltas
    """
    from django.db.models import Q

    # Excluir anuladas y totalmente devueltas
    qs = queryset.exclude(estado__in=['anulada', 'totalmente_devuelta'])

    # Filtrar solo pagadas o parcialmente devueltas
    qs = qs.filter(estado__in=['pagada', 'parcialmente_devuelta'])

    # Excluir facturas de CRÉDITO (tienen CuentaPorCobrar vinculada)
    qs = qs.exclude(cuenta_por_cobrar__isnull=False)

    # Excluir facturas donde el pedido tiene TIPO_PAGO_PEDIDO=credito en notas
    qs = qs.exclude(pedido__notas__contains='TIPO_PAGO_PEDIDO=credito')

    return qs


def _calcular_saldo_credito_cliente(cliente, facturas_pendientes=None):
    """Saldo usado por el cliente: CxC vinculadas + pendientes coincidentes no vinculadas."""
    saldo = Decimal('0.00')
    facturas_contabilizadas = set()

    cuentas_cliente = CuentaPorCobrar.objects.filter(cliente=cliente).select_related(
        'factura').prefetch_related('factura__pagos_cxc')
    for cuenta in cuentas_cliente:
        factura = cuenta.factura
        if not factura:
            continue
        facturas_contabilizadas.add(factura.id)
        saldo += _saldo_factura_pendiente(factura)

    if facturas_pendientes is None:
        facturas_pendientes = list(
            Factura.objects.filter(
                estado__in=['pendiente', 'parcialmente_devuelta']
            ).prefetch_related('pagos_cxc', 'devoluciones')
        )

    for factura in facturas_pendientes:
        if factura.id in facturas_contabilizadas:
            continue
        if _cliente_coincide_con_factura(cliente, factura):
            saldo += _saldo_factura_pendiente(factura)
            facturas_contabilizadas.add(factura.id)

    return saldo if saldo > 0 else Decimal('0.00')


def _saldo_factura_pendiente(factura):
    # Calcular desde DB para evitar datos stale cuando hay prefetch de pagos.
    if factura.estado in ['anulada', 'totalmente_devuelta']:
        return Decimal('0.00')

    # CxC solo aplica para ventas a crédito.
    if not _factura_es_credito(factura):
        return Decimal('0.00')

    return _calcular_saldo_factura_cxc(factura)


def _calcular_fechas_cxc(factura, cliente_match=None):
    tz_rd = pytz.timezone('America/Santo_Domingo')
    fecha_base = factura.fecha_factura or timezone.now()
    fecha_emision = timezone.localtime(fecha_base, tz_rd).date(
    ) if timezone.is_aware(fecha_base) else fecha_base.date()

    dias_credito = 30
    if cliente_match and cliente_match.dias_credito is not None:
        dias_credito = max(0, int(cliente_match.dias_credito))

    fecha_vencimiento = fecha_emision + timedelta(days=dias_credito)
    return fecha_emision, fecha_vencimiento


def _sincronizar_cuenta_por_cobrar(factura, cliente_match=None):
    # No crear/sincronizar CxC para contado.
    if not _factura_es_credito(factura):
        return None

    fecha_emision, fecha_vencimiento = _calcular_fechas_cxc(
        factura, cliente_match)
    total_factura = factura.get_total_neto() if hasattr(
        factura, 'get_total_neto') else Decimal(str(factura.total or 0))

    defaults = {
        'cliente': cliente_match,
        'fecha_emision': fecha_emision,
        'fecha_vencimiento': fecha_vencimiento,
        'monto_original': total_factura,
        'saldo_pendiente': total_factura,
        'estado': 'pendiente',
        'notas': factura.notas or '',
    }
    cuenta, created = CuentaPorCobrar.objects.get_or_create(
        factura=factura, defaults=defaults)

    saldo = _calcular_saldo_factura_cxc(factura)

    hoy = timezone.localdate()
    if factura.estado == 'anulada':
        estado = 'anulada'
    elif saldo <= 0:
        estado = 'pagada'
    elif saldo < total_factura:
        estado = 'vencida' if cuenta.fecha_vencimiento < hoy else 'parcial'
    else:
        estado = 'vencida' if cuenta.fecha_vencimiento < hoy else 'pendiente'

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
    if cuenta.estado != estado:
        cuenta.estado = estado
        cambios.append('estado')
    if cuenta.notas != (factura.notas or ''):
        cuenta.notas = factura.notas or ''
        cambios.append('notas')

    if cambios:
        cuenta.save(update_fields=sorted(
            set(cambios + ['fecha_actualizacion'])))
    elif created:
        cuenta.save()

    return cuenta


def _armar_clientes_cuentas_por_cobrar():
    tz_rd = pytz.timezone('America/Santo_Domingo')
    hoy_local = timezone.now().astimezone(tz_rd).date()

    clientes = Cliente.objects.all()
    cliente_por_telefono = {}
    cliente_por_nombre = {}

    for cliente in clientes:
        tel_principal = _telefono_solo_digitos(cliente.telefono_principal)
        tel_alt = _telefono_solo_digitos(cliente.telefono_alternativo)
        if tel_principal:
            cliente_por_telefono[tel_principal] = cliente
        if tel_alt:
            cliente_por_telefono[tel_alt] = cliente

        nombre_key = (cliente.nombre_completo or '').strip().lower()
        if nombre_key and nombre_key not in cliente_por_nombre:
            cliente_por_nombre[nombre_key] = cliente

    # Asegura sincronización de facturas con deuda activa y devoluciones parciales.
    for factura in Factura.objects.filter(
        estado__in=['pendiente', 'parcialmente_devuelta']
    ).prefetch_related('pagos_cxc', 'devoluciones'):
        if not _factura_es_credito(factura):
            continue

        nombre_factura = (factura.nombre_cliente or '').strip()
        telefono_factura = _telefono_solo_digitos(factura.telefono_cliente)

        cliente_match = None
        if telefono_factura and telefono_factura in cliente_por_telefono:
            cliente_match = cliente_por_telefono[telefono_factura]
        elif nombre_factura and nombre_factura.lower() in cliente_por_nombre:
            cliente_match = cliente_por_nombre[nombre_factura.lower()]

        _sincronizar_cuenta_por_cobrar(factura, cliente_match)

    # Para la tabla: todas las cuentas
    cuentas = CuentaPorCobrar.objects.select_related('factura', 'cliente').prefetch_related(
        'factura__pagos_cxc',
        'factura__devoluciones',
    ).order_by('fecha_emision', 'id')

    agrupados = {}
    for cuenta in cuentas:
        factura = cuenta.factura
        if not factura or not _factura_es_credito(factura):
            continue

        saldo = _saldo_factura_pendiente(factura)

        nombre_factura = (factura.nombre_cliente or '').strip()
        telefono_factura = _telefono_solo_digitos(factura.telefono_cliente)

        cliente_match = None
        if telefono_factura and telefono_factura in cliente_por_telefono:
            cliente_match = cliente_por_telefono[telefono_factura]
        elif nombre_factura and nombre_factura.lower() in cliente_por_nombre:
            cliente_match = cliente_por_nombre[nombre_factura.lower()]

        if telefono_factura:
            group_key = f"tel:{telefono_factura}"
        elif nombre_factura:
            group_key = f"nom:{nombre_factura.lower()}"
        else:
            group_key = f"fac:{factura.id}"

        if group_key not in agrupados:
            nombre_ui = (
                cliente_match.nombre_completo if cliente_match else nombre_factura) or 'Cliente no identificado'
            telefono_ui = (
                cliente_match.telefono_principal if cliente_match else factura.telefono_cliente) or ''
            agrupados[group_key] = {
                'group_key': group_key,
                'cedula': cliente_match.cedula if cliente_match else 'N/A',
                'nombre_completo': nombre_ui,
                'telefono': telefono_ui,
                'email': '',
                'direccion': cliente_match.direccion if cliente_match else '',
                'tipo_cliente': 'Con credito' if (cliente_match and (cliente_match.limite_credito or Decimal('0.00')) > 0) else 'Regular',
                'notas': cliente_match.notas_credito if cliente_match else '',
                'facturas': [],
                'historial_pagos': [],
            }

        fecha_emision = cuenta.fecha_emision
        fecha_vencimiento = cuenta.fecha_vencimiento
        dias_vencimiento = (fecha_vencimiento - hoy_local).days

        productos_originales = []
        for item in factura.get_items_detalle():
            cantidad_item = Decimal(str(item.get('cantidad', 0)))
            precio_item = Decimal(str(item.get('precio', 0)))
            subtotal_item = Decimal(
                str(item.get('subtotal', cantidad_item * precio_item)))
            productos_originales.append({
                'nombre': item.get('nombre', 'Producto'),
                'codigo': item.get('codigo', ''),
                'categoria': item.get('categoria', ''),
                'cantidad': float(cantidad_item),
                'precio_unitario': float(precio_item),
                'subtotal': float(subtotal_item),
            })

        productos_devueltos_map = {}
        for devolucion in factura.devoluciones.prefetch_related('detalles'):
            detalles = list(devolucion.detalles.all())
            if detalles:
                for detalle in detalles:
                    nombre = (
                        detalle.nombre_producto or '').strip() or 'Producto'
                    key = nombre.lower()
                    cantidad = Decimal(str(detalle.cantidad or 0))
                    precio = Decimal(str(detalle.precio_unitario or 0))
                    subtotal = Decimal(
                        str(detalle.monto or (cantidad * precio)))
                    if key not in productos_devueltos_map:
                        productos_devueltos_map[key] = {
                            'nombre': nombre,
                            'cantidad': Decimal('0.00'),
                            'precio_unitario': precio,
                            'subtotal': Decimal('0.00'),
                        }
                    productos_devueltos_map[key]['cantidad'] += cantidad
                    productos_devueltos_map[key]['subtotal'] += subtotal
                continue

            for item in (devolucion.productos_devueltos or []):
                nombre = str(item.get('nombre') or '').strip() or 'Producto'
                key = nombre.lower()
                cantidad = Decimal(str(item.get('cantidad', 0)))
                precio = Decimal(
                    str(item.get('precio_unitario', item.get('precio', 0))))
                subtotal = Decimal(
                    str(item.get('subtotal', cantidad * precio)))
                if key not in productos_devueltos_map:
                    productos_devueltos_map[key] = {
                        'nombre': nombre,
                        'cantidad': Decimal('0.00'),
                        'precio_unitario': precio,
                        'subtotal': Decimal('0.00'),
                    }
                productos_devueltos_map[key]['cantidad'] += cantidad
                productos_devueltos_map[key]['subtotal'] += subtotal

        productos_devueltos = [
            {
                'nombre': data['nombre'],
                'cantidad': float(data['cantidad']),
                'precio_unitario': float(data['precio_unitario']),
                'subtotal': float(data['subtotal']),
            }
            for data in productos_devueltos_map.values()
        ]

        agrupados[group_key]['facturas'].append({
            'id': factura.id,
            'numero': factura.numero_factura,
            'fecha_emision': fecha_emision.isoformat(),
            'fecha_vencimiento': fecha_vencimiento.isoformat(),
            'dias_vencimiento': dias_vencimiento,
            'vencida': dias_vencimiento < 0,
            'monto_total': float(factura.total or Decimal('0.00')),
            'saldo_pendiente': float(saldo),
            'estado_cuenta': cuenta.estado,
            'estado_factura': factura.estado,
            'concepto': factura.notas or f"Factura {factura.numero_factura}",
            'descripcion': factura.notas or '',
            'notas': factura.notas or '',
            'productos_originales': productos_originales,
            'productos_devueltos': productos_devueltos,
        })

        for pago in factura.pagos_cxc.all():
            metodo_label = dict(PagoCuentaCobrar.METODO_PAGO_CHOICES).get(
                pago.metodo_pago, pago.metodo_pago)
            agrupados[group_key]['historial_pagos'].append({
                'fecha': pago.fecha_pago.isoformat(),
                'monto': float(pago.monto),
                'metodo': metodo_label,
                'referencia': pago.referencia or '',
                'numero_comprobante': pago.numero_comprobante or '',
                'numero_factura': factura.numero_factura or '',
            })

    clientes_payload = []
    for idx, data in enumerate(agrupados.values(), start=1):
        # Orden requerido en CxC: primero facturas con saldo pendiente, luego pagadas;
        # dentro de cada grupo, las más nuevas arriba.
        data['facturas'].sort(key=lambda x: x.get(
            'fecha_emision') or '', reverse=True)
        data['facturas'].sort(key=lambda x: float(
            x.get('saldo_pendiente') or 0) <= 0)
        data['historial_pagos'].sort(key=lambda x: x['fecha'], reverse=True)

        total_adeudado = sum(item['saldo_pendiente']
                             for item in data['facturas'])
        facturas_vencidas = sum(
            1 for item in data['facturas'] if item['vencida'] and item['saldo_pendiente'] > 0)
        deuda_vencida = sum(item['saldo_pendiente'] for item in data['facturas']
                            if item['vencida'] and item['saldo_pendiente'] > 0)

        if total_adeudado >= 20000:
            nivel_deuda = 'alta'
        elif total_adeudado >= 7000:
            nivel_deuda = 'media'
        else:
            nivel_deuda = 'baja'

        clientes_payload.append({
            'id': idx,
            'group_key': data['group_key'],
            'cedula': data['cedula'],
            'nombre_completo': data['nombre_completo'],
            'telefono': data['telefono'],
            'email': data['email'],
            'direccion': data['direccion'],
            'tipo_cliente': data['tipo_cliente'],
            'notas': data['notas'],
            'cantidad_facturas': len(data['facturas']),
            'facturas_vencidas': facturas_vencidas,
            'total_adeudado': float(total_adeudado),
            'deuda_vencida': float(deuda_vencida),
            'nivel_deuda': nivel_deuda,
            'facturas': data['facturas'],
            'historial_pagos': data['historial_pagos'],
        })

    clientes_payload.sort(key=lambda x: x['total_adeudado'], reverse=True)
    return clientes_payload


@login_required
def cuentaporcobrar_datos(request):
    """Retorna datos reales para la tabla de cuentas por cobrar."""
    clientes = _armar_clientes_cuentas_por_cobrar()
    facturas_pendientes = sum(
        1
        for cliente in clientes
        for factura in cliente.get('facturas', [])
        if float(factura.get('saldo_pendiente') or 0) > 0
    )
    clientes_con_deuda = sum(1 for cliente in clientes if float(
        cliente.get('total_adeudado') or 0) > 0)
    return JsonResponse({'success': True, 'clientes': clientes, 'facturas_pendientes': facturas_pendientes, 'clientes_con_deuda': clientes_con_deuda})


@login_required
def historial_pagos(request):
    import pytz
    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    fecha_reporte = ahora_local.strftime('%d/%m/%Y %I:%M %p')

    # Parámetros de filtrado
    search = request.GET.get('search', '').strip()
    metodo_pago = request.GET.get('metodo_pago', '')
    fecha = request.GET.get('fecha', '')
    page = int(request.GET.get('page', 1))

    # Consulta base: TODOS los pagos
    pagos_base = PagoCuentaCobrar.objects.select_related(
        'factura', 'cuenta_por_cobrar', 'registrado_por')
    pagos = pagos_base.order_by('-fecha_pago')

    # Filtros
    if search:
        pagos = pagos.filter(
            Q(factura__numero_factura__icontains=search) |
            Q(factura__nombre_cliente__icontains=search) |
            Q(numero_comprobante__icontains=search)
        )
    if metodo_pago:
        pagos = pagos.filter(metodo_pago=metodo_pago)
    if fecha:
        inicio_hoy = ahora_local.replace(
            hour=0, minute=0, second=0, microsecond=0)
        fin_hoy = inicio_hoy + timedelta(days=1)
        inicio_mes_actual = inicio_hoy.replace(day=1)

        if fecha == 'hoy':
            pagos = pagos.filter(fecha_pago__gte=inicio_hoy,
                                 fecha_pago__lt=fin_hoy)
        elif fecha == 'ayer':
            inicio_ayer = inicio_hoy - timedelta(days=1)
            pagos = pagos.filter(fecha_pago__gte=inicio_ayer,
                                 fecha_pago__lt=inicio_hoy)
        elif fecha in ['ultimos_7_dias', 'semana']:
            inicio_7_dias = inicio_hoy - timedelta(days=6)
            pagos = pagos.filter(
                fecha_pago__gte=inicio_7_dias, fecha_pago__lt=fin_hoy)
        elif fecha == 'ultimos_30_dias':
            inicio_30_dias = inicio_hoy - timedelta(days=29)
            pagos = pagos.filter(
                fecha_pago__gte=inicio_30_dias, fecha_pago__lt=fin_hoy)
        elif fecha in ['este_mes', 'mes']:
            pagos = pagos.filter(
                fecha_pago__gte=inicio_mes_actual, fecha_pago__lt=fin_hoy)
        elif fecha == 'mes_pasado':
            fin_mes_pasado = inicio_mes_actual
            ultimo_dia_mes_pasado = inicio_mes_actual - timedelta(days=1)
            inicio_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
            pagos = pagos.filter(
                fecha_pago__gte=inicio_mes_pasado, fecha_pago__lt=fin_mes_pasado)
        elif fecha == 'este_anio':
            inicio_anio = inicio_hoy.replace(month=1, day=1)
            pagos = pagos.filter(
                fecha_pago__gte=inicio_anio, fecha_pago__lt=fin_hoy)
        elif fecha == 'semana_actual':
            inicio_semana = (
                inicio_hoy - timedelta(days=ahora_local.weekday()))
            pagos = pagos.filter(
                fecha_pago__gte=inicio_semana, fecha_pago__lt=fin_hoy)

    # Paginación de 50 pagos por página
    paginator = Paginator(pagos, 50)
    page_obj = paginator.get_page(page)

    # Procesar pagos para template
    pagos_procesados = []
    for pago in page_obj:
        fecha_base = pago.fecha_pago or timezone.now()
        fecha_local = timezone.localtime(fecha_base, tz_rd)
        if pago.registrado_por:
            nombre = pago.registrado_por.get_full_name()
            if not nombre:
                nombre = pago.registrado_por.username
        else:
            nombre = ''
        pagos_procesados.append({
            'id': pago.id,
            'numero_comprobante': pago.numero_comprobante or 'Sin comprobante',
            'factura_numero': pago.factura.numero_factura if pago.factura else 'Sin factura',
            'nombre_cliente': pago.factura.nombre_cliente if pago.factura else 'Cliente no registrado',
            'monto': float(pago.monto or 0),
            'metodo_pago': pago.metodo_pago or '',
            'fecha_formateada': fecha_local.strftime('%d/%m/%Y %I:%M %p'),
            'registrado_por': nombre,
        })

    # Estadísticas
    total_pagos = pagos.count()
    ingresos_totales = pagos.filter().aggregate(
        total=models.Sum('monto'))['total'] or 0

    # Estadísticas mensuales y anuales (sobre TODOS los pagos, no solo filtrados)
    inicio_mes_rd = ahora_local.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_hoy_rd = ahora_local.replace(
        hour=0, minute=0, second=0, microsecond=0)
    fin_hoy_rd = inicio_hoy_rd + timedelta(days=1)
    pagos_mes_actual = pagos_base.filter(
        fecha_pago__gte=inicio_mes_rd, fecha_pago__lt=fin_hoy_rd)
    ingresos_mes_actual = pagos_mes_actual.aggregate(
        total=models.Sum('monto'))['total'] or 0
    total_pagos_mes = pagos_mes_actual.count()

    context = {
        'pagos': pagos_procesados,
        'paginator': paginator,
        'page_obj': page_obj,
        'filtros': {
            'search': search,
            'metodo_pago': metodo_pago,
            'fecha': fecha,
        },
        'estadisticas': {
            'total_pagos': total_pagos,
            'ingresos_totales': ingresos_totales,
            'ingresos_mes_actual': ingresos_mes_actual,
            'total_pagos_mes': total_pagos_mes,
        },
        'fecha_reporte': fecha_reporte,
    }
    return render(request, 'facturacion/historial_pagos.html', context)


@login_required
def cuentaporcobrar_comprobante_pdf(request):
    """Genera un comprobante PDF en formato termico 80mm para pagos de CxC."""
    pagos_param = (request.GET.get('pagos') or '').strip()
    if not pagos_param:
        return HttpResponse('Debe indicar pagos para generar el comprobante.', status=400)

    try:
        pago_ids = [int(pid.strip())
                    for pid in pagos_param.split(',') if pid.strip()]
    except ValueError:
        return HttpResponse('Formato de pagos invalido.', status=400)

    pagos = list(
        PagoCuentaCobrar.objects.filter(id__in=pago_ids)
        .select_related('factura', 'registrado_por')
        .order_by('fecha_pago', 'id')
    )
    if not pagos:
        return HttpResponse('No se encontraron pagos para el comprobante.', status=404)

    factura_ids = {p.factura_id for p in pagos}
    pagos_facturas = list(
        PagoCuentaCobrar.objects.filter(factura_id__in=factura_ids)
        .only('id', 'factura_id', 'monto', 'fecha_pago')
        .order_by('fecha_pago', 'id')
    )

    total_factura_por_id = {}
    for pago in pagos:
        total_factura_por_id[pago.factura_id] = Decimal(
            str(pago.factura.total or '0'))

    acumulado_por_factura = {factura_id: Decimal(
        '0.00') for factura_id in factura_ids}
    resumen_por_pago = {}
    for pago_hist in pagos_facturas:
        total_factura = total_factura_por_id.get(
            pago_hist.factura_id, Decimal('0.00'))
        acumulado_por_factura[pago_hist.factura_id] += Decimal(
            str(pago_hist.monto or '0'))

        saldo_actual = total_factura - \
            acumulado_por_factura[pago_hist.factura_id]
        if saldo_actual < Decimal('0.00'):
            saldo_actual = Decimal('0.00')

        saldo_anterior = saldo_actual + Decimal(str(pago_hist.monto or '0'))
        if saldo_anterior > total_factura:
            saldo_anterior = total_factura

        resumen_por_pago[pago_hist.id] = {
            'saldo_anterior': saldo_anterior,
            'saldo_actual': saldo_actual,
        }

    ancho_ticket = 80 * mm
    alto_linea = 4 * mm
    lineas_encabezado = 14
    lineas_por_pago = 13
    lineas_pie = 6
    alto_ticket = (lineas_encabezado + (len(pagos) *
                   lineas_por_pago) + lineas_pie) * alto_linea
    if alto_ticket < (120 * mm):
        alto_ticket = 120 * mm

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="comprobante_cxc_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.pdf"'

    c = canvas.Canvas(response, pagesize=(ancho_ticket, alto_ticket))
    y = alto_ticket - 8 * mm

    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    total_pagado = sum((p.monto for p in pagos), Decimal('0.00'))

    def _format_money(value):
        return f'RD$ {Decimal(str(value or 0)):,.2f}'

    def _draw_label_value(y_pos, label, value, label_x=5 * mm):
        # Etiqueta en negrita y valor en regular; posicion dinamica para evitar solapes.
        label_text = f'{label}:'
        c.setFont('Helvetica-Bold', 8)
        c.drawString(label_x, y_pos, label_text)

        label_width = c.stringWidth(label_text, 'Helvetica-Bold', 8)
        value_x = label_x + label_width + (2 * mm)
        c.setFont('Helvetica', 8)
        c.drawString(value_x, y_pos, str(value))

    no_transaccion_general = pagos[0].id if pagos else 0
    # Encabezado del negocio con logo
    try:
        logo_path = os.path.join(
            settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'img', 'fastfood.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(
                settings.BASE_DIR, 'static', 'img', 'fastfood.png')

        if os.path.exists(logo_path):
            logo_size = 14 * mm
            logo_x = (ancho_ticket - logo_size) / 2
            c.drawImage(logo_path, logo_x, y - logo_size, width=logo_size,
                        height=logo_size, preserveAspectRatio=True, mask='auto')
            y -= (logo_size + 2 * mm)
    except Exception:
        pass

    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(ancho_ticket / 2, y, '402 FASTFOOD')
    y -= alto_linea
    c.setFont('Helvetica', 7)
    c.drawCentredString(ancho_ticket / 2, y, 'RNC: 00000000')
    y -= alto_linea
    c.drawCentredString(
        ancho_ticket / 2, y, 'Direccion: Castanuelas, calle 30 de mayo frente a la bomba')
    y -= alto_linea
    c.drawCentredString(ancho_ticket / 2, y, 'Telefono: 849-362-1791')
    y -= alto_linea

    c.line(5 * mm, y, ancho_ticket - 5 * mm, y)
    y -= alto_linea

    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(ancho_ticket / 2, y, 'COMPROBANTE DE PAGO')
    y -= alto_linea
    _draw_label_value(y, 'Generado', ahora_local.strftime('%d/%m/%Y %I:%M %p'))
    y -= alto_linea
    c.setFont('Helvetica', 7)
    c.drawRightString(ancho_ticket - 5 * mm, y,
                      f'Recibo: #{no_transaccion_general}')
    y -= alto_linea

    for pago in pagos:
        resumen_pago = resumen_por_pago.get(pago.id, {
            'saldo_anterior': Decimal('0.00'),
            'saldo_actual': Decimal('0.00'),
        })
        saldo_anterior = resumen_pago['saldo_anterior']
        saldo_actual = resumen_pago['saldo_actual']
        tipo_comprobante = 'Factura saldada' if saldo_actual <= Decimal(
            '0.00') else 'Abono'

        numero_comprobante = pago.numero_comprobante or f'CP-{pago.id}'
        numero_factura = pago.factura.numero_factura or f'FACT-{pago.factura_id}'
        cliente_nombre = (
            pago.factura.nombre_cliente or 'Cliente general')[:34]
        metodo = pago.get_metodo_pago_display() if hasattr(
            pago, 'get_metodo_pago_display') else (pago.metodo_pago or 'N/A')
        referencia = (pago.referencia or 'N/A')[:34]

        if pago.registrado_por:
            nombre_usuario = (pago.registrado_por.get_full_name(
            ) or pago.registrado_por.username or 'N/A').strip()
        else:
            nombre_usuario = 'N/A'

        c.line(5 * mm, y, ancho_ticket - 5 * mm, y)
        y -= alto_linea
        _draw_label_value(y, 'Comprobante', numero_comprobante[:28])
        y -= alto_linea

        fecha_pago_local = pago.fecha_pago
        if timezone.is_naive(fecha_pago_local):
            fecha_pago_local = timezone.make_aware(
                fecha_pago_local, timezone.get_current_timezone())
        fecha_pago_local = timezone.localtime(fecha_pago_local, tz_rd)
        _draw_label_value(
            y, 'Fecha pago', fecha_pago_local.strftime('%d/%m/%Y'))
        y -= alto_linea
        _draw_label_value(y, 'Tipo', tipo_comprobante)
        y -= alto_linea
        _draw_label_value(y, 'Cliente', cliente_nombre)
        y -= alto_linea
        _draw_label_value(y, 'Factura', numero_factura[:30])
        y -= alto_linea
        _draw_label_value(y, 'Monto pagado', _format_money(pago.monto))
        y -= alto_linea
        _draw_label_value(y, 'Balance anterior', _format_money(saldo_anterior))
        y -= alto_linea
        _draw_label_value(y, 'Balance actual', _format_money(saldo_actual))
        y -= alto_linea
        _draw_label_value(y, 'Metodo pago', metodo[:28])
        y -= alto_linea
        _draw_label_value(y, 'Referencia', referencia)
        y -= alto_linea
        _draw_label_value(y, 'Despachado por', nombre_usuario[:28])
        y -= alto_linea

        # ...no imprimir firma aquí...
        y -= (alto_linea - 1 * mm)
        y -= 1 * mm

    c.line(5 * mm, y, ancho_ticket - 5 * mm, y)
    y -= alto_linea
    c.setFont('Helvetica-Bold', 9)
    c.drawString(5 * mm, y, 'TOTAL PAGADO')
    c.drawRightString(ancho_ticket - 5 * mm, y, _format_money(total_pagado))
    y -= (alto_linea + 1 * mm)

    c.setFont('Helvetica-Oblique', 7)
    c.drawCentredString(ancho_ticket / 2, y, 'Gracias por su pago')
    y -= alto_linea

    # Firma UUID de pago (centrada, negro para impresora térmica, pequeña, debajo del mensaje de gracias)
    uuid_firmas = [str(p.uuid_pago)
                   for p in pagos if hasattr(p, 'uuid_pago') and p.uuid_pago]
    if uuid_firmas:
        c.setFont('Helvetica-Oblique', 6)
        # Negro para que se vea en impresora térmica
        c.setFillColorRGB(0, 0, 0)
        if len(uuid_firmas) == 1:
            c.drawCentredString(ancho_ticket / 2, y,
                                f"Firma: {uuid_firmas[0]}")
        else:
            # Si hay varios pagos, concatenar UUIDs separados por espacio
            c.drawCentredString(ancho_ticket / 2, y,
                                "Firmas: " + " ".join(uuid_firmas))
        y -= alto_linea

    c.showPage()
    c.save()
    return response


@login_required
@require_POST
def cuentaporcobrar_registrar_pago(request):
    """Registra pago por factura puntual o por cliente (distribuido)."""

    # ── Parse payload ──────────────────────────────────────────────────────────
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = request.POST

    # ── Monto ─────────────────────────────────────────────────────────────────
    try:
        monto = Decimal(str(payload.get('monto') or '0'))
    except Exception:
        monto = Decimal('0.00')

    if monto <= 0:
        return JsonResponse(
            {'success': False, 'error': 'El monto debe ser mayor que 0.'},
            status=400
        )

    # ── Fecha de pago ─────────────────────────────────────────────────────────
    fecha_pago_raw = str(payload.get('fecha_pago') or '').strip()
    fecha_pago = None
    tz_actual = timezone.get_current_timezone()
    ahora_local = timezone.localtime(timezone.now(), tz_actual)
    if fecha_pago_raw:
        try:
            fecha_sola = datetime.strptime(fecha_pago_raw, '%Y-%m-%d').date()
            fecha_pago = datetime.combine(fecha_sola, ahora_local.time())
        except Exception:
            return JsonResponse(
                {'success': False, 'error': 'Fecha de pago inválida.'},
                status=400
            )

    if not fecha_pago:
        fecha_pago = ahora_local

    if timezone.is_naive(fecha_pago):
        fecha_pago = timezone.make_aware(fecha_pago, tz_actual)
    else:
        fecha_pago = timezone.localtime(fecha_pago, tz_actual)

    # ── Método de pago ────────────────────────────────────────────────────────
    metodo_pago = (payload.get('metodo_pago') or 'efectivo').strip()
    metodos_validos = {item[0]
                       for item in PagoCuentaCobrar.METODO_PAGO_CHOICES}
    if metodo_pago not in metodos_validos:
        metodo_pago = 'efectivo'

    referencia = (payload.get('referencia') or '').strip()
    notas = (payload.get('notas') or '').strip()

    # ── Pago completo ─────────────────────────────────────────────────────────
    raw_pago_completo = payload.get('pago_completo', True)
    if isinstance(raw_pago_completo, bool):
        pago_completo = raw_pago_completo
    else:
        pago_completo = str(raw_pago_completo).strip().lower() in {
            '1', 'true', 'si', 'sí', 'on'}

    # ── Identificadores ───────────────────────────────────────────────────────
    factura_id = payload.get('factura_id')
    cliente_nombre = (payload.get('cliente_nombre') or '').strip()
    cliente_telefono = _telefono_solo_digitos(payload.get('cliente_telefono'))

    # ── UUID — OBLIGATORIO desde el frontend ──────────────────────────────────
    # El UUID debe generarse en el cliente ANTES de enviar el form.
    # Si el backend lo genera, la idempotencia no funciona porque cada
    # reenvío produce un UUID diferente → pago duplicado.
    uuid_pago = (payload.get('uuid_pago') or '').strip()
    if not uuid_pago:
        return JsonResponse(
            {'success': False, 'error': 'uuid_pago es requerido. Debe generarse en el frontend antes de enviar.'},
            status=400
        )

    # =========================================================================
    # CASO 1 — Pago a una factura específica
    # =========================================================================
    if factura_id:
        with transaction.atomic():
            factura = get_object_or_404(
                Factura.objects.exclude(
                    estado='pagada').prefetch_related('pagos_cxc'),
                id=factura_id
            )
            cuenta = _sincronizar_cuenta_por_cobrar(factura)
            saldo_actual = _saldo_factura_pendiente(factura)

            if saldo_actual <= 0:
                return JsonResponse(
                    {'success': False, 'error': 'La factura no tiene saldo pendiente.'},
                    status=400
                )
            if monto > saldo_actual:
                return JsonResponse(
                    {'success': False,
                        'error': f'El monto excede el saldo pendiente (RD$ {saldo_actual}).'},
                    status=400
                )

            # ── Idempotencia con get_or_create para evitar race condition ────
            try:
                pago_registrado, creado = PagoCuentaCobrar.objects.get_or_create(
                    uuid_pago=uuid_pago,
                    defaults={
                        'cuenta_por_cobrar': cuenta,
                        'factura':           factura,
                        'monto':             monto,
                        'fecha_pago':        fecha_pago,
                        'metodo_pago':       metodo_pago,
                        'referencia':        referencia,
                        'notas':             notas,
                        'registrado_por':    request.user if request.user.is_authenticated else None,
                    }
                )
            except IntegrityError:
                # Dos requests simultáneos con el mismo UUID: el segundo llega aquí
                pago_registrado = PagoCuentaCobrar.objects.get(
                    uuid_pago=uuid_pago)
                creado = False

            # ── Pago duplicado — devolver info para reimpresión ──────────────
            if not creado:
                comprobante_url = (
                    f"{reverse('cuentaporcobrar_comprobante_pdf')}?pagos={pago_registrado.id}"
                    if pago_registrado.id else ''
                )
                return JsonResponse({
                    'success':          True,
                    'mensaje':          'Pago ya registrado previamente.',
                    'pago_id':          pago_registrado.id,
                    'uuid_pago':        str(pago_registrado.uuid_pago),
                    'comprobante_url':  comprobante_url,
                    'reimpresion':      True,
                })

            # ── Pago nuevo — sincronizar saldo y cerrar factura si aplica ────
            comprobante_url = (
                f"{reverse('cuentaporcobrar_comprobante_pdf')}?pagos={pago_registrado.id}"
            )
            _sincronizar_cuenta_por_cobrar(factura)

            if _saldo_factura_pendiente(factura) <= 0:
                factura.estado = 'pagada'
                factura.metodo_pago = metodo_pago
                factura.save(update_fields=['estado', 'metodo_pago'])

                # Sincronizar movimientos financieros
                _sincronizar_movimientos_factura(factura)

            # Registrar ingreso financiero por pago de CxC
            MovimientoFinanciero.objects.create(
                tipo="INGRESO",
                origen="PAGO_CXC",
                monto=monto,
                fecha_operacion=fecha_pago,
                factura=factura,
                pago_cxc=pago_registrado,
                metodo_pago=metodo_pago,
                creado_por=request.user if request.user.is_authenticated else None,
                descripcion=f"Pago CxC factura {factura.numero_factura}. Comprobante: {pago_registrado.numero_comprobante}",
                referencia=pago_registrado.numero_comprobante or "",
            )

            return JsonResponse({
                'success':             True,
                'mensaje':             'Pago registrado correctamente.',
                'comprobante_url':     comprobante_url,
                'numero_comprobante':  pago_registrado.numero_comprobante,
            })

    # =========================================================================
    # CASO 2 — Pago distribuido por cliente
    # =========================================================================
    if not cliente_nombre and not cliente_telefono:
        return JsonResponse(
            {'success': False, 'error': 'Debe indicar cliente para aplicar el pago.'},
            status=400
        )

    if not pago_completo:
        return JsonResponse(
            {
                'success': False,
                'error':   'Seleccione una factura específica o active el pago completo de la deuda.'
            },
            status=400
        )

    # ── Buscar facturas pendientes del cliente ─────────────────────────────
    facturas_no_pagadas = (
        Factura.objects
        .exclude(estado='pagada')
        .prefetch_related('pagos_cxc')
        .order_by('fecha_factura')
    )
    facturas_cliente = []

    for factura in facturas_no_pagadas:
        tel_factura = _telefono_solo_digitos(factura.telefono_cliente)
        nombre_factura = (factura.nombre_cliente or '').strip().lower()

        coincide = False
        if cliente_telefono and tel_factura and cliente_telefono == tel_factura:
            coincide = True
        elif cliente_nombre and nombre_factura and cliente_nombre.lower() == nombre_factura:
            coincide = True

        if coincide:
            facturas_cliente.append(factura)

    if not facturas_cliente:
        return JsonResponse(
            {'success': False,
                'error': 'No se encontraron facturas pendientes para ese cliente.'},
            status=404
        )

    saldo_total_cliente = sum(
        (_saldo_factura_pendiente(f) for f in facturas_cliente),
        Decimal('0.00')
    )
    if monto > saldo_total_cliente:
        return JsonResponse(
            {
                'success': False,
                'error':   f'El monto excede el saldo pendiente total del cliente (RD$ {saldo_total_cliente}).'
            },
            status=400
        )

    # ── Distribuir el pago entre las facturas ─────────────────────────────
    restante = monto
    aplicado_total = Decimal('0.00')
    pagos_creados_ids = []
    pagos_creados = []
    hubo_reimpresion = False

    with transaction.atomic():
        for factura in facturas_cliente:
            if restante <= 0:
                break

            cuenta = _sincronizar_cuenta_por_cobrar(factura)
            saldo_actual = _saldo_factura_pendiente(factura)
            if saldo_actual <= 0:
                continue

            monto_aplicar = saldo_actual if saldo_actual <= restante else restante

            # UUID único por factura dentro del pago distribuido
            # uuid_pago_factura = f"{uuid_pago}-{factura.id}"
            uuid_pago_factura = str(uuid.uuid5(
                uuid.UUID(uuid_pago), str(factura.id)))
            # ── Idempotencia con get_or_create ───────────────────────────
            try:
                pago_obj, creado = PagoCuentaCobrar.objects.get_or_create(
                    uuid_pago=uuid_pago_factura,
                    defaults={
                        'cuenta_por_cobrar': cuenta,
                        'factura':           factura,
                        'monto':             monto_aplicar,
                        'fecha_pago':        fecha_pago,
                        'metodo_pago':       metodo_pago,
                        'referencia':        referencia,
                        'notas':             notas,
                        'registrado_por':    request.user if request.user.is_authenticated else None,
                    }
                )
            except IntegrityError:
                pago_obj = PagoCuentaCobrar.objects.get(
                    uuid_pago=uuid_pago_factura)
                creado = False

            pagos_creados_ids.append(str(pago_obj.id))
            pagos_creados.append(pago_obj)

            if creado:
                aplicado_total += monto_aplicar
                # Registrar ingreso financiero por este pago parcial distribuido
                MovimientoFinanciero.objects.create(
                    tipo="INGRESO",
                    origen="PAGO_CXC",
                    monto=monto_aplicar,
                    fecha_operacion=fecha_pago,
                    factura=factura,
                    pago_cxc=pago_obj,
                    metodo_pago=metodo_pago,
                    creado_por=request.user if request.user.is_authenticated else None,
                    descripcion=f"Pago CxC distribuido factura {factura.numero_factura}. Comprobante: {pago_obj.numero_comprobante}",
                    referencia=pago_obj.numero_comprobante or "",
                )
            else:
                hubo_reimpresion = True

            restante -= monto_aplicar

            _sincronizar_cuenta_por_cobrar(factura)
            if _saldo_factura_pendiente(factura) <= 0:
                factura.estado = 'pagada'
                factura.metodo_pago = metodo_pago
                factura.save(update_fields=['estado', 'metodo_pago'])

                # Sincronizar movimientos financieros
                _sincronizar_movimientos_factura(factura)

    # ── Respuesta del pago distribuido ────────────────────────────────────
    comprobante_url = (
        f"{reverse('cuentaporcobrar_comprobante_pdf')}?pagos={','.join(pagos_creados_ids)}"
        if pagos_creados_ids else ''
    )
    numeros_comprobante = [
        p.numero_comprobante for p in pagos_creados if p.numero_comprobante
    ]

    # Todos los pagos ya existían → reimpresión total
    if aplicado_total <= 0 and hubo_reimpresion and pagos_creados_ids:
        return JsonResponse({
            'success':              True,
            'mensaje':              'Pago ya registrado previamente.',
            'reimpresion':          True,
            'comprobante_url':      comprobante_url,
            'numeros_comprobante':  numeros_comprobante,
        })

    # No se pudo aplicar nada y no había registros previos → error real
    if aplicado_total <= 0:
        return JsonResponse(
            {'success': False, 'error': 'No fue posible aplicar el pago.'},
            status=400
        )

    return JsonResponse({
        'success':               True,
        'mensaje':               f'Pago aplicado correctamente. Monto aplicado: RD$ {aplicado_total}',
        'restante_no_aplicado':  float(restante),
        'comprobante_url':       comprobante_url,
        'numeros_comprobante':   numeros_comprobante,
    })


@login_required
def estado_cuenta_cliente_pdf(request):
    """Genera un PDF A4 de estado de cuenta de un cliente."""
    cliente_id = request.GET.get('cliente_id')
    if not cliente_id:
        return HttpResponse('Debe indicar cliente_id.', status=400)
    try:
        cliente = Cliente.objects.get(pk=cliente_id)
    except Cliente.DoesNotExist:
        return HttpResponse('Cliente no encontrado.', status=404)

    cuentas = CuentaPorCobrar.objects.filter(
        cliente=cliente).select_related('factura').order_by('fecha_emision')
    facturas = [c.factura for c in cuentas if c.factura]
    pagos_qs = PagoCuentaCobrar.objects.filter(
        factura__in=facturas).select_related('factura').order_by('fecha_pago')

    total_facturado = sum((Decimal(str(f.total or 0))
                          for f in facturas), Decimal('0.00'))
    total_devuelto = sum(
        (Decimal(str(getattr(f, 'get_total_devuelto', lambda: Decimal('0.00'))() or 0))
         for f in facturas),
        Decimal('0.00')
    )
    total_pagado = pagos_qs.aggregate(total=Sum('monto'))[
        'total'] or Decimal('0.00')
    saldo_pendiente = total_facturado - total_devuelto - total_pagado
    if saldo_pendiente < Decimal('0.00'):
        saldo_pendiente = Decimal('0.00')

    # ── Estilos ────────────────────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=20*mm,   bottomMargin=20*mm,
    )
    styles = getSampleStyleSheet()
    title_sty = ParagraphStyle(
        'TitleEC',  parent=styles['Heading1'],  fontSize=18, alignment=1, spaceAfter=4)
    small_sty = ParagraphStyle(
        'SmallEC',  parent=styles['Normal'],    fontSize=9)
    bold_sty = ParagraphStyle(
        'BoldEC',   parent=styles['Normal'],    fontName='Helvetica-Bold')
    # Estilo para celdas de tabla (evita overflow, hace word-wrap automático)
    cell_sty = ParagraphStyle(
        'CellEC',   parent=styles['Normal'],    fontSize=9,  leading=11)
    cell_b_sty = ParagraphStyle(
        'CellBEC',  parent=styles['Normal'],    fontSize=9,  leading=11, fontName='Helvetica-Bold')
    cell_i_sty = ParagraphStyle('CellIEC',  parent=styles['Normal'],    fontSize=8,  leading=10,
                                fontName='Helvetica-Oblique', textColor=colors.HexColor('#555555'))
    hdr_sty = ParagraphStyle('HdrEC',    parent=styles['Normal'],    fontSize=9,  leading=11,
                             fontName='Helvetica-Bold',   alignment=1)

    story = []

    # ── Logo + datos empresa ───────────────────────────────────────────────────
    try:
        logo_path = os.path.join(
            settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'img', 'fastfood.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(
                settings.BASE_DIR, 'static', 'img', 'fastfood.png')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=30*mm, height=30*mm)
            logo_table = Table([[logo]], colWidths=[doc.width])
            logo_table.setStyle(TableStyle(
                [('ALIGN', (0, 0), (0, 0), 'CENTER')]))
            story.append(logo_table)
            story.append(Spacer(1, 4))
    except Exception:
        pass

    story.append(Paragraph("402 FASTFOOD",
                 title_sty))
    story.append(Paragraph("RNC: 00000000",
                 small_sty))
    story.append(
        Paragraph("Dirección: Castanuelas, calle 30 de mayo",    small_sty))
    story.append(
        Paragraph("Teléfono: 849-362-1791",                      small_sty))
    story.append(Spacer(1, 8))

    # ── Info cliente ───────────────────────────────────────────────────────────
    story.append(Paragraph("<b>INFORMACIÓN DEL CLIENTE</b>", bold_sty))
    tcli = Table([
        ["Nombre:",    cliente.nombre_completo],
        ["Teléfono:",  cliente.telefono_principal],
        ["Dirección:", cliente.direccion],
        ["Email:",     getattr(cliente, 'email', '-')],
    ], colWidths=[60*mm, doc.width - 60*mm])
    tcli.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ALIGN',         (0, 0), (0, -1),  'RIGHT'),
        ('ALIGN',         (1, 0), (1, -1),  'LEFT'),
    ]))
    story.append(tcli)
    story.append(Spacer(1, 8))

    # ── Tarjetas de totales ────────────────────────────────────────────────────
    val_sty = {
        'total':    ParagraphStyle('v1', parent=bold_sty, textColor=colors.HexColor('#222222'), fontSize=14, alignment=1),
        'pagado':   ParagraphStyle('v2', parent=bold_sty, textColor=colors.HexColor('#1ca64c'), fontSize=14, alignment=1),
        'pendiente': ParagraphStyle('v3', parent=bold_sty, textColor=colors.HexColor('#d32f2f'), fontSize=14, alignment=1),
    }
    tcard = Table([
        [Paragraph('<b>TOTAL FACTURADO</b>', bold_sty),
         Paragraph('<b>TOTAL PAGADO</b>',    bold_sty),
         Paragraph('<b>SALDO PENDIENTE</b>', bold_sty)],
        [Paragraph(f"RD$ {total_facturado:,.2f}",  val_sty['total']),
         Paragraph(f"RD$ {total_pagado:,.2f}",     val_sty['pagado']),
         Paragraph(f"RD$ {saldo_pendiente:,.2f}",  val_sty['pendiente'])],
    ], colWidths=[doc.width/3]*3)
    tcard.setStyle(TableStyle([
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('LINEBELOW',     (0, 1), (2, 1),   1, colors.HexColor('#888888')),
    ]))
    story.append(tcard)
    story.append(Spacer(1, 20))

    # ── Tabla de detalle ───────────────────────────────────────────────────────
    # Anchos de columna  (suman doc.width = 170mm aprox en A4 con márgenes 20mm)
    #   col0 N°Factura  : 38mm   ← más ancho para evitar corte
    #   col1 Fecha      : 22mm
    #   col2 Descripción: resto
    #   col3 Total      : 24mm
    #   col4 Pagado     : 24mm
    #   col5 Saldo      : 24mm
    C0 = 38*mm
    C1 = 22*mm
    C3 = 24*mm
    C4 = 24*mm
    C5 = 24*mm
    C2 = doc.width - C0 - C1 - C3 - C4 - C5   # ~38mm

    col_widths = [C0, C1, C2, C3, C4, C5]

    COLOR_HDR = colors.HexColor('#e3e3e3')
    # fondo verde muy suave para filas de pago
    COLOR_PAGO = colors.HexColor('#f5f9f5')

    # Cabecera
    data = [[
        Paragraph('N° Factura',   hdr_sty),
        Paragraph('Fecha',        hdr_sty),
        Paragraph('Descripción',  hdr_sty),
        Paragraph('Total',        hdr_sty),
        Paragraph('Pagado',       hdr_sty),
        Paragraph('Saldo',        hdr_sty),
    ]]

    row_styles = []
    row_idx = 1

    for cxc in cuentas:
        f = cxc.factura
        pagos_fact = [p for p in pagos_qs if p.factura_id == f.id]
        pagado = sum([p.monto for p in pagos_fact])
        saldo = (f.total or 0) - pagado

        # ── Fila de factura ────────────────────────────────────────────────────
        descripcion = getattr(f, 'descripcion', None) or '-'
        data.append([
            Paragraph(f.numero_factura or '-',             cell_b_sty),
            Paragraph(f.fecha_factura.strftime('%d/%m/%Y'), cell_sty),
            Paragraph(descripcion,                          cell_sty),
            Paragraph(f"RD$ {f.total:,.2f}",               cell_sty),
            Paragraph(f"RD$ {pagado:,.2f}",                cell_sty),
            Paragraph(f"RD$ {saldo:,.2f}",                 cell_sty),
        ])
        row_styles += [
            ('ALIGN',       (3, row_idx), (5, row_idx), 'RIGHT'),
            ('LINEBELOW',   (0, row_idx), (-1, row_idx),
             0.25, colors.HexColor('#bbbbbb')),
        ]
        row_idx += 1

        # ── Filas de pago (una por pago) ───────────────────────────────────────
        for p in pagos_fact:
            metodo_str = p.get_metodo_pago_display()
            comp_str = p.numero_comprobante or '-'
            # col2: método + comprobante en una sola celda, bien legible
            desc_pago = f"\u21b3 {metodo_str}   Comp.: {comp_str}"

            data.append([
                # col0: vacío
                Paragraph('', cell_i_sty),
                Paragraph(p.fecha_pago.strftime('%d/%m/%Y'),
                          cell_i_sty),  # col1: fecha pago
                # col2: descripción pago
                Paragraph(desc_pago,                          cell_i_sty),
                # col3: vacío
                Paragraph('', cell_i_sty),
                # col4: vacío
                Paragraph('', cell_i_sty),
                Paragraph(f"RD$ {p.monto:,.2f}",
                          cell_i_sty),  # col5: monto pago
            ])
            row_styles += [
                ('BACKGROUND', (0, row_idx), (-1, row_idx), COLOR_PAGO),
                ('ALIGN',      (5, row_idx), (5, row_idx),  'RIGHT'),
                ('LINEBELOW',  (0, row_idx), (-1, row_idx),
                 0.15, colors.HexColor('#d0d0d0')),
            ]
            row_idx += 1

    tdet = Table(data, colWidths=col_widths, repeatRows=1)
    tdet.setStyle(TableStyle([
        # Cabecera
        ('BACKGROUND',    (0, 0), (-1, 0), COLOR_HDR),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 9),
        ('ALIGN',         (0, 0), (-1, 0), 'CENTER'),
        ('LINEBELOW',     (0, 0), (-1, 0), 1, colors.HexColor('#888888')),
        # General
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        # Columnas numéricas alineadas a la derecha (filas de factura – base)
        ('ALIGN',         (3, 1), (5, -1), 'RIGHT'),
    ] + row_styles))
    story.append(Paragraph("<b>DETALLE DE FACTURAS</b>", bold_sty))
    story.append(Spacer(1, 6))
    story.append(tdet)
    story.append(Spacer(1, 10))

    # ── Notas ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>NOTAS / OBSERVACIONES</b>", bold_sty))
    # Fecha límite dinámica: 15 días después de hoy
    fecha_limite = (timezone.localdate() +
                    timedelta(days=15)).strftime('%d/%m/%Y')
    story.append(Paragraph(
        f"Por favor realizar los pagos pendientes antes del {fecha_limite}. Gracias por su preferencia.",
        small_sty,
    ))

    # ── Build ──────────────────────────────────────────────────────────────────
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    response = HttpResponse(content_type='application/pdf')
    # Usar nombre del cliente en el nombre del archivo, quitando espacios y caracteres problemáticos
    nombre_archivo = cliente.nombre_completo.strip().replace(' ', '_').replace('ñ', 'n')
    import re
    nombre_archivo = re.sub(r'[^A-Za-z0-9_\-]', '', nombre_archivo)
    response['Content-Disposition'] = (
        f'attachment; filename="estado_cuenta_cliente___{nombre_archivo}.pdf"'
    )
    response.write(pdf)
    return response
