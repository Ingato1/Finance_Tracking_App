from django import template
import math

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtract the arg from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def absolute(value):
    """Return the absolute value of the given number"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value
