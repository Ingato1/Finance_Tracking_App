from django import template

register = template.Library()

@register.filter
def sum_attributes(queryset, attribute):
    return sum(getattr(item, attribute, 0) for item in queryset)

@register.filter
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0