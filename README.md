![Logotipo de la aplicación](img-doc/derejfood.png)

# Documentación Técnica del Sistema de Facturación y Gestión

#

## 1. Introducción

El proyecto **Derej Food** es una plataforma integral para la operación diaria de restaurantes y comercios de alimentos. Centraliza la gestión de inventario, ciclo de ventas, control de caja, créditos, cobranzas, devoluciones y generación de comprobantes. Está construido sobre **Django 4.2.20** con un backend basado en **MySQL** y una única app denominada `facturacion`, que concentra modelos, vistas, plantillas y recursos estáticos propios del negocio.

## 2. Tecnologías y dependencias clave

- **Django 4.2.20** para el framework web y ORM.
- **MySQL** como motor relacional principal (configurado mediante variables de entorno en [settings.py](restaurante/restaurante/settings.py)).
- **ReportLab** para la emisión de comprobantes PDF y otros reportes impresos.
- **WhiteNoise** para servir archivos estáticos en despliegues productivos.
- **python-dotenv** (`load_dotenv`) para inyectar secretos y credenciales sin exponerlos en el repositorio.

## 3. Arquitectura general

- **App única (`facturacion`)**: concentra los modelos de dominio, vistas basadas en funciones y rutas declaradas en [urls.py](restaurante/facturacion/urls.py).
- **Plantillas HTML** bajo [`templates/facturacion`](restaurante/facturacion/templates/facturacion/), organizadas por vistas (ventas, dashboard, entradas, cuentas por cobrar, etc.).
- **Templatetags personalizados** en [custom_filters.py](restaurante/facturacion/templatetags/custom_filters.py) para formatear montos y números con el estilo contable local.
- **Recursos estáticos** ubicados en [static](restaurante/static/) y recolectados en [staticfiles](restaurante/staticfiles/) para despliegue.
- **Configuración central** en [settings.py](restaurante/restaurante/settings.py), donde se habilitan middlewares, almacenamiento de estáticos y parámetros regionales (`LANGUAGE_CODE='es-do'`, `TIME_ZONE='America/Santo_Domingo'`).
- **Seguridad**: autenticación estándar de Django, decoradores `login_required` y permisos para operaciones sensibles (por ejemplo edición o eliminación de inventario).

## Estructura de Carpetas

```
restaurante/
│   manage.py
│   requirements.txt
│
├── facturacion/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── templates/
│   │   └── facturacion/
│   │       ├── facturacion.html
│   │       ├── gestiondepedidos.html
│   │       ├── inventario.html
│   │       ├── registrodeclientes.html
│   │       ├── dashbort.html
│   │       ├── roles.html
│   │       ├── anulacionydevolucion.html
│   │       ├── imprimir_termica.html
│   │       ├── ticket_chef.html
│   │       ├── listadeplatillos.html
│   │       ├── pedidos.html
│   │       ├── salida.html
│   │       ├── historial_pedidos.html
│   ├── migrations/
│   ├── templatetags/
│   ├── tests.py
│   ├── admin.py
│   ├── apps.py
│
├── restaurante/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│
├── static/
│   └── img/
```

## 4. Modelo de datos principal

Los modelos residen en [models.py](restaurante/facturacion/models.py) y cubren todo el ciclo operativo.

| Modelo                  | Rol principal                                                                 | Relacionamientos destacados                                               |
| ----------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `Producto`              | Catálogo de productos con stock, precios, categorías y control de salidas.    | Consumido por `SalidaProducto`, `DetalleItemPedido`, `Factura`, `Pedido`. |
| `Plato`                 | Registro de platillos, categorías, precios y códigos automáticos.             | Asociado a `DetalleItemPedido`, `Pedido`.                                 |
| `Mesa`                  | Gestión de mesas, estados y ubicación.                                        | Relacionado a `Pedido`.                                                   |
| `Pedido`                | Encapsula cada transacción de venta, soportando mesa, delivery y para llevar. | Relación 1:N con `DetalleItemPedido`; N:1 con `Mesa`; N:1 con `Factura`.  |
| `DetalleItemPedido`     | Desglose de productos/platos vendidos, cantidades y precios unitarios.        | FK a `Pedido`, `Producto` y `Plato`.                                      |
| `Factura`               | Almacena facturas, métodos de pago, estados, items, devoluciones y totales.   | Relación 1:N con `Pedido`; N:1 con `Cliente`; N:1 con `Devolucion`.       |
| `Devolucion`            | Registra devoluciones vinculadas a una `Factura` y reinstala stock si aplica. | FK a `Factura`, `Producto`.                                               |
| `Cliente`               | Registro de clientes con límite de crédito y datos de contacto.               | Asociado a `Pedido`, `Factura`.                                           |
| `SalidaProducto`        | Auditoría de salidas de inventario por venta, daño, ajuste o consumo interno. | FK a `Producto`.                                                          |
| `HistorialEstadoPedido` | Bitácora de cambios de estado en pedidos.                                     | FK a `Pedido`, `User`.                                                    |

## 5. Módulos funcionales

