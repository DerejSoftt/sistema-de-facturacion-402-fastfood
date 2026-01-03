

from django.shortcuts import render, redirect,  get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from .models import Producto, Plato, Pedido, Mesa, DeliveryConfig, HistorialEstadoPedido, DetalleItemPedido, Factura
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
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
    categorias = Producto.objects.values_list('categoria', flat=True).distinct()
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
    """Actualizar la cantidad de un producto"""
    if request.method == 'POST':
        producto = get_object_or_404(Producto, id=producto_id)
        nueva_cantidad = request.POST.get('cantidad', 0)
        
        try:
            producto.cantidad = Decimal(nueva_cantidad)
            producto.save()
            return redirect('inventario')
        except:
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
                    messages.error(request, 'Nombre y categoría son requeridos')
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
                messages.success(request, f'Plato "{nombre}" (Código: {plato.codigo}) guardado exitosamente')
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
        categorias = platos.values_list('categoria', flat=True).distinct().count()
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
    if request.method == 'PUT':
        try:
            plato = Plato.objects.get(id=plato_id)
            
            # Parsear datos JSON
            data = json.loads(request.body)
            
            # Actualizar campos
            if 'nombre' in data:
                plato.nombre = data['nombre'].strip()
            
            if 'categoria' in data:
                plato.categoria = data['categoria']
            
            if 'precio' in data:
                try:
                    precio = float(data['precio'])
                    if precio >= 0:
                        plato.precio = precio
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Precio inválido'})
            
            plato.save()
            
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
            estado__in=['pendiente', 'confirmado', 'preparacion', 'listo', 'entregado']
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
                'disponibilidad': 'disponible',  # Asumimos que todos los platos activos están disponibles
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
            print(f"  - {bebida.nombre}: ${bebida.precio_compra} (Stock: {bebida.cantidad})")
        print(f"PLATOS ENCONTRADOS: {platos.count()}")
        for plato in platos:
            print(f"  - {plato.nombre}: ${plato.precio} ({plato.get_categoria_display()})")
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


