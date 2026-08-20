"""Admin registration so the box and product catalogues are editable in /admin."""
from django.contrib import admin

from .models import Box, Product


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = (
        "name", "inner_length", "inner_width", "inner_height",
        "max_weight", "cost", "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("cost", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "length", "width", "height", "weight")
    search_fields = ("name", "sku")
