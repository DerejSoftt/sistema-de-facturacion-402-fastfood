from django.urls import path
from . import views
from django.conf import settings


urlpatterns = [
    path('', views.index, name='index'),
    path('logout/', views.logout_view, name='logout'),
    path('entradadeproductos', views.entradadeproductos, name='entradadeproductos'),
    path('guardar-producto/', views.guardar_producto, name='guardar_producto'),
    path('inventario/', views.inventario, name='inventario'),
    path('producto/<int:producto_id>/eliminar/', views.eliminar_producto, name='eliminar_producto'),
    path('producto/<int:producto_id>/actualizar-cantidad/', views.actualizar_cantidad, name='actualizar_cantidad'),
    path('entradadeplatillos', views.entradadeplatillos, name='entradadeplatillos'),
    path('entrada-platos/', views.entradadeplatillos, name='entrada_platos'),
    path('guardar-plato/', views.guardar_plato, name='guardar_plato'),
    path('listadeplatillos', views.listadeplatillos, name='listadeplatillos'),
    path('lista-platos/', views.listadeplatillos, name='lista_platos'),
    path('eliminar-plato/<int:plato_id>/', views.eliminar_plato, name='eliminar_plato'),
    path('obtener-plato/<int:plato_id>/', views.obtener_plato, name='obtener_plato'),
    path('actualizar-plato/<int:plato_id>/', views.actualizar_plato, name='actualizar_plato'),
    path('pedidos', views.pedidos, name='pedidos'),
    path('pedidos/crear/', views.crear_pedido, name='crear_pedido'),
    path('pedidos/limpiar-carrito/', views.limpiar_carrito, name='limpiar_carrito'),
    path('gestiondepedidos', views.gestiondepedidos, name='gestiondepedidos'),
     path('gestiondepedidos/detalle/<int:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),
    path('gestiondepedidos/cambiar-estado/<int:pedido_id>/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
    path('gestiondepedidos/eliminar/<int:pedido_id>/', views.eliminar_pedido, name='eliminar_pedido'),
    path('facturacion', views.facturacion, name='facturacion'),
    path('facturacion/crear/', views.crear_factura, name='crear_factura'),
    path('facturacion/detalle/<int:factura_id>/', views.detalle_factura, name='detalle_factura'),
    

    path('imprimir-factura/<int:factura_id>/', views.imprimir_factura_termica, name='imprimir_factura_termica'),
    path('detalle-factura/<int:factura_id>/', views.detalle_factura, name='detalle_factura'),
    path('exportar-facturas/', views.exportar_facturas, name='exportar_facturas'),
    path('salida', views.salida, name='salida'),
     path('obtener-productos-salida/', views.obtener_productos_salida, name='obtener_productos_salida'),
     path('registrar-salida/', views.registrar_salida, name='registrar_salida'),
    path('reabastecer-producto/', views.reabastecer_producto, name='reabastecer_producto'),
    path('roles', views.roles, name='roles'),
       path('roles/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('roles/delete/<int:user_id>/', views.delete_user, name='delete_user'),
]