### 5.1 Autenticación y roles

- Vista `index` maneja login utilizando `django.contrib.auth`. Redirige a dashboard tras autenticarse.
- Decoradores `login_required` protegen todas las vistas operativas. Los permisos restringen endpoints críticos (por ejemplo edición o eliminación de inventario).
- Vista `roles` y plantillas asociadas permiten administrar permisos básicos (frente a `User`, `Group`, `Permission`).

### 5.2 Dashboard y analítica

- `dashboard` y vistas asociadas calculan métricas diarias/mensuales con ORM y consultas agregadas.
- Indicadores: ventas, créditos, acumulados mensuales, evolución semanal, inventario disponible, productos con stock bajo, cuentas vencidas, top productos y últimas ventas.

### 5.3 Gestión de inventario

- Vista `inventario` expone un catálogo editable vía AJAX con edición y eliminación protegida para usuarios autorizados.
- `Producto.save()` genera códigos únicos, calcula subtotal y controla stock. Cada variación de cantidad dispara `SalidaProducto` para trazabilidad.
- Endpoints adicionales soportan altas manuales y carga de plantillas.

### 5.4 Clientes

- `registrodeclientes` y `gestiondeclientes` gestionan el ciclo de vida de clientes y validan límites de crédito.
- Endpoints REST permiten integraciones front-end.

### 5.5 Pedidos y facturación

- `pedidos` carga formulario con clientes activos e inventario disponible.
- `crear_pedido` valida totales, controla descuentos y soporta pedidos de mesa, delivery y para llevar.
- Cada `DetalleItemPedido` descuenta stock y registra movimientos. El view final retorna respuesta JSON con desglose de totales para usar en el frontend.

### 5.6 Devoluciones y anulaciones

- `anulacionydevolucion` controla devoluciones, reponiendo stock y marcando razones.
- Endpoints permiten revertir ventas o productos, restaurando inventario y dejando trazabilidad.

### 5.7 Reporting y utilitarios

- Reportes PDF: comprobantes, listados de cuentas vencidas y facturas reimpresas (basado en ReportLab).
- Exportaciones CSV desde funciones auxiliares en [views.py](restaurante/facturacion/views.py).
- Consultas especiales facilitan experiencias tipo POS.

### 5.8 Organización de `views.py`

El archivo monolítico [views.py](restaurante/facturacion/views.py) agrupa todas las vistas de la app y está dividido por bloques temáticos, cada uno con decoradores y helpers específicos:

- **Autenticación y dashboard**: `index`, `dashbort` y métricas diarias/mensuales.
- **Inventario**: `inventario`, `salida`, control de stock y trazabilidad.
- **Clientes y ventas**: `registrodeclientes`, `pedidos`, validaciones y creación de transacciones.
- **Devoluciones y anulaciones**: `anulacionydevolucion`, control de reversos y restablecimiento de stock.
- **Comprobantes y utilitarios**: `imprimir_termica`, `ticket_chef`, generación de PDFs y tickets.

## 6. Flujo operativo end-to-end

1. **Ingreso de mercancía**: usuarios registran productos y entradas, generando códigos únicos y movimientos de stock.
2. **Habilitación de caja**: cada vendedor abre su sesión.
3. **Venta/Pedido**:
   - Selección de cliente (existente o nuevo).
   - Construcción de carrito con validación de stock en tiempo real.
   - Configuración de pago: contado, crédito simple o delivery.
   - Confirmación: se crea `Pedido`, `DetalleItemPedido`, se descuenta stock y se actualiza el dashboard.
4. **Facturación**: se genera factura, se calcula IVA, descuentos y totales; se imprime comprobante.
5. **Devoluciones / anulaciones**: flujos dedicados revierten ventas o productos, restaurando inventario y dejando trazabilidad.
6. **Cierre**: al final del día se consolidan los datos para arqueos diarios.

## 7. Integraciones internas y archivos relevantes

- **Rutas**: cubren todo el dominio y se centralizan en [urls.py](restaurante/facturacion/urls.py).
- **Plantillas**: cada feature tiene su HTML (por ejemplo [facturacion.html](restaurante/facturacion/templates/facturacion/facturacion.html), [dashbort.html](restaurante/facturacion/templates/facturacion/dashbort.html), [cuentaporcobrar.html](cuentaporcobrar.html)).
- **Assets**: imágenes y scripts en [static/](restaurante/static/); archivos compilados en [staticfiles/](restaurante/staticfiles/) listos para WhiteNoise.

## 8. Seguridad y cumplimiento

- Credenciales de base de datos y llaves se cargan desde `.env` (no versionado).
- CSRF está habilitado globalmente; endpoints AJAX críticos usan `@csrf_exempt` solo cuando es imprescindible y se compensan con permisos.
- Validaciones server-side para montos, descuento, stock y límites de crédito evitan inconsistencias contables.
- Soft delete en modelos críticos preserva histórico sin exponer datos sensibles en documentos.

## 9. Despliegue y configuración

1. Crear archivo `.env` con las siguientes variables de entorno:

```bash
SECRET_KEY="tu_clave_secreta"
DB_NAME="nombre_base_datos"
DB_USER="usuario"
DB_PASSWORD="contraseña"
DB_HOST="localhost"
DB_PORT="3306"
ALLOWED_HOSTS="localhost,127.0.0.1"
CSRF_TRUSTED_ORIGINS="http://localhost,http://127.0.0.1"
DEBUG=True
```

2. Instalar dependencias ([requirements.txt](restaurante/requirements.txt)).
3. Ejecutar migraciones (`python manage.py migrate`).
4. Crear superusuario (`python manage.py createsuperuser`).
5. Colectar estáticos (`python manage.py collectstatic`).
6. Configurar servicio WSGI (Gunicorn/uwsgi) apuntando a [wsgi.py](restaurante/restaurante/wsgi.py) y habilitar WhiteNoise para estáticos.

## 10. Métricas y mejoras futuras sugeridas

- **KPI adicionales**: rotación de inventario, margen por categoría, aging de cuentas.
- **Alertas proactivas**: notificaciones por correo o WhatsApp para cuentas vencidas o stock crítico.
- **API pública**: encapsular endpoints clave en una API REST (Django REST Framework) para integraciones externas.
- **Pruebas automatizadas**: ampliar [tests.py](restaurante/facturacion/tests.py) con casos de venta, rebaja de deuda y devoluciones.

---

## Modelos Clave

- **Producto:** Controla productos con categorías, stock, precios y subtotales automáticos.
- **Plato:** Registro de platillos, categorías, precios y códigos automáticos.
- **Mesa:** Gestión de mesas, estados y ubicación.
- **Pedido:** Maneja pedidos, tipos, estados, items, auditoría y relación con facturas.
- **Factura:** Almacena facturas, métodos de pago, estados, items, devoluciones y totales.
- **Devolución:** Registra devoluciones de facturas, productos devueltos, motivos y montos.
- **Cliente:** Control de clientes, crédito, teléfonos, dirección y estado.
- **SalidaProducto:** Registra salidas de inventario por diferentes motivos.
- **HistorialEstadoPedido:** Rastrea cambios de estado en pedidos.

## Templates

La aplicación cuenta con templates personalizados para cada funcionalidad, con diseño moderno y sidebar fijo. Ejemplos:

- `facturacion.html`: Panel de facturación.
- `gestiondepedidos.html`: Gestión y seguimiento de pedidos.
- `inventario.html`: Control de productos y stock.
- `registrodeclientes.html`: Registro y consulta de clientes.
- `dashbort.html`: Dashboard de métricas.
- `roles.html`: Gestión de usuarios y permisos.
- `anulacionydevolucion.html`: Devoluciones y anulaciones.
- `imprimir_termica.html`: Factura para impresión térmica.
- `ticket_chef.html`: Ticket para cocina.
- `listadeplatillos.html`: Gestión de platillos.
- `pedidos.html`: Visualización de pedidos.
- `salida.html`: Registro de salidas de productos.
- `historial_pedidos.html`: Historial de pedidos pagados.

## Instalación

1. **Requisitos:**
   - Python 3.10+
   - Django 4.2.20
   - MySQL
   - Paquetes adicionales: `mysqlclient`, `pillow`, `reportlab`, `asgiref`, `sqlparse`, `tzdata`, `charset-normalizer`.

2. **Instalación de dependencias:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configuración de base de datos:**
   - Edita las variables de entorno en `.env` para definir `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
   - El sistema utiliza MySQL con configuración estricta y soporte para zona horaria.

4. **Migraciones:**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Creación de superusuario:**

   ```bash
   python manage.py createsuperuser
   ```

6. **Ejecución del servidor:**
   ```bash
   python manage.py runserver
   ```

## Uso

- Accede al sistema desde el navegador en `http://localhost:8000`.
- Inicia sesión con usuario registrado.
- Utiliza el dashboard para visualizar métricas.
- Gestiona inventario, pedidos, facturación, devoluciones y clientes desde el menú lateral.
- Imprime facturas y tickets desde las vistas correspondientes.

## Seguridad y Roles

- El sistema implementa autenticación y autorización basada en usuarios, grupos y permisos de Django.
- Los roles permiten segmentar el acceso a funcionalidades críticas.

## Pruebas

- El archivo `tests.py` está preparado para pruebas unitarias con Django TestCase.
- Se recomienda implementar pruebas para cada modelo y vista crítica.

## Personalización

- Los templates pueden ser adaptados para branding propio.
- El sistema soporta ampliación de modelos y vistas para nuevas funcionalidades.

## Dependencias

Ver archivo [restaurante/requirements.txt](restaurante/requirements.txt) para la lista completa.

## Configuración

- Variables de entorno para seguridad y base de datos.
- Soporte para archivos estáticos y media.
- Configuración de zona horaria: `America/Santo_Domingo`.

## Contacto y Soporte

Para soporte, contactar al desarrollador o consultar la documentación de Django.

---