from decimal import Decimal
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
                messages.error(request, 'Error al procesar los items del carrito')
                return redirect('pedidos')
                
            if not cart_items:
                messages.error(request, 'El carrito está vacío')
                return redirect('pedidos')
            
            print("=" * 80)
            print("ITEMS EN EL CARRITO (PARSED):")
            for idx, item in enumerate(cart_items):
                print(f"  [{idx}] {item.get('name')} (ID: {item.get('id')}, Tipo: {item.get('tipo')}, es_bebida: {item.get('es_bebida')}, Quantity: {item.get('quantity')})")
            print("=" * 80)
            
            # 🔥 VALIDAR STOCK DE BEBIDAS ANTES DE CREAR EL PEDIDO
            bebidas_sin_stock = []
            
            for item in cart_items:
                # Si el item es una bebida (tipo = 'bebida' o es_bebida = True)
                if item.get('tipo') == 'bebida' or item.get('es_bebida'):
                    # Extraer el ID real del prefijo "bebida_"
                    item_id = item.get('id', '')
                    print(f"Procesando bebida - item_id original: {item_id}")
                    
                    bebida_id = None
                    
                    if isinstance(item_id, str):
                        if item_id.startswith('bebida_'):
                            try:
                                bebida_id = int(item_id.replace('bebida_', ''))
                            except ValueError:
                                print(f"ERROR: No se pudo convertir ID: {item_id}")
                                bebidas_sin_stock.append(f"ID inválido para {item.get('name')}")
                                continue
                        else:
                            # Si no tiene prefijo pero es número
                            try:
                                bebida_id = int(item_id)
                            except ValueError:
                                print(f"ERROR: ID no numérico: {item_id}")
                                bebidas_sin_stock.append(f"ID inválido para {item.get('name')}")
                                continue
                    else:
                        # Si ya es un número
                        bebida_id = int(item_id)
                    
                    cantidad_solicitada = int(item.get('quantity', 1))
                    
                    print(f"Validando bebida - ID: {bebida_id}, Nombre: {item.get('name')}, Cantidad: {cantidad_solicitada}")
                    
                    try:
                        bebida = Producto.objects.get(id=bebida_id, categoria='bebida')
                        
                        # Verificar si hay suficiente stock
                        # 🔥 Convertir a Decimal para comparación
                        stock_disponible = Decimal(str(bebida.cantidad))
                        if stock_disponible < cantidad_solicitada:
                            error_msg = f'❌ No hay suficiente stock de {bebida.nombre}. Disponible: {stock_disponible}, Solicitado: {cantidad_solicitada}'
                            bebidas_sin_stock.append(error_msg)
                            print(error_msg)
                            continue
                            
                        # Reducir el stock de la bebida
                        bebida.cantidad = stock_disponible - Decimal(str(cantidad_solicitada))
                        bebida.save()
                        print(f"✅ Stock reducido para {bebida.nombre}: nuevo stock = {bebida.cantidad}")
                        
                    except Producto.DoesNotExist:
                        error_msg = f'❌ La bebida "{item.get("name")}" ya no está disponible'
                        bebidas_sin_stock.append(error_msg)
                        print(error_msg)
                        continue
            
            # Si hay bebidas sin stock, mostrar error y cancelar el pedido
            if bebidas_sin_stock:
                for error in bebidas_sin_stock:
                    messages.error(request, error)
                return redirect('pedidos')
            
            # Crear el pedido - SIN usuario
            pedido = Pedido(
                tipo_pedido=tipo_pedido,
                items=cart_items,
                subtotal=subtotal,
                envio=envio,
                total=total,
                estado='pendiente',
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
                
                # Actualizar estado de la mesa
                mesa.estado = 'ocupada'
                mesa.save()
                
            elif tipo_pedido == 'delivery':
                codigo_delivery = request.POST.get('codigo_delivery')
                if not codigo_delivery:
                    messages.error(request, 'Se requiere código de delivery')
                    return redirect('pedidos')
                
                pedido.codigo_delivery = codigo_delivery
                
                nombre_cliente = request.POST.get('customer_name', '').strip()
                telefono_cliente = request.POST.get('customer_phone', '').strip()
                direccion_entrega = request.POST.get('customer_address', '').strip()
                
                if not nombre_cliente:
                    nombre_cliente = f"Cliente Delivery {codigo_delivery}"
                if not telefono_cliente:
                    telefono_cliente = "No especificado"
                if not direccion_entrega:
                    direccion_entrega = "Dirección no especificada"
                
                pedido.nombre_cliente = nombre_cliente
                pedido.telefono_cliente = telefono_cliente
                pedido.direccion_entrega = direccion_entrega
                
                delivery_config = DeliveryConfig.objects.filter(
                    tipo='delivery',
                    codigo=codigo_delivery
                ).first()
                if delivery_config:
                    delivery_config.estado = 'ocupado'
                    delivery_config.save()
                    
            elif tipo_pedido == 'llevar':
                codigo_llevar = request.POST.get('codigo_llevar')
                if not codigo_llevar:
                    messages.error(request, 'Se requiere código para llevar')
                    return redirect('pedidos')
                
                pedido.codigo_delivery = codigo_llevar
                
                nombre_cliente = request.POST.get('customer_name_takeaway', '').strip()
                if not nombre_cliente:
                    nombre_cliente = f"Cliente Para Llevar {codigo_llevar}"
                
                pedido.nombre_cliente = nombre_cliente
                
                llevar_config = DeliveryConfig.objects.filter(
                    tipo='llevar',
                    codigo=codigo_llevar
                ).first()
                if llevar_config:
                    llevar_config.estado = 'ocupado'
                    llevar_config.save()
            else:
                messages.error(request, 'Tipo de pedido no válido')
                return redirect('pedidos')
            
            # Guardar el pedido (esto generará automáticamente el código_pedido)
            pedido.save()
            print(f"✅ Pedido {pedido.codigo_pedido} creado con ID: {pedido.id}")
            
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
                    
                    nombre_plato = item.get('name', item.get('nombre', 'Sin nombre'))
                    cantidad = int(item.get('quantity', 1))
                    # 🔥 Convertir a Decimal en lugar de float
                    precio_unitario = Decimal(str(item.get('price', item.get('precio', 0))))
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
                        print(f"    ⚠️ ADVERTENCIA: ID inválido para {nombre_plato}, usando 0")
                    
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
            
            # Generar ticket del lado del servidor
            generar_ticket_chef_servidor(pedido, cart_items)
            
            # Contar platos y bebidas
            platos_count = sum(1 for item in cart_items if item.get('tipo') != 'bebida' and not item.get('es_bebida'))
            bebidas_count = sum(1 for item in cart_items if item.get('tipo') == 'bebida' or item.get('es_bebida'))
            
            messages.success(
                request, 
                f'✅ Pedido {pedido.codigo_pedido} creado exitosamente! '
                f'Platos: {platos_count} | Bebidas: {bebidas_count} | '
                f'Total: ${total:.2f}'
            )
            
            # Redirigir a la página de gestión de pedidos
            return redirect('gestion_pedidos')
            
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
        platos_items = [item for item in cart_items if item.get('tipo') != 'bebida' and not item.get('es_bebida')]
        bebidas_items = [item for item in cart_items if item.get('tipo') == 'bebida' or item.get('es_bebida')]
        
        context = {
            'pedido': pedido,
            'items': cart_items,
            'platos_items': platos_items,
            'bebidas_items': bebidas_items,
            'fecha': now().strftime('%d/%m/%Y %H:%M'),
            'codigo_display': codigo_display,
            'total_items': len(cart_items),
            'platos_count': len(platos_items),
            'bebidas_count': len(bebidas_items),
            'tiempo_estimado': sum(item.get('prepTime', 15) for item in cart_items),
        }
        
        ticket_html = render_to_string('facturacion/ticket_chef.html', context)
        
        # Guardar ticket en archivo o base de datos si es necesario
        print("=" * 50)
        print("TICKET COCINA GENERADO")
        print(f"Código: {codigo_display}")
        print(f"Fecha: {context['fecha']}")
        print(f"Items totales: {len(cart_items)}")
        print(f"  - Platos: {len(platos_items)}")
        print(f"  - Bebidas: {len(bebidas_items)}")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error generando ticket del chef: {e}")
@csrf_exempt 
def limpiar_carrito(request):
    """Vista para limpiar el carrito (opcional)"""
    # En una aplicación real, esto limpiaría el carrito de la sesión
    # request.session['cart'] = []
    
    messages.success(request, 'Carrito limpiado exitosamente')
    return redirect('pedidos')

@csrf_exempt 
def gestiondepedidos(request):
    """Vista principal de gestión de pedidos"""
    # Obtener parámetros de filtrado
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    tipo_pedido = request.GET.get('tipo', '')
    fecha = request.GET.get('fecha', '')
    sort_by = request.GET.get('sort', '-fecha_pedido')
    page = request.GET.get('page', 1)
    
    # Construir query base
    pedidos = Pedido.objects.all().select_related('mesa').order_by('-fecha_pedido')
    
    # Aplicar filtros
    if search:
        pedidos = pedidos.filter(
            Q(codigo_pedido__icontains=search) |
            Q(nombre_cliente__icontains=search) |
            Q(telefono_cliente__icontains=search) |
            Q(mesa__numero__icontains=search)
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
    
    # Paginación
    paginator = Paginator(pedidos, 10)
    page_obj = paginator.get_page(page)
    
    # Calcular estadísticas
    today = datetime.now().date()
    
    # Total de pedidos
    total_pedidos = Pedido.objects.count()
    
    # Pedidos pendientes/preparación
    pedidos_pendientes = Pedido.objects.filter(
        estado__in=['pendiente', 'confirmado', 'preparacion']
    ).count()
    
    # Ingresos de hoy (excluyendo cancelados)
    ingresos_hoy = Pedido.objects.filter(
        fecha_pedido__date=today,
        estado__in=['entregado', 'completado', 'listo']
    ).aggregate(total=Sum('total'))['total'] or 0
    
    # Pedidos a domicilio (no cancelados)
    pedidos_domicilio = Pedido.objects.filter(
        tipo_pedido='delivery',
        estado__in=['pendiente', 'confirmado', 'preparacion', 'listo', 'entregado', 'completado']
    ).count()
    
    context = {
        'user': request.user,
        'page_title': 'Gestión de Pedidos',
        'pedidos': page_obj,
        'estadisticas': {
            'total_pedidos': total_pedidos,
            'pedidos_pendientes': pedidos_pendientes,
            'ingresos_hoy': ingresos_hoy,
            'pedidos_domicilio': pedidos_domicilio,
        },
        'filtros': {
            'search': search,
            'estado': estado,
            'tipo_pedido': tipo_pedido,
            'fecha': fecha,
            'sort': sort_by,
        },
        'paginator': page_obj,
    }
    return render(request, 'facturacion/gestiondepedidos.html', context)


@csrf_exempt 
def procesar_pedidos_para_template(pedidos_queryset):
    """Procesa los pedidos para ser usados en el template"""
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
        }
        
        pedidos_procesados.append(pedido_procesado)
    
    return pedidos_procesados





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
    fecha_pedido = pedido.fecha_pedido.strftime('%A, %d de %B de %Y a las %H:%M')
    
    # Determinar información del cliente
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
        'items': items,
        'subtotal': float(pedido.subtotal),
        'envio': float(pedido.envio),
        'total': float(pedido.total),
        'notas': pedido.notas or '',
        'cantidad_items': pedido.get_cantidad_items(),
        'tiempo_preparacion': pedido.get_tiempo_preparacion_estimado(),
    }
    
    return JsonResponse(data)

