# tu_app/templatetags/auth_extras.py
from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Verifica si el usuario pertenece a un grupo específico
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        # Forma más eficiente de verificar
        return user.groups.filter(name=group_name).exists()
    except:
        return False

@register.simple_tag
def check_group(user, group_name):
    """
    Tag simple para verificar grupos
    """
    return has_group(user, group_name)