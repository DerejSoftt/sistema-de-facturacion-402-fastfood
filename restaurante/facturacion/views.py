

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
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
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
from django.shortcuts import render
from django.db.models import Sum
from django.contrib.auth.models import User
from .models import Pedido, Factura, Mesa, DeliveryConfig, Producto
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.shortcuts import render, redirect,  get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from .models import Producto, Plato, Pedido, Mesa, DeliveryConfig, HistorialEstadoPedido, DetalleItemPedido, Factura, Devolucion, Cliente 
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, Exists, OuterRef
from django.db.models.functions import Coalesce
from django.db.models import DecimalField
from decimal import Decimal
from django.contrib import messages
from datetime import date
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from django.utils import timezone
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group, Permission
from django.db import transaction
from django.views.decorators.csrf import csrf_protect
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.http import HttpResponse
from django.db.models import F


@csrf_exempt
def index(request):
    """
    Vista principal que maneja tanto el login como el dashboard
    """
    if request.user.is_authenticated:
        return render(request, 'facturacion/index.html')

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
            return redirect('index')
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
            categoria='bebida',
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

        # DEBUG: Mostrar información de bebidas y platos
        print("=" * 50)
        print(f"BEBIDAS ENCONTRADAS: {bebidas.count()}")
        for bebida in bebidas:
            print(
                f"  - {bebida.nombre}: ${bebida.precio_compra} (Stock: {bebida.cantidad})")
        print(f"PLATOS ENCONTRADOS: {platos.count()}")
        for plato in platos:
            print(
                f"  - {plato.nombre}: ${plato.precio} ({plato.get_categoria_display()})")
        print("=" * 50)

        context = {
            'mesas': mesas,
            'delivery_codes': delivery_codes,
            'llevar_codes': llevar_codes,
            'bebidas_json': json.dumps(bebidas_json),  # Solo bebidas
            'platos_json': json.dumps(platos_json),    # Solo platos
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
            'total_bebidas': 0,
            'total_platos': 0,
            'title': 'Realizar Pedido',
        }
        return render(request, 'facturacion/pedidos.html', context)