@csrf_exempt 
def cambiar_estado_pedido(request, pedido_id):
    """Cambiar estado de un pedido"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        pedido = get_object_or_404(Pedido, id=pedido_id)
        nuevo_estado = request.POST.get('estado')
        
        if not nuevo_estado:
            return JsonResponse({'error': 'Estado no especificado'}, status=400)
        
        # Registrar cambio en historial
        HistorialEstadoPedido.objects.create(
            pedido=pedido,
            estado_anterior=pedido.estado,
            estado_nuevo=nuevo_estado,
            usuario=request.user
        )
        
        # Actualizar pedido
        pedido.estado = nuevo_estado
        
        # Si se entrega/completa, registrar fecha de entrega
        if nuevo_estado in ['entregado', 'completado']:
            pedido.fecha_entrega = timezone.now()
        
        # LIBERAR MESA SI ES NECESARIO (tanto para completado como cancelado)
        if nuevo_estado in ['completado', 'cancelado', 'entregado'] and pedido.mesa:
            pedido.mesa.estado = 'disponible'
            pedido.mesa.save()
            # También podrías limpiar la relación si quieres
            # pedido.mesa = None
        
        pedido.actualizado_por = request.user
        pedido.save()
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Estado actualizado a {pedido.get_estado_display()}',
            'estado': pedido.estado,
            'estado_display': pedido.get_estado_display(),
            'codigo_pedido': pedido.codigo_pedido
        })
        
    except Exception as e:
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
        
        # LIBERAR MESA ANTES DE CUALQUIER OPERACIÓN SI EXISTE
        if pedido.mesa:
            pedido.mesa.estado = 'disponible'
            pedido.mesa.save()
        
        if eliminar_vista:
            # Eliminar permanentemente de la base de datos
            codigo_pedido = pedido.codigo_pedido
            pedido.delete()
            
            return JsonResponse({
                'success': True,
                'mensaje': f'Pedido {codigo_pedido} eliminado de la vista',
                'eliminado': True
            })
        else:
            # Marcar como cancelado (comportamiento anterior)
            pedido.estado = 'cancelado'
            pedido.actualizado_por = request.user
            pedido.save()
            
            return JsonResponse({
                'success': True,
                'mensaje': f'Pedido {pedido.codigo_pedido} cancelado'
            })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    


@csrf_exempt 
# En el modelo Pedido
def liberar_mesa_si_corresponde(self):
    """Libera la mesa si el pedido está en un estado que requiere liberación"""
    estados_que_liberan_mesa = ['completado', 'cancelado', 'entregado']
    
    if self.estado in estados_que_liberan_mesa and self.mesa:
        self.mesa.estado = 'disponible'
        self.mesa.save()
        # Opcional: limpiar la relación
        # self.mesa = None
        # self.save()
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
        
        # Obtener IDs de pedidos que ya tienen factura
        pedidos_con_factura_ids = list(Factura.objects.values_list('pedido_id', flat=True))
        print(f"Pedidos con factura (IDs): {pedidos_con_factura_ids}")
        
        # Obtener pedidos listos para facturar (sin factura)
        pedidos_pendientes = Pedido.objects.filter(
            estado__in=['entregado', 'listo', 'completado']
        ).exclude(
            id__in=pedidos_con_factura_ids
        ).select_related('mesa').order_by('-fecha_pedido')
        
        print(f"Pedidos disponibles para facturar: {pedidos_pendientes.count()}")
        
        # Obtener TODAS las facturas (pendientes y pagadas)
        facturas = Factura.objects.select_related('pedido').all().order_by('-fecha_factura')
        print(f"Total facturas existentes: {facturas.count()}")
        
        # Preparar datos para JavaScript
        pedidos_json = []
        
        # Añadir pedidos pendientes de facturar
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
                        })
            except Exception as e:
                print(f"Error procesando items del pedido {pedido.id}: {e}")
                items_data = [{
                    'name': 'Producto',
                    'quantity': 1,
                    'price': float(pedido.total),
                    'total': float(pedido.total),
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
                'tipo_registro': 'pedido',  # Nuevo campo para identificar tipo
                'tiene_factura': False,     # Nuevo campo
            }
            pedidos_json.append(pedido_dict)
        
        # Añadir facturas existentes
        for factura in facturas:
            try:
                items_data = factura.get_items_detalle()
                
                # Para facturas, usamos el mismo formato que pedidos pero con información adicional
                factura_dict = {
                    'id': f"factura_{factura.id}",  # ID único para facturas
                    'codigo_pedido': factura.pedido.codigo_pedido if factura.pedido else 'N/A',
                    'tipo_pedido': factura.tipo_pedido,
                    'estado_factura': factura.estado,  # Estado de la factura (pagada/pendiente)
                    'estado': 'facturado',  # Estado general
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
                    'tipo_registro': 'factura',  # Identifica que es una factura
                    'tiene_factura': True,
                    'factura_id': factura.id,
                    'numero_factura': factura.numero_factura,
                    'metodo_pago': factura.metodo_pago,
                    'fecha_factura': factura.fecha_factura.isoformat() if factura.fecha_factura else None,
                }
                pedidos_json.append(factura_dict)
            except Exception as e:
                print(f"Error procesando factura {factura.id}: {e}")
        
        print(f"Total registros (pedidos + facturas): {len(pedidos_json)}")
        
        # Preparar facturas para estadísticas
        facturas_json = []
        for factura in facturas:
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
                    'iva': float(factura.iva),
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
        
        total_facturas = facturas.count()
        facturas_mes = facturas.filter(fecha_factura__date__gte=inicio_mes)
        ingresos_mes = sum(float(f.total) for f in facturas_mes.filter(estado='pagada'))
        facturas_pendientes_count = facturas.filter(estado='pendiente').count()
        
        promedio_factura = 0
        if total_facturas > 0:
            total_ingresos = sum(float(f.total) for f in facturas.filter(estado='pagada'))
            promedio_factura = total_ingresos / total_facturas
        
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
        print(f"Total registros: {len(pedidos_json)}")
        
        return render(request, 'facturacion/facturacion.html', context)
        
    except Exception as e:
        import traceback
        print(f"ERROR en facturación: {str(e)}")
        print(traceback.format_exc())
        
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
            
            # Calcular totales
            subtotal = float(request.POST.get('subtotal', pedido.subtotal))
            envio = float(request.POST.get('envio', pedido.envio))
            iva = subtotal * 0.12  # 12% IVA
            total = subtotal + iva + envio
            
            # Obtener items del pedido
            items_json = request.POST.get('items', '[]')
            try:
                items = json.loads(items_json)
            except:
                items = pedido.get_items_detalle()
            
            # Crear la factura
            factura = Factura(
                pedido=pedido,
                tipo_pedido=pedido.tipo_pedido,
                metodo_pago=request.POST.get('metodo_pago', 'efectivo'),
                estado=request.POST.get('estado', 'pagada'),
                subtotal=subtotal,
                iva=iva,
                envio=envio,
                total=total,
                items=items,
                notas=request.POST.get('notas', ''),
                creado_por=request.user,
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
            
            # Si viene fecha específica
            if request.POST.get('invoice_date'):
                try:
                    factura.fecha_factura = datetime.strptime(
                        request.POST.get('invoice_date'), 
                        '%Y-%m-%d'
                    )
                except:
                    pass
            
            # Guardar la factura
            factura.save()
            
            # Actualizar estado del pedido
            pedido.estado = 'completado'
            pedido.save()
            
            # Verificar si se debe imprimir
            if request.POST.get('imprimir') == 'true':
                # Redirigir a la vista de impresión
                return redirect('imprimir_factura_termica', factura_id=factura.id)
            
            return redirect('facturacion')
            
        except Exception as e:
            print(f"Error al crear factura: {str(e)}")
            # En caso de error, redirigir con mensaje
            return redirect('facturacion')
    
    return redirect('facturacion')


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
    """Imprimir factura en formato térmico 80mm"""
    factura = get_object_or_404(Factura, id=factura_id)
    
    # Marcar como impresa
    factura.marcar_impresa()
    
    # Preparar datos para la plantilla térmica
    context = {
        'factura': factura,
        'items': factura.get_items_detalle(),
        'empresa': {
            'nombre': '402 FASTFOOD',
            'direccion': 'Av. Principal 30 DE MAYO',
            'telefono': '849-362-1791',
            
        }
    }
    
    # Usar una plantilla específica para impresión térmica
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
            cantidad = Decimal(str(data.get('cantidad')))  # Convertir a Decimal
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
            cantidad = Decimal(str(data.get('cantidad')))  # Convertir a Decimal
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
                messages.error(request, 'Por favor complete todos los campos obligatorios')
                return redirect('roles')
            
            if password != confirm_password:
                messages.error(request, 'Las contraseñas no coinciden')
                return redirect('roles')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, 'El nombre de usuario ya existe')
                return redirect('roles')
            
            if len(password) < 8:
                messages.error(request, 'La contraseña debe tener al menos 8 caracteres')
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
                    
                    messages.success(request, f'Usuario {username} creado exitosamente')
            
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
            messages.success(request, f'Usuario {username} actualizado exitosamente')
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
            messages.success(request, f'Usuario {username} eliminado exitosamente')
    
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
        'roles': ['Administrador'],  # Solo administradores pueden gestionar usuarios
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
                messages.error(request, 'No tienes permiso para acceder a este módulo')
                return redirect('index')
        return wrapper
    return decorator