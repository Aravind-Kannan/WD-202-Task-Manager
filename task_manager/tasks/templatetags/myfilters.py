from django import template

register = template.Library()


# ? How to create custom template tags and filters
# ? Refer: https://docs.djangoproject.com/en/4.0/howto/custom-template-tags/
# * Registering custom filter 'addclass': converts the variable into widget and applies class to that widget
@register.filter(name="addclass")
def addclass(value, arg):
    return value.as_widget(attrs={"class": arg})