@csrf_exempt
def crear_pedido(request):
    """Vista para crear un nuevo pedido - funciona sin login"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario con valores por defecto
            tipo_pedido = request.POST.get('tipo_pedido')
            cart_items_json = request.POST.get('cart_items')

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
    """Vista principal de gestión de pedidos - EXCLUYE PEDIDOS PAGADOS"""
    # Obtener parámetros de filtrado
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    tipo_pedido = request.GET.get('tipo', '')
    fecha = request.GET.get('fecha', '')
    sort_by = request.GET.get('sort', '-fecha_pedido')
    page = request.GET.get('page', 1)

    # Construir query base - EXCLUIR PEDIDOS CON FACTURAS PAGADAS
    from django.db.models import Q, Exists, OuterRef

    # Subconsulta para verificar si el pedido tiene facturas pagadas
    facturas_pagadas = Factura.objects.filter(
        pedido_id=OuterRef('pk'),
        estado='pagada'
    )

    # Consulta principal: todos los pedidos que NO tienen facturas pagadas
    # Usamos un nombre diferente para la anotación para evitar conflicto con la propiedad
    pedidos = Pedido.objects.annotate(
        factura_pagada_annotated=Exists(facturas_pagadas)  # Cambiado el nombre
    ).filter(
        factura_pagada_annotated=False  # Solo pedidos SIN facturas pagadas
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
        today = datetime.now().date()
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
    # Solo para pedidos que no tienen facturas pagadas
    pedidos_activos = Pedido.objects.annotate(
        factura_pagada_annotated=Exists(facturas_pagadas)  # Mismo nombre
    ).filter(
        factura_pagada_annotated=False,
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
    today = datetime.now().date()

    # Total de pedidos activos (sin factura pagada)
    total_pedidos_activos = Pedido.objects.annotate(
        factura_pagada_annotated=Exists(facturas_pagadas)  # Mismo nombre
    ).filter(
        factura_pagada_annotated=False
    ).exclude(
        estado='cancelado'
    ).count()

    # Pedidos pendientes (sin factura pagada)
    pedidos_pendientes_count = Pedido.objects.annotate(
        factura_pagada_annotated=Exists(facturas_pagadas)
    ).filter(
        factura_pagada_annotated=False,
        estado__in=['pendiente', 'confirmado']
    ).count()

    # Ingresos hoy (solo de pedidos con facturas pagadas - para mostrar diferencia)
    facturas_hoy_pagadas = Factura.objects.filter(
        fecha_factura__date=today,
        estado='pagada'
    )
    ingresos_hoy = facturas_hoy_pagadas.aggregate(total=Sum('total'))[
        'total'] or 0

    # Pedidos a domicilio activos (sin factura pagada)
    pedidos_domicilio_activos = Pedido.objects.annotate(
        factura_pagada_annotated=Exists(facturas_pagadas)
    ).filter(
        factura_pagada_annotated=False,
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

        print(
            f"  Procesando item: {item_name} (id: {item_id}, cantidad: {cantidad})")

        # Verificar si es un producto de categoría bebida
        # Caso 1: El ID empieza con "PROD-" (formato del frontend)
        if isinstance(item_id, str) and item_id.startswith('PROD-'):
            try:
                prod_id = int(item_id.split('-')[1])
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

        # Caso 2: Buscar por nombre si no tenemos ID
        elif item_name:
            producto = Producto.objects.filter(
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
            'fecha_formateada': pedido.fecha_pedido.strftime('%d/%m/%Y %H:%M'),
            'tiene_factura_pagada': tiene_factura_pagada,
        }

        pedidos_procesados.append(pedido_procesado)

    return pedidos_procesados


@csrf_exempt
def historial_pedidos_pagados(request):
    """Vista para ver el historial de pedidos ya pagados"""
    # Obtener parámetros de filtrado
    search = request.GET.get('search', '')
    tipo_pedido = request.GET.get('tipo', '')
    fecha = request.GET.get('fecha', '')
    page = request.GET.get('page', 1)

    # Subconsulta para pedidos con facturas pagadas
    facturas_pagadas = Factura.objects.filter(
        pedido_id=OuterRef('pk'),
        estado='pagada'
    )

    # Consulta: solo pedidos CON facturas pagadas
    pedidos = Pedido.objects.annotate(
        factura_pagada_annotated=Exists(facturas_pagadas)  # Cambiado el nombre
    ).filter(
        factura_pagada_annotated=True  # Solo pedidos CON facturas pagadas
    ).select_related('mesa').order_by('-fecha_pedido')

    # Aplicar filtros
    if search:
        pedidos = pedidos.filter(
            Q(codigo_pedido__icontains=search) |
            Q(nombre_cliente__icontains=search) |
            Q(telefono_cliente__icontains=search) |
            Q(codigo_delivery__icontains=search)
        )

    if tipo_pedido:
        pedidos = pedidos.filter(tipo_pedido=tipo_pedido)

    if fecha:
        today = datetime.now().date()
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

    # Paginación
    paginator = Paginator(pedidos, 20)
    page_obj = paginator.get_page(page)

    # Procesar pedidos para template
    pedidos_procesados = []
    for pedido in page_obj:
        # Obtener la factura pagada asociada
        factura = Factura.objects.filter(
            pedido=pedido, estado='pagada').first()

        pedido_procesado = {
            'id': pedido.id,
            'codigo_pedido': pedido.codigo_pedido,
            'nombre_cliente': pedido.nombre_cliente or '',
            'tipo_pedido': pedido.tipo_pedido,
            'estado': 'pagado',
            'estado_display': 'Pagado',
            'total': float(pedido.total),
            'fecha_formateada': pedido.fecha_pedido.strftime('%d/%m/%Y %H:%M'),
            'mesa_numero': pedido.mesa.numero_display if pedido.mesa else '',
            'factura_numero': factura.numero_factura if factura else '',
            'factura_fecha': factura.fecha_factura if factura else pedido.fecha_pedido,
            'metodo_pago': factura.metodo_pago if factura else '',
        }
        pedidos_procesados.append(pedido_procesado)

    # Estadísticas
    total_pedidos_pagados = pedidos.count()
    ingresos_totales = Factura.objects.filter(
        estado='pagada').aggregate(total=Sum('total'))['total'] or 0

    context = {
        'user': request.user,
        'page_title': 'Historial de Pedidos Pagados',
        'pedidos': pedidos_procesados,
        'estadisticas': {
            'total_pedidos': total_pedidos_pagados,
            'ingresos_totales': ingresos_totales,
        },
        'filtros': {
            'search': search,
            'tipo_pedido': tipo_pedido,
            'fecha': fecha,
        },
        'paginator': page_obj,
        'mostrando_pagados': True,
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

        # Si el estado cambia a CANCELADO, reponer bebidas del inventario
        if nuevo_estado == 'cancelado' and pedido.estado != 'cancelado':
            print(
                f"🔄 Cancelando pedido {pedido.codigo_pedido} - Reponiendo bebidas...")
            alertas, _ = actualizar_inventario_bebidas(
                items_actuales, operacion='sumar')
            alertas_totales.extend(alertas)

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

        # Recalcular subtotal, total, etc.
        subtotal = sum(item['total'] for item in items_actuales)
        total = subtotal + float(pedido.envio)

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

        if eliminar_vista:
            # Eliminar permanentemente de la base de datos
            codigo_pedido = pedido.codigo_pedido

            # Reponer bebidas del inventario si no tiene factura pagada
            if not tiene_factura_pagada:
                print(
                    f"🔄 Eliminando pedido {codigo_pedido} - Reponiendo bebidas...")
                alertas, _ = actualizar_inventario_bebidas(
                    items, operacion='sumar')
                alertas_totales.extend(alertas)

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
                alertas, _ = actualizar_inventario_bebidas(
                    items, operacion='sumar')
                alertas_totales.extend(alertas)

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

        # Actualizar información del cliente si se proporciona
        if nombre_cliente:
            pedido.nombre_cliente = nombre_cliente
        if telefono_cliente:
            pedido.telefono_cliente = telefono_cliente
        if notas is not None:
            pedido.notas = notas

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
        print("=== DEBUG FACTURACIÓN ===")

        # Obtener IDs de pedidos que ya tienen factura PAGADA
        pedidos_con_factura_pagada_ids = list(
            Factura.objects.filter(estado='pagada').values_list(
                'pedido_id', flat=True)
        )

        print(
            f"Pedidos con factura pagada (IDs): {pedidos_con_factura_pagada_ids}")

        # 🔥 Obtener pedidos que están ocupando mesa y NO tienen factura PAGADA
        pedidos_pendientes = Pedido.objects.filter(
            estado__in=['pendiente', 'confirmado', 'preparacion',
                        'listo', 'entregado', 'completado']
        ).exclude(
            id__in=pedidos_con_factura_pagada_ids  # EXCLUIR pedidos con facturas PAGADAS
        ).select_related('mesa').order_by('-fecha_pedido')

        print(
            f"Pedidos disponibles para facturar (sin factura pagada): {pedidos_pendientes.count()}")

        # Obtener facturas PENDIENTES (las pagadas NO se muestran)
        facturas_pendientes = Factura.objects.filter(
            estado='pendiente').select_related('pedido').all().order_by('-fecha_factura')

        print(f"Facturas pendientes: {facturas_pendientes.count()}")

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
            }

            pedidos_json.append(pedido_dict)

        # Añadir facturas pendientes como registros separados
        for factura in facturas_pendientes:
            try:
                items_data = factura.get_items_detalle()

                factura_dict = {
                    'id': f"factura_{factura.id}",
                    'codigo_pedido': factura.pedido.codigo_pedido if factura.pedido else 'N/A',
                    'tipo_pedido': factura.tipo_pedido,
                    'estado_factura': factura.estado,
                    'estado': 'facturado',
                    'total': float(factura.total),
                    'mesa': {
                        'numero_display': factura.numero_mesa_codigo or '',
                    } if factura.tipo_pedido == 'mesa' else None,
                    'codigo_delivery': factura.numero_mesa_codigo if factura.tipo_pedido in ['delivery', 'llevar'] else '',
                    'nombre_cliente': factura.nombre_cliente or '',
                    'telefono_cliente': factura.telefono_cliente or '',
                    'direccion_entrega': factura.direccion_entrega or '',
                    'items': items_data,
                    'subtotal': float(factura.subtotal),
                    'envio': float(factura.envio),
                    'fecha_pedido': factura.fecha_factura.isoformat() if factura.fecha_factura else None,
                    'es_factura': True,
                    'factura_id': factura.id,
                    'numero_factura': factura.numero_factura,
                    'metodo_pago': factura.metodo_pago,
                }
                pedidos_json.append(factura_dict)
            except Exception as e:
                print(f"Error procesando factura {factura.id}: {e}")

        print(f"Total registros para mostrar: {len(pedidos_json)}")

        # Preparar facturas para estadísticas (todas, incluyendo pagadas)
        facturas_json = []
        todas_facturas = Factura.objects.all().order_by('-fecha_factura')
        for factura in todas_facturas:
            try:
                items_data = factura.get_items_detalle()

                factura_dict = {
                    'id': factura.id,
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
                    'items': items_data,
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

        print("=== CONTEXTO PREPARADO ===")
        print(f"Total registros para mostrar: {len(pedidos_json)}")

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

            # Calcular totales - SIN IVA NI ENVÍO
            subtotal = float(request.POST.get('subtotal', pedido.subtotal))
            envio = 0  # Establecer envío a 0 ya que no lo estamos usando
            iva = 0  # Establecer IVA a 0 ya que no lo estamos usando

            # TOTAL sin IVA ni envío - usar el total del pedido directamente
            total = float(request.POST.get('total', pedido.total))

            # Obtener items del pedido
            items_json = request.POST.get('items', '[]')
            try:
                items = json.loads(items_json)
            except:
                items = pedido.get_items_detalle()

            # Crear la factura con estado PAGADA
            # Obtener hora actual en zona horaria de República Dominicana
            import pytz
            from django.utils import timezone
            tz_rd = pytz.timezone('America/Santo_Domingo')
            now_rd = timezone.now().astimezone(tz_rd)

            factura = Factura(
                pedido=pedido,
                tipo_pedido=pedido.tipo_pedido,
                metodo_pago=request.POST.get('metodo_pago', 'efectivo'),
                estado='pagada',  # Estado PAGADA automáticamente
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

            if pedido.tipo_pedido == 'delivery':
                factura.direccion_entrega = pedido.direccion_entrega

            # Guardar la factura
            factura.save()

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

        except Exception as e:
            print(f"Error al crear factura: {str(e)}")
            import traceback
            traceback.print_exc()
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
            print("ℹ️ No se encontraron bebidas para descontar en este pedido")

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
            'direccion': 'Av. Principal 30 DE MAYO',
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


@login_required
def dashbort(request):
    # Obtener hora local actual
    ahora_local = timezone.localtime()
    hoy_local = ahora_local.date()
    hora_actual = ahora_local.time()

    # DEFINICIÓN DEL "DÍA": De 6:00 AM a 5:59 AM del día siguiente
    if ahora_local.hour >= 6:
        # Si son las 6:00 AM o más tarde, el día actual comenzó hoy a las 6:00 AM
        inicio_dia = timezone.make_aware(
            datetime.combine(hoy_local, datetime(2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(hoy_local + timedelta(days=1),
                             datetime(2000, 1, 1, 5, 59, 59).time())
        )
    else:
        # Si es antes de las 6:00 AM, estamos en el día que comenzó ayer a las 6:00 AM
        inicio_dia = timezone.make_aware(
            datetime.combine(hoy_local - timedelta(days=1),
                             datetime(2000, 1, 1, 6, 0, 0).time())
        )
        fin_dia = timezone.make_aware(
            datetime.combine(hoy_local, datetime(2000, 1, 1, 5, 59, 59).time())
        )

    # Obtener rango visual para mostrar (para información)
    rango_dia_inicio = timezone.localtime(inicio_dia)
    rango_dia_fin = timezone.localtime(fin_dia)

    # 1. VENTA DEL DÍA - Facturas del "día" según nueva definición (6 AM a 5:59 AM)
    facturas_hoy = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia,
        estado='pagada'
    )

    venta_dia = facturas_hoy.aggregate(total_dia=Sum('total'))[
        'total_dia'] or Decimal('0.00')

    # 2. VENTA DEL MES - Esto se mantiene igual (mes calendario)
    primer_dia_mes = hoy_local.replace(day=1)
    inicio_mes = timezone.make_aware(
        datetime.combine(primer_dia_mes, datetime.min.time())
    )

    # El fin del mes es el último día del mes actual a las 23:59:59
    if hoy_local.month == 12:
        ultimo_dia_mes = hoy_local.replace(day=31)
    else:
        ultimo_dia_mes = hoy_local.replace(
            month=hoy_local.month + 1, day=1) - timedelta(days=1)

    fin_mes = timezone.make_aware(
        datetime.combine(ultimo_dia_mes, datetime.max.time())
    )

    facturas_mes = Factura.objects.filter(
        fecha_factura__gte=inicio_mes,
        fecha_factura__lte=fin_mes,
        estado='pagada'
    )

    venta_mes = facturas_mes.aggregate(total_mes=Sum('total'))[
        'total_mes'] or Decimal('0.00')

    # 3. PEDIDOS HOY - Usar misma definición de "día" (6 AM a 5:59 AM)
    total_pedidos = Pedido.objects.filter(
        fecha_pedido__gte=inicio_dia,
        fecha_pedido__lte=fin_dia
    ).count()

    # 4. GASTOS TOTALES - Mantener igual
    gastos_totales = venta_mes * Decimal('0.60')

    # 5. GANANCIAS NETAS
    ganancias_netas = venta_mes - gastos_totales

    # 6. NUEVOS CLIENTES - Usar definición de "día" (6 AM a 5:59 AM)
    nuevos_clientes = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia
    ).exclude(nombre_cliente='').values('nombre_cliente').distinct().count()

    # 7. ACTIVIDADES RECIENTES - Mantener igual (últimas 5 facturas sin filtrar por día)
    actividades_recientes = Factura.objects.filter(
        estado='pagada'
    ).order_by('-fecha_factura')[:5]

    # 8. PRODUCTOS MÁS VENDIDOS - Usar facturas del "día" (6 AM a 5:59 AM)
    productos_vendidos = {}

    for factura in facturas_hoy:  # Ahora usa facturas_hoy (definición del día)
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
                    else:
                        productos_vendidos[nombre] = {
                            'nombre': nombre,
                            'cantidad': cantidad,
                            'ingresos': Decimal(str(cantidad * precio))
                        }
        except Exception as e:
            print(
                f"Error procesando items de factura {factura.numero_factura}: {e}")
            continue

    productos_top = sorted(
        productos_vendidos.values(),
        key=lambda x: x['cantidad'],
        reverse=True
    )[:5]

    # 9. DATOS PARA GRÁFICO DE VENTAS - Últimos 7 "días" (cada uno de 6 AM a 5:59 AM)
    ultimos_7_dias = []
    ventas_7_dias = []

    for i in range(6, -1, -1):
        # Para cada día en el gráfico, aplicar la misma lógica de 6 AM a 5:59 AM
        dia_referencia = hoy_local - timedelta(days=i)

        # Determinar rango para este día
        if i == 0:
            # Para hoy, usar los rangos ya calculados
            dia_inicio = inicio_dia
            dia_fin = fin_dia
            dia_str = "Hoy"
        else:
            # Para días anteriores
            dia_anterior = dia_referencia
            # Crear rango de 6 AM a 5:59 AM del día siguiente
            dia_inicio = timezone.make_aware(
                datetime.combine(dia_anterior, datetime(
                    2000, 1, 1, 6, 0, 0).time())
            )
            dia_fin = timezone.make_aware(
                datetime.combine(dia_anterior + timedelta(days=1),
                                 datetime(2000, 1, 1, 5, 59, 59).time())
            )
            dia_str = dia_anterior.strftime('%a')

        venta_dia_grafico = Factura.objects.filter(
            fecha_factura__gte=dia_inicio,
            fecha_factura__lte=dia_fin,
            estado='pagada'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

        ultimos_7_dias.append(dia_str)
        ventas_7_dias.append(float(venta_dia_grafico))

    # 10. DATOS PARA GRÁFICO DE CATEGORÍAS - Mantener igual
    categorias_data = []
    ventas_categorias_data = []

    try:
        # Primero intentar obtener categorías de productos vendidos hoy
        categorias_dict = {}
        
        for factura in facturas_hoy:
            items = factura.get_items_detalle()
            if items and isinstance(items, list):
                for item in items:
                    categoria = item.get('categoria', 'otro').lower()
                    cantidad = float(item.get('quantity', 0))
                    precio = float(item.get('price', 0))
                    
                    if categoria in categorias_dict:
                        categorias_dict[categoria] += cantidad * precio
                    else:
                        categorias_dict[categoria] = cantidad * precio
        
        # Si no hay categorías hoy, intentar del mes
        if not categorias_dict:
            for factura in facturas_mes:
                items = factura.get_items_detalle()
                if items and isinstance(items, list):
                    for item in items:
                        categoria = item.get('categoria', 'otro').lower()
                        cantidad = float(item.get('quantity', 0))
                        precio = float(item.get('price', 0))
                        
                        if categoria in categorias_dict:
                            categorias_dict[categoria] += cantidad * precio
                        else:
                            categorias_dict[categoria] = cantidad * precio
        
        # Si aún no hay datos, usar categorías por defecto
        if categorias_dict:
            categorias_data = list(categorias_dict.keys())
            ventas_categorias_data = list(categorias_dict.values())
        else:
            # Datos de ejemplo solo si no hay datos reales
            categorias_data = ['Entradas', 'Platos Fuertes', 'Postres', 'Bebidas', 'Especiales']
            ventas_categorias_data = [15, 40, 25, 12, 8]
    except Exception as e:
        print(f"Error en categorías: {e}")
        categorias_data = ['Entradas', 'Platos Fuertes', 'Postres', 'Bebidas', 'Especiales']
        ventas_categorias_data = [15, 40, 25, 12, 8]

    # 11. DATOS PARA GRÁFICOS DE MES Y AÑO (DATOS REALES)
    # Etiquetas para gráfico mensual (últimas 4 semanas)
    labels_mensuales = []
    proyeccion_mensual = []
    
    # Calcular ventas de las últimas 4 semanas
    for semana in range(4):
        fecha_inicio_semana = hoy_local - timedelta(weeks=semana, days=hoy_local.weekday())
        fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)
        
        # Ajustar horas para el período
        inicio_semana = timezone.make_aware(
            datetime.combine(fecha_inicio_semana, datetime(2000, 1, 1, 6, 0, 0).time())
        )
        fin_semana = timezone.make_aware(
            datetime.combine(fecha_fin_semana + timedelta(days=1),
                             datetime(2000, 1, 1, 5, 59, 59).time())
        )
        
        # Obtener ventas de esta semana
        venta_semana = Factura.objects.filter(
            fecha_factura__gte=inicio_semana,
            fecha_factura__lte=fin_semana,
            estado='pagada'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        
        labels_mensuales.append(f"Sem {semana+1}")
        proyeccion_mensual.append(float(venta_semana))
    
    # Invertir para que la última semana sea la primera
    labels_mensuales = labels_mensuales[::-1]
    proyeccion_mensual = proyeccion_mensual[::-1]
    
    # Etiquetas para gráfico anual (últimos 12 meses)
    labels_anuales = []
    proyeccion_anual = []
    
    # Calcular ventas de los últimos 12 meses
    for i in range(11, -1, -1):
        # Calcular fecha del mes
        fecha_mes = hoy_local.replace(day=1)
        for _ in range(i):
            # Retroceder un mes
            fecha_mes = (fecha_mes.replace(day=1) - timedelta(days=1)).replace(day=1)
        
        # Calcular inicio y fin del mes
        if fecha_mes.month == 12:
            ultimo_dia = fecha_mes.replace(day=31)
        else:
            ultimo_dia = fecha_mes.replace(month=fecha_mes.month + 1, day=1) - timedelta(days=1)
        
        inicio_mes_grafico = timezone.make_aware(
            datetime.combine(fecha_mes, datetime.min.time())
        )
        fin_mes_grafico = timezone.make_aware(
            datetime.combine(ultimo_dia, datetime.max.time())
        )
        
        # Obtener ventas de este mes
        venta_mes_grafico = Factura.objects.filter(
            fecha_factura__gte=inicio_mes_grafico,
            fecha_factura__lte=fin_mes_grafico,
            estado='pagada'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        
        # Nombre del mes en español
        meses_esp = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        
        labels_anuales.append(meses_esp[fecha_mes.month - 1])
        proyeccion_anual.append(float(venta_mes_grafico))
    
    # Invertir para que enero sea primero
    labels_anuales = labels_anuales[::-1]
    proyeccion_anual = proyeccion_anual[::-1]

    # Datos para depuración y verificación DIRECTA en el dashboard
    facturas_hoy_todas = Factura.objects.filter(
        fecha_factura__gte=inicio_dia,
        fecha_factura__lte=fin_dia
    ).order_by('-fecha_factura')

    todas_facturas = Factura.objects.filter(
        estado='pagada'
    ).order_by('-fecha_factura')[:10]

    # OBTENER DATOS DE VERIFICACIÓN DIRECTA
    # Total de facturas en la base de datos
    total_facturas_db = Factura.objects.count()
    total_facturas_pagadas_db = Factura.objects.filter(estado='pagada').count()
    
    # Rango de fechas de facturas
    primera_factura = Factura.objects.order_by('fecha_factura').first()
    ultima_factura = Factura.objects.order_by('-fecha_factura').first()
    
    # Facturas del último mes completo (para verificar que hay datos)
    mes_pasado = hoy_local.replace(day=1) - timedelta(days=1)
    inicio_mes_pasado = mes_pasado.replace(day=1)
    fin_mes_pasado = mes_pasado
    
    inicio_mes_pasado_time = timezone.make_aware(
        datetime.combine(inicio_mes_pasado, datetime.min.time())
    )
    fin_mes_pasado_time = timezone.make_aware(
        datetime.combine(fin_mes_pasado, datetime.max.time())
    )
    
    facturas_mes_pasado = Factura.objects.filter(
        fecha_factura__gte=inicio_mes_pasado_time,
        fecha_factura__lte=fin_mes_pasado_time,
        estado='pagada'
    ).count()
    
    venta_mes_pasado = Factura.objects.filter(
        fecha_factura__gte=inicio_mes_pasado_time,
        fecha_factura__lte=fin_mes_pasado_time,
        estado='pagada'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    context = {
        'venta_dia': venta_dia,
        'venta_mes': venta_mes,
        'total_pedidos': total_pedidos,
        'gastos_totales': gastos_totales,
        'ganancias_netas': ganancias_netas,
        'nuevos_clientes': nuevos_clientes,
        'actividades': actividades_recientes,
        'productos_top': productos_top,
        'dias_grafico': json.dumps(ultimos_7_dias),
        'ventas_grafico': json.dumps(ventas_7_dias),
        'categorias_grafico': json.dumps(categorias_data),
        'ventas_categorias_grafico': json.dumps(ventas_categorias_data),
        'labels_mensuales_json': json.dumps(labels_mensuales),
        'proyeccion_mensual_json': json.dumps(proyeccion_mensual),
        'labels_anuales_json': json.dumps(labels_anuales),
        'proyeccion_anual_json': json.dumps(proyeccion_anual),
        'fecha_actual': ahora_local.strftime('%A, %d de %B de %Y'),
        'hora_actual': ahora_local.strftime('%I:%M:%S'),
        'hoy': hoy_local,
        'now_utc': timezone.now(),
        'total_facturas_hoy': facturas_hoy_todas.count(),
        'total_facturas_mes': facturas_mes.count(),
        'facturas_hoy_todas': facturas_hoy_todas,
        'todas_facturas': todas_facturas,
        
        # Información adicional para depuración
        'rango_dia_inicio': rango_dia_inicio.strftime('%d/%m/%Y %H:%M'),
        'rango_dia_fin': rango_dia_fin.strftime('%d/%m/%Y %H:%M'),
        'definicion_dia': '6:00 AM - 5:59 AM (día siguiente)',
        
        # DATOS DE VERIFICACIÓN PARA MOSTRAR DIRECTAMENTE EN EL DASHBOARD
        'total_facturas_db': total_facturas_db,
        'total_facturas_pagadas_db': total_facturas_pagadas_db,
        'primera_factura_fecha': primera_factura.fecha_factura.strftime('%d/%m/%Y') if primera_factura else 'No hay facturas',
        'ultima_factura_fecha': ultima_factura.fecha_factura.strftime('%d/%m/%Y') if ultima_factura else 'No hay facturas',
        'facturas_mes_pasado': facturas_mes_pasado,
        'venta_mes_pasado': venta_mes_pasado,
        'mes_pasado_nombre': inicio_mes_pasado.strftime('%B %Y'),
        
        # DATOS CRUDOS PARA DIAGNÓSTICO
        'datos_semana_raw': list(zip(ultimos_7_dias, ventas_7_dias)),
        'datos_categorias_raw': list(zip(categorias_data, ventas_categorias_data)),
        'datos_mensual_raw': list(zip(labels_mensuales, proyeccion_mensual)),
        'datos_anual_raw': list(zip(labels_anuales, proyeccion_anual)),
    }

    return render(request, 'facturacion/dashbort.html', context)


@login_required
def dashboard_stats(request):
    """Vista API para obtener estadísticas en formato JSON"""
    try:
        # Obtener hora local actual
        ahora_local = timezone.localtime()
        hoy_local = ahora_local.date()

        # DEFINICIÓN DEL "DÍA": De 6:00 AM a 5:59 AM del día siguiente
        if ahora_local.hour >= 6:
            inicio_dia = timezone.make_aware(
                datetime.combine(hoy_local, datetime(
                    2000, 1, 1, 6, 0, 0).time())
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
                datetime.combine(hoy_local, datetime(
                    2000, 1, 1, 5, 59, 59).time())
            )

        # 1. VENTA DEL DÍA
        facturas_hoy = Factura.objects.filter(
            fecha_factura__gte=inicio_dia,
            fecha_factura__lte=fin_dia,
            estado='pagada'
        )

        venta_dia = facturas_hoy.aggregate(total_dia=Sum('total'))[
            'total_dia'] or Decimal('0.00')

        # 2. VENTA DEL MES
        primer_dia_mes = hoy_local.replace(day=1)
        inicio_mes = timezone.make_aware(
            datetime.combine(primer_dia_mes, datetime.min.time()))

        if hoy_local.month == 12:
            ultimo_dia_mes = hoy_local.replace(day=31)
        else:
            ultimo_dia_mes = hoy_local.replace(
                month=hoy_local.month + 1, day=1) - timedelta(days=1)

        fin_mes = timezone.make_aware(datetime.combine(
            ultimo_dia_mes, datetime.max.time()))

        facturas_mes = Factura.objects.filter(
            fecha_factura__gte=inicio_mes,
            fecha_factura__lte=fin_mes,
            estado='pagada'
        )

        venta_mes = facturas_mes.aggregate(total_mes=Sum('total'))[
            'total_mes'] or Decimal('0.00')

        # 3. PEDIDOS HOY
        total_pedidos = Pedido.objects.filter(
            fecha_pedido__gte=inicio_dia,
            fecha_pedido__lte=fin_dia
        ).count()

        # 4. GASTOS TOTALES
        gastos_totales = venta_mes * Decimal('0.60')

        # 5. GANANCIAS NETAS
        ganancias_netas = venta_mes - gastos_totales

        # 6. NUEVOS CLIENTES
        nuevos_clientes = Factura.objects.filter(
            fecha_factura__gte=inicio_dia,
            fecha_factura__lte=fin_dia
        ).exclude(nombre_cliente='').values('nombre_cliente').distinct().count()

        # Retornar datos como JSON
        return JsonResponse({
            'venta_dia': float(venta_dia),
            'venta_mes': float(venta_mes),
            'total_pedidos': total_pedidos,
            'gastos_totales': float(gastos_totales),
            'ganancias_netas': float(ganancias_netas),
            'nuevos_clientes': nuevos_clientes,
            'fecha_actual': ahora_local.strftime('%A, %d de %B de %Y'),
            'hora_actual': ahora_local.strftime('%H:%M:%S'),
            'total_facturas_hoy': facturas_hoy.count(),
            'total_facturas_mes': facturas_mes.count(),
            'status': 'success'
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })


@login_required
def generar_pdf_ticket_dia(request):
    """Generar PDF del ticket de venta del día para impresora 80mm"""
    # Obtener hora local actual - forzar zona horaria de República Dominicana
    import pytz
    tz_rd = pytz.timezone('America/Santo_Domingo')
    ahora_local = timezone.now().astimezone(tz_rd)
    hoy_local = ahora_local.date()

    # DEFINICIÓN DEL "DÍA": De 6:00 AM a 5:59 AM del día siguiente
    if ahora_local.hour >= 6:
        # Si son las 6:00 AM o más tarde, el día actual comenzó hoy a las 6:00 AM
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
        # Si es antes de las 6:00 AM, estamos en el día que comenzó ayer a las 6:00 AM
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
        estado='pagada'
    ).order_by('fecha_factura')

    venta_dia = facturas_hoy.aggregate(total_dia=Sum('total'))[
        'total_dia'] or Decimal('0.00')

    # Crear un buffer para el PDF
    buffer = io.BytesIO()

    # Configurar el tamaño de la página para impresora térmica 80mm
    ancho_pagina = 80 * mm  # 226.77 puntos
    alto_pagina = 297 * mm  # Alto estándar para ticket continuo

    # Crear el documento PDF con tamaño personalizado
    c = canvas.Canvas(buffer, pagesize=(ancho_pagina, alto_pagina))

    # Configurar fuentes y estilos para impresora térmica
    c.setFont("Helvetica", 8)

    # Coordenadas iniciales (de arriba hacia abajo)
    y = alto_pagina - 10 * mm  # Comenzar 10mm desde el borde superior

    # 1. ENCABEZADO DEL RESTAURANTE CON LOGO
    # Intentar cargar el logo
    try:
        logo_path = os.path.join(
            settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'img', 'fastfood.png')
        if not os.path.exists(logo_path):
            # Intentar ruta alternativa
            logo_path = os.path.join(
                settings.BASE_DIR, 'static', 'img', 'fastfood.png')

        if os.path.exists(logo_path):
            # Dibujar logo centrado (pequeño: 15mm x 15mm)
            logo_size = 15 * mm
            logo_x = (ancho_pagina - logo_size) / 2
            c.drawImage(logo_path, logo_x, y - logo_size, width=logo_size,
                        height=logo_size, preserveAspectRatio=True, mask='auto')
            y -= (logo_size + 3 * mm)
    except Exception as e:
        # Si falla la carga del logo, continuar sin él
        pass

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho_pagina / 2, y, "404 FASTFOOD")
    y -= 6 * mm

    c.setFont("Helvetica", 9)
    c.drawCentredString(ancho_pagina / 2, y, "REPORTE DE CUADRE DE VENTAS")
    y -= 5 * mm

    # Línea separadora
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 4 * mm

    # 2. PERÍODO DE REPORTE (con nueva definición)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(ancho_pagina / 2, y, "PERÍODO DE REPORTE")
    y -= 4 * mm

    c.setFont("Helvetica", 8)
    c.drawCentredString(ancho_pagina / 2, y, periodo_corto)
    y -= 4 * mm

    c.drawCentredString(ancho_pagina / 2, y, "(De 6:00 AM a 5:59 AM)")
    y -= 6 * mm

    # 3. FECHA Y HORA DE GENERACIÓN
    c.setFont("Helvetica", 8)
    c.drawString(5 * mm, y, f"Generado:")
    c.drawRightString(ancho_pagina - 5 * mm, y,
                      ahora_local.strftime('%d/%m/%Y %I:%M'))
    y -= 4 * mm

    # Línea separadora
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 4 * mm

    # 4. RESUMEN DE VENTAS
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(ancho_pagina / 2, y, "RESUMEN DE VENTAS")
    y -= 4 * mm

    c.setFont("Helvetica", 8)
    c.drawString(5 * mm, y, f"Total de Facturas:")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(ancho_pagina - 5 * mm, y, f"{facturas_hoy.count()}")
    y -= 4 * mm

    # Línea separadora punteada
    c.setDash(1, 2)
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    c.setDash()
    y -= 6 * mm

    # 5. DETALLE DE FACTURAS (si hay)
    if facturas_hoy.exists():
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(ancho_pagina / 2, y, "DETALLE DE FACTURAS")
        y -= 5 * mm

        # Encabezado de tabla
        c.setFont("Helvetica-Bold", 8)
        c.drawString(5 * mm, y, "FACTURA")
        c.drawString(30 * mm, y, "HORA")
        c.drawString(42 * mm, y, "CLIENTE")
        c.drawRightString(ancho_pagina - 5 * mm, y, "TOTAL")
        y -= 4 * mm

        c.setFont("Helvetica", 7)
        for factura in facturas_hoy:
            # Verificar si hay espacio en la página
            if y < 25 * mm:  # Si queda poco espacio
                c.showPage()
                c.setFont("Helvetica", 8)
                y = alto_pagina - 10 * mm
                # Reimprimir encabezado de tabla
                c.setFont("Helvetica-Bold", 8)
                c.drawString(5 * mm, y, "FACTURA")
                c.drawString(30 * mm, y, "HORA")
                c.drawString(42 * mm, y, "CLIENTE")
                c.drawRightString(ancho_pagina - 5 * mm, y, "TOTAL")
                y -= 4 * mm
                c.setFont("Helvetica", 7)

            # Número de factura (mostrar solo los últimos 8 dígitos)
            num_factura = factura.numero_factura
            if len(num_factura) > 8:
                num_factura = "..." + num_factura[-8:]
            c.drawString(5 * mm, y, f"#{num_factura}")

            # Hora
            hora_factura = factura.fecha_factura.astimezone(tz_rd)
            c.drawString(30 * mm, y, hora_factura.strftime('%I:%M'))

            # Cliente (truncar si es muy largo)
            cliente = factura.nombre_cliente or "CLIENTE"
            if len(cliente) > 10:
                cliente = cliente[:10] + "."
            c.drawString(42 * mm, y, cliente)

            # Total de la factura
            c.drawRightString(ancho_pagina - 5 * mm, y,
                              f"${factura.total:,.2f}")
            y -= 3.5 * mm

        # Línea separadora después de la lista
        c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
        y -= 8 * mm

    # 6. TOTAL DEL DÍA
    c.setFont("Helvetica-Bold", 11)
    c.drawString(5 * mm, y, "TOTAL DEL DÍA:")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(ancho_pagina - 5 * mm, y, f"${venta_dia:,.2f}")
    y -= 8 * mm

    # Línea doble para énfasis
    c.setLineWidth(0.8)
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    y -= 1.5 * mm
    c.line(5 * mm, y, ancho_pagina - 5 * mm, y)
    c.setLineWidth(1)
    y -= 6 * mm

    # 7. ESTADÍSTICAS ADICIONALES
    c.setFont("Helvetica", 8)
    c.drawCentredString(ancho_pagina / 2, y, "ESTADÍSTICAS")
    y -= 4 * mm

    # Promedio por factura
    promedio = venta_dia / \
        facturas_hoy.count() if facturas_hoy.count() > 0 else Decimal('0.00')
    c.drawString(5 * mm, y, f"Promedio por factura:")
    c.drawRightString(ancho_pagina - 5 * mm, y, f"${promedio:,.2f}")
    y -= 3.5 * mm

    # Factura más alta
    if facturas_hoy.exists():
        max_factura = facturas_hoy.aggregate(max_total=Max('total'))[
            'max_total'] or Decimal('0.00')
        c.drawString(5 * mm, y, f"Factura más alta:")
        c.drawRightString(ancho_pagina - 5 * mm, y, f"${max_factura:,.2f}")
        y -= 3.5 * mm

    # Factura más baja
    if facturas_hoy.exists():
        min_factura = facturas_hoy.aggregate(min_total=Min('total'))[
            'min_total'] or Decimal('0.00')
        c.drawString(5 * mm, y, f"Factura más baja:")
        c.drawRightString(ancho_pagina - 5 * mm, y, f"${min_factura:,.2f}")
        y -= 3.5 * mm

    y -= 4 * mm

    # 8. PIE DE PÁGINA
    c.setFont("Helvetica", 8)
    c.drawCentredString(ancho_pagina / 2, y, "*** GRACIAS POR SU VISITA ***")
    y -= 3 * mm

    c.setFont("Helvetica", 7)
    c.drawCentredString(ancho_pagina / 2, y,
                        "Sistema de Gestión de Restaurantes")
    y -= 3 * mm

    c.drawCentredString(ancho_pagina / 2, y, "www.mirestaurante.com")
    y -= 5 * mm

    # 9. CÓDIGO DE BARRAS (simulado para referencia)
    c.setFont("Helvetica", 6)
    c.drawCentredString(ancho_pagina / 2, y, "| | | | | | | | | | | | | | | |")
    y -= 2 * mm
    c.drawCentredString(ancho_pagina / 2, y,
                        f"REF: {ahora_local.strftime('%Y%m%d%H%M')}")
    y -= 3 * mm

    # 10. NOTA IMPORTANTE
    c.setFont("Helvetica", 6)
    nota_texto = "Nota: Este reporte incluye ventas desde las 6:00 AM hasta las 5:59 AM del día siguiente."
    # Dividir texto largo en líneas
    max_chars_per_line = 45
    lines = []
    for i in range(0, len(nota_texto), max_chars_per_line):
        lines.append(nota_texto[i:i+max_chars_per_line])

    for line in lines:
        c.drawCentredString(ancho_pagina / 2, y, line)
        y -= 2.5 * mm

    # Guardar el PDF
    c.save()

    # Obtener el valor del buffer y devolver como respuesta HTTP
    buffer.seek(0)

    # Configurar respuesta HTTP
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"reporte_ventas_{ahora_local.strftime('%Y%m%d_%H%M')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


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
    venta_dia = facturas_hoy.aggregate(total_dia=Sum('total'))[
        'total_dia'] or Decimal('0.00')

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


# Para PDF

# Importar modelos


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
        estado='pagada'
    )

    venta_dia = facturas_hoy.aggregate(total_dia=Sum('total'))[
        'total_dia'] or Decimal('0.00')

    print(
        f"🔍 DEBUG: Encontradas {facturas_hoy.count()} facturas en el período")
    print(f"🔍 DEBUG: Venta total del día: ${venta_dia}")

    # Obtener productos vendidos en el día
    productos_vendidos = {}

    for factura in facturas_hoy:
        try:
            items = factura.get_items_detalle()
            print(
                f"🔍 DEBUG: Factura {factura.numero_factura} tiene {len(items)} items")

            if items and isinstance(items, list):
                for item in items:
                    # DEBUG: Imprimir todas las claves del item
                    print(f"  📦 Item keys: {item.keys()}")

                    # Obtener nombre del producto - probar todas las posibles claves
                    nombre = item.get('nombre', '').strip()
                    if not nombre:
                        nombre = item.get('name', '').strip()
                    if not nombre:
                        nombre = item.get('producto', '').strip()
                    if not nombre:
                        nombre = item.get('product', '').strip()

                    print(f"  🔍 Nombre encontrado: '{nombre}'")

                    if not nombre or nombre.lower() == 'desconocido':
                        print(f"  ⚠️  Nombre vacío o 'Desconocido', saltando...")
                        continue

                    # Obtener cantidad - probar todas las posibles claves
                    cantidad = 0
                    cantidad_keys = ['cantidad', 'quantity', 'qty']
                    for key in cantidad_keys:
                        if key in item:
                            try:
                                cantidad = float(item[key])
                                print(f"  🔍 Cantidad de '{key}': {cantidad}")
                                break
                            except (ValueError, TypeError):
                                pass

                    if cantidad <= 0:
                        print(
                            f"  ⚠️  Cantidad inválida ({cantidad}), saltando...")
                        continue

                    # Obtener precio - probar todas las posibles claves
                    precio = 0
                    precio_keys = ['precio', 'price', 'unit_price']
                    for key in precio_keys:
                        if key in item:
                            try:
                                precio = float(item[key])
                                print(f"  🔍 Precio de '{key}': {precio}")
                                break
                            except (ValueError, TypeError):
                                pass

                    # Calcular ingresos
                    ingresos = Decimal(str(cantidad * precio))

                    print(f"  ✅ Procesado: {nombre} x{cantidad} = ${ingresos}")

                    if nombre in productos_vendidos:
                        productos_vendidos[nombre]['cantidad'] += cantidad
                        productos_vendidos[nombre]['ingresos'] += ingresos
                        productos_vendidos[nombre]['precio_unitario'] = productos_vendidos[nombre]['ingresos'] / Decimal(
                            str(productos_vendidos[nombre]['cantidad']))
                    else:
                        productos_vendidos[nombre] = {
                            'nombre': nombre,
                            'cantidad': cantidad,
                            'precio_unitario': Decimal(str(precio)),
                            'ingresos': ingresos
                        }
            else:
                print(
                    f"⚠️  Factura {factura.numero_factura} no tiene items o no es una lista")

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
# views.py - Actualiza la función anulacionydevolucion


# ============================================================
# FUNCIONES DE GESTIÓN DE STOCK - SOLO BEBIDAS
# ============================================================

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
                # Depuración directa
                print(f"\n{'='*60}")
                print(f"DEBUG - Factura: {factura.numero_factura}")
                print(f"Tipo de items: {type(factura.items)}")
                if isinstance(factura.items, str):
                    print(f"Es una cadena. Longitud: {len(factura.items)}")
                    print(f"Primeros 300 caracteres: {factura.items[:300]}")
                elif isinstance(factura.items, dict):
                    print(
                        f"Es un diccionario. Claves: {list(factura.items.keys())}")
                elif isinstance(factura.items, list):
                    print(f"Es una lista. Longitud: {len(factura.items)}")
                print(f"{'='*60}")
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
                # Depuración directa
                print(f"\n{'='*60}")
                print(f"DEBUG - Factura: {factura.numero_factura}")
                print(f"Tipo de items: {type(factura.items)}")
                if isinstance(factura.items, str):
                    print(f"Es una cadena. Longitud: {len(factura.items)}")
                    print(f"Primeros 300 caracteres: {factura.items[:300]}")
                elif isinstance(factura.items, dict):
                    print(
                        f"Es un diccionario. Claves: {list(factura.items.keys())}")
                elif isinstance(factura.items, list):
                    print(f"Es una lista. Longitud: {len(factura.items)}")
                print(f"{'='*60}")
            else:
                messages.error(
                    request, f'Factura {numero_factura} no encontrada')

        if factura:
            print(f"\n📄 FACTURA ENCONTRADA: {factura.numero_factura}")
            print(f"📦 Campo 'items' tipo: {type(factura.items)}")

            # DEPURACIÓN DETALLADA
            if isinstance(factura.items, str):
                print(f"🔍 Contenido de items (string):")
                print(factura.items[:500])
            elif isinstance(factura.items, list):
                print(
                    f"🔍 Contenido de items (lista con {len(factura.items)} elementos):")
                for i, item in enumerate(factura.items[:3]):  # Muestra solo 3
                    print(f"   Item {i}: {item}")

            # Obtener items detallados
            items = factura.get_items_detalle()
            print(f"\n✅ Items normalizados: {len(items)}")

            # Mostrar primeros 5 items para depuración
            for i, item in enumerate(items[:5]):
                print(f"  {i+1}. {item.get('nombre', 'Sin nombre')} - Cant: {item.get('cantidad', 0)} - Precio: ${item.get('precio', 0)} - Cat: '{item.get('categoria', '')}'")

            items_json = json.dumps(items, cls=DjangoJSONEncoder)

            # Obtener productos disponibles para devolución
            productos_disponibles = factura.get_productos_disponibles_devolucion()
            productos_disponibles_json = json.dumps(
                productos_disponibles, cls=DjangoJSONEncoder)
            print(
                f"✅ Productos disponibles para devolver: {len(productos_disponibles)}")

            # Obtener todas las devoluciones para el historial
            devoluciones = factura.devoluciones.all()
            todos_productos_devueltos = []

            for devolucion in devoluciones:
                if devolucion.productos_devueltos:
                    todos_productos_devueltos.extend(
                        devolucion.productos_devueltos)

            productos_devueltos_json = json.dumps(
                todos_productos_devueltos, cls=DjangoJSONEncoder)
            print(
                f"✅ Productos ya devueltos: {len(todos_productos_devueltos)}")

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

# ============================================================
# NORMALIZACIÓN DE ITEMS
# ============================================================


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
# ============================================================
# VISTA PRINCIPAL
# ============================================================


# ============================================================
# DEVOLUCIÓN TOTAL
# ============================================================

@login_required
def procesar_devolucion_total(request):
    """Procesar devolución total de una factura"""
    if request.method == 'POST':
        numero_factura = request.POST.get('numero_factura')

        if not numero_factura:
            messages.error(request, 'Número de factura requerido')
            return redirect('anulacionydevolucion')

        try:
            factura = get_object_or_404(Factura, numero_factura=numero_factura)

            if factura.estado != 'pagada':
                messages.error(
                    request,
                    f'La factura debe estar pagada para procesar devolución. Estado actual: {factura.get_estado_display()}'
                )
                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

            with transaction.atomic():
                # Usar el método del modelo para obtener items
                items = factura.get_items_detalle()
                productos_devueltos = []
                monto_total_devuelto = 0
                bebidas_repuestas = 0

                print(f"\n🔄 PROCESANDO DEVOLUCIÓN TOTAL")

                for item in items:
                    codigo = item.get('codigo', '')
                    nombre = item.get('nombre', '')
                    cantidad = item.get('cantidad', 0)
                    precio = item.get('precio', 0)
                    categoria = item.get('categoria', '')

                    print(f"\n📦 Procesando item: {nombre}")
                    print(f"   Código: '{codigo}'")
                    print(f"   Categoría: '{categoria}'")
                    print(f"   Cantidad: {cantidad}")

                    # REPONER stock para bebidas
                    if categoria.lower() == 'bebida':
                        # Usar código si está disponible, sino usar nombre
                        identificador = codigo if codigo and codigo.strip() else nombre
                        print(
                            f"   🍺 ES BEBIDA - Reponiendo stock con identificador: '{identificador}'")

                        if reponer_stock_producto(identificador, cantidad):
                            bebidas_repuestas += 1
                            print(f"   ✅ Stock repuesto exitosamente")
                        else:
                            print(f"   ⚠️  No se pudo reponer stock")
                    else:
                        print(f"   ℹ️  No es bebida - no se repone stock")

                    monto_total_devuelto += precio * cantidad
                    productos_devueltos.append({
                        'producto_id': item.get('producto_id'),
                        'codigo': codigo,
                        'nombre': nombre,
                        'cantidad': cantidad,
                        'precio_unitario': precio,
                        'subtotal': precio * cantidad,
                        'categoria': categoria
                    })

                # Crear registro de devolución
                Devolucion.objects.create(
                    factura=factura,
                    tipo_devolucion='total',
                    productos_devueltos=productos_devueltos,
                    monto_devuelto=monto_total_devuelto,
                    motivo='Devolución total procesada desde el sistema',
                    procesado_por=request.user
                )

                factura.estado = 'totalmente_devuelta'
                factura.fecha_devolucion = timezone.now()
                factura.save()

                print(f"\n✅ DEVOLUCIÓN TOTAL COMPLETADA")
                print(f"   Bebidas repuestas: {bebidas_repuestas}")
                print(f"   Monto devuelto: ${monto_total_devuelto:.2f}")

                messages.success(
                    request,
                    f'✅ Devolución total procesada. Monto: ${monto_total_devuelto:.2f}. Bebidas repuestas: {bebidas_repuestas}'
                )

                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

        except Exception as e:
            messages.error(
                request, f'❌ Error al procesar devolución: {str(e)}')
            import traceback
            traceback.print_exc()
            return redirect('anulacionydevolucion')

    return redirect('anulacionydevolucion')

# ============================================================
# DEVOLUCIÓN PARCIAL
# ============================================================


@login_required
def procesar_devolucion_parcial(request):
    """Procesar devolución parcial con validación mejorada"""
    if request.method == 'POST':
        numero_factura = request.POST.get('numero_factura')
        productos_json = request.POST.get('productos_devueltos', '[]')

        if not numero_factura:
            messages.error(request, 'Número de factura requerido')
            return redirect('anulacionydevolucion')

        try:
            factura = get_object_or_404(Factura, numero_factura=numero_factura)

            if factura.estado not in ['pagada', 'parcialmente_devuelta']:
                messages.error(
                    request,
                    f'Estado inválido para devolución: {factura.get_estado_display()}'
                )
                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

            productos_devueltos = json.loads(productos_json)

            if not productos_devueltos:
                messages.error(request, 'Debes seleccionar productos')
                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

            with transaction.atomic():
                items_factura = factura.get_items_detalle()
                productos_procesados = []
                monto_total_devuelto = Decimal('0.00')
                bebidas_repuestas = 0

                print(f"\n🔄 PROCESANDO DEVOLUCIÓN PARCIAL")

                for producto_data in productos_devueltos:
                    producto_nombre = producto_data.get('nombre', '')
                    cantidad_devolver = float(producto_data.get('cantidad', 0))
                    categoria = producto_data.get('categoria', '')

                    # Buscar en items de factura
                    item_factura = buscar_item_por_nombre(
                        items_factura, producto_nombre)
                    if not item_factura:
                        messages.error(
                            request, f'Producto {producto_nombre} no encontrado')
                        return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

                    cantidad_original = float(item_factura.get('cantidad', 0))
                    cantidad_ya_devuelta = factura.get_cantidad_ya_devuelta(
                        producto_nombre)
                    cantidad_disponible = cantidad_original - cantidad_ya_devuelta

                    # VALIDACIÓN CRÍTICA
                    if cantidad_devolver > cantidad_disponible:
                        messages.error(
                            request,
                            f'❌ {producto_nombre}: Intentas devolver {cantidad_devolver} pero solo hay {cantidad_disponible} disponible (ya devuelto: {cantidad_ya_devuelta})'
                        )
                        return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

                    precio = Decimal(str(item_factura.get('precio', 0)))
                    subtotal = precio * Decimal(str(cantidad_devolver))
                    codigo = item_factura.get('codigo', '')

                    print(f"\n📦 {producto_nombre}")
                    print(
                        f"   Devolver: {cantidad_devolver} de {cantidad_disponible} disponibles")
                    print(f"   Código: '{codigo}', Categoría: '{categoria}'")

                    # Reponer stock para bebidas
                    if categoria.lower() == 'bebida':
                        identificador = codigo if codigo and codigo.strip() else producto_nombre
                        print(f"   🍺 Reponiendo con: '{identificador}'")

                        if reponer_stock_producto(identificador, cantidad_devolver):
                            bebidas_repuestas += 1
                            print(f"   ✅ Stock repuesto")
                        else:
                            print(f"   ⚠️  Advertencia: No se pudo reponer stock")

                    monto_total_devuelto += subtotal
                    productos_procesados.append({
                        'producto_id': item_factura.get('producto_id'),
                        'codigo': codigo,
                        'nombre': producto_nombre,
                        'cantidad': cantidad_devolver,
                        'precio_unitario': float(precio),
                        'subtotal': float(subtotal),
                        'categoria': categoria
                    })

                # Crear registro de devolución
                Devolucion.objects.create(
                    factura=factura,
                    tipo_devolucion='parcial',
                    productos_devueltos=productos_procesados,
                    monto_devuelto=monto_total_devuelto,
                    motivo='Devolución parcial procesada',
                    procesado_por=request.user
                )

                # Actualizar estado de factura
                if factura.estado == 'pagada':
                    factura.estado = 'parcialmente_devuelta'

                # Verificar si ya se devolvió todo
                productos_disponibles = factura.get_productos_disponibles_devolucion()
                if not productos_disponibles:
                    factura.estado = 'totalmente_devuelta'

                factura.fecha_devolucion = timezone.now()
                factura.save()

                print(f"\n✅ DEVOLUCIÓN COMPLETADA")
                print(f"   Bebidas repuestas: {bebidas_repuestas}")
                print(f"   Monto: ${monto_total_devuelto}")

                messages.success(
                    request,
                    f'✅ Devolución procesada: ${monto_total_devuelto:.2f}. Bebidas repuestas: {bebidas_repuestas}'
                )

                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
            import traceback
            traceback.print_exc()
            return redirect('anulacionydevolucion')

    return redirect('anulacionydevolucion')

# ============================================================
# ANULACIÓN DE FACTURA
# ============================================================


@login_required
def procesar_anulacion_factura(request):
    """Procesar anulación de una factura (disminuir stock de bebidas)"""
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
                bebidas_disminuidas = 0

                print(f"\n❌ PROCESANDO ANULACIÓN DE FACTURA")

                # DISMINUIR stock para productos bebida
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
                            f"   🍺 ES BEBIDA - Disminuyendo stock con: '{identificador}'")

                        if disminuir_stock_producto(identificador, cantidad):
                            bebidas_disminuidas += 1
                            print(f"   ✅ Stock disminuido exitosamente")

                factura.estado = 'anulada'
                factura.motivo_anulacion = motivo
                factura.fecha_devolucion = timezone.now()
                factura.save()

                print(f"\n✅ ANULACIÓN COMPLETADA")
                print(f"   Bebidas ajustadas: {bebidas_disminuidas}")

                messages.success(
                    request,
                    f'✅ Factura {factura.numero_factura} anulada. Bebidas ajustadas: {bebidas_disminuidas}'
                )

                return redirect(f'{reverse("anulacionydevolucion")}?numero_factura={factura.numero_factura}')

        except Exception as e:
            messages.error(request, f'❌ Error al anular factura: {str(e)}')
            import traceback
            traceback.print_exc()
            return redirect('anulacionydevolucion')

    return redirect('anulacionydevolucion')





def registrodeclientes(request):
    """Vista para el registro de clientes"""
    
    # Si es POST y es AJAX
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Obtener datos del formulario
            cedula = request.POST.get('cedula', '').strip()
            nombre_completo = request.POST.get('nombre_completo', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            telefono_principal = request.POST.get('telefono_principal', '').strip()
            telefono_alternativo = request.POST.get('telefono_alternativo', '').strip()
            
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
            telefono_principal_limpio = ''.join(filter(str.isdigit, telefono_principal))
            if not telefono_principal_limpio or len(telefono_principal_limpio) != 10:
                return JsonResponse({
                    'success': False,
                    'error': 'El teléfono principal debe tener 10 dígitos'
                })
            
            # Validar teléfono alternativo si existe
            if telefono_alternativo:
                telefono_alt_limpio = ''.join(filter(str.isdigit, telefono_alternativo))
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
                notas_credito=notas_credito if notas_credito else None
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
