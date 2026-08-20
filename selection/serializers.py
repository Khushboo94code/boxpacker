"""DRF serializers: request validation and response shaping for the API."""
from rest_framework import serializers

from .models import Box, Product


class BoxSerializer(serializers.ModelSerializer):
    volume = serializers.SerializerMethodField()

    class Meta:
        model = Box
        fields = [
            "id", "name", "inner_length", "inner_width", "inner_height",
            "max_weight", "cost", "is_active", "volume",
        ]

    def get_volume(self, obj) -> float:
        return float(obj.volume)


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "sku", "name", "length", "width", "height", "weight"]


class OrderItemSerializer(serializers.Serializer):
    """One line of an incoming order. Dimensions in cm, weight in kg."""

    name = serializers.CharField(max_length=150, default="item")
    length = serializers.FloatField()
    width = serializers.FloatField()
    height = serializers.FloatField()
    weight = serializers.FloatField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        for dim in ("length", "width", "height"):
            if attrs[dim] <= 0:
                raise serializers.ValidationError(
                    {dim: "Must be greater than 0."}
                )
        if attrs["weight"] < 0:
            raise serializers.ValidationError(
                {"weight": "Must be zero or greater."}
            )
        return attrs


class RecommendRequestSerializer(serializers.Serializer):
    """The body of POST /api/recommend/: a non-empty list of order items."""

    items = OrderItemSerializer(many=True, allow_empty=False)
