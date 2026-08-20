"""Database models for the box-selection system.

Dimensions are stored in centimetres, weight in kilograms and cost in a single
currency. ``DecimalField`` is used throughout to avoid binary float rounding on
money and measurements.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

# A tiny positive lower bound so dimensions/weights must be strictly > 0.
# Decimal (not float) keeps DRF's model-field introspection warning-free.
_POSITIVE = MinValueValidator(Decimal("0.001"))


class Box(models.Model):
    """A shipping box in the catalogue, described by its *internal* dimensions."""

    name = models.CharField(max_length=100, unique=True)
    inner_length = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[_POSITIVE],
        help_text="Internal length in cm.",
    )
    inner_width = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[_POSITIVE],
        help_text="Internal width in cm.",
    )
    inner_height = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[_POSITIVE],
        help_text="Internal height in cm.",
    )
    max_weight = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[_POSITIVE],
        help_text="Maximum load in kg.",
    )
    cost = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(0)],
        help_text="Unit cost of the box.",
    )
    is_active = models.BooleanField(
        default=True, help_text="Only active boxes are considered for selection."
    )

    class Meta:
        ordering = ["cost", "name"]
        verbose_name_plural = "boxes"

    def __str__(self) -> str:
        return f"{self.name} ({self.inner_length}x{self.inner_width}x{self.inner_height} cm)"

    @property
    def volume(self):
        return self.inner_length * self.inner_width * self.inner_height


class Product(models.Model):
    """A catalogue product used to pre-fill order lines on the frontend.

    Orders may also contain ad-hoc items that are not in this catalogue, so the
    packing logic never requires a product row to exist.
    """

    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    length = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[_POSITIVE], help_text="cm"
    )
    width = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[_POSITIVE], help_text="cm"
    )
    height = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[_POSITIVE], help_text="cm"
    )
    weight = models.DecimalField(
        max_digits=8, decimal_places=3, validators=[_POSITIVE], help_text="kg"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"
