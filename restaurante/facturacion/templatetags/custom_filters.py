# En tu aplicación (facturacion/templatetags/custom_filters.py)
from django import template

register = template.Library()

@register.filter
def default_decimal(value, default_value):
    """Filtro personalizado para manejar valores decimales con valor por defecto."""
    try:
        if value is None:
            return default_value
        return value
    except:
        return default_value

@register.filter
def safe_multiply(value, multiplier):
    """Multiplica de forma segura un valor por un multiplicador."""
    try:
        return float(value) * float(multiplier)
    except (ValueError, TypeError, AttributeError):
        return 0.0