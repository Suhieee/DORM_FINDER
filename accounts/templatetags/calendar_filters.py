from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key."""
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(key, [])
    return []
