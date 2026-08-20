"""HTTP layer: the recommendation endpoint, catalogue endpoints and the page."""
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Box, Product
from .packing import BoxSpec, OrderItem, recommend_box
from .serializers import (
    BoxSerializer,
    ProductSerializer,
    RecommendRequestSerializer,
)


def _box_to_dict(box: BoxSpec) -> dict:
    return {
        "id": box.id,
        "name": box.name,
        "inner_length": box.length,
        "inner_width": box.width,
        "inner_height": box.height,
        "max_weight": box.max_weight,
        "cost": box.cost,
    }


class RecommendView(APIView):
    """POST an order, get back the cheapest box that fits the whole thing."""

    def post(self, request):
        request_ser = RecommendRequestSerializer(data=request.data)
        request_ser.is_valid(raise_exception=True)

        items = [
            OrderItem(
                name=row["name"],
                length=row["length"],
                width=row["width"],
                height=row["height"],
                weight=row["weight"],
                quantity=row["quantity"],
            )
            for row in request_ser.validated_data["items"]
        ]

        boxes = [
            BoxSpec(
                id=b.id,
                name=b.name,
                length=float(b.inner_length),
                width=float(b.inner_width),
                height=float(b.inner_height),
                max_weight=float(b.max_weight),
                cost=float(b.cost),
            )
            for b in Box.objects.filter(is_active=True)
        ]

        if not boxes:
            return Response(
                {"detail": "No active boxes are configured. Load the catalogue first."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        result = recommend_box(items, boxes)

        payload = {
            "found": result.found,
            "recommended_box": _box_to_dict(result.recommended) if result.found else None,
            "order_summary": {
                "total_units": result.total_units,
                "total_weight_kg": result.total_weight,
                "total_item_volume_cm3": result.total_item_volume,
            },
            "evaluations": [
                {
                    "box": e.box.name,
                    "cost": e.box.cost,
                    "fits": e.fits,
                    "fill_rate": e.fill_rate,
                    "reason": e.reason,
                }
                for e in result.evaluations
            ],
            "layout": [
                {
                    "item": p.item,
                    "position": {"x": p.position[0], "y": p.position[1], "z": p.position[2]},
                    "dimensions": {
                        "length": p.dimensions[0],
                        "width": p.dimensions[1],
                        "height": p.dimensions[2],
                    },
                    "rotation_type": p.rotation_type,
                    "rotated": p.rotated,
                    "orientation": p.orientation,
                }
                for p in result.layout
            ],
        }
        if not result.found:
            payload["detail"] = (
                "No available box can hold this order. Consider splitting it "
                "across multiple boxes or adding a larger box to the catalogue."
            )
        return Response(payload, status=status.HTTP_200_OK)


class BoxListView(ListAPIView):
    """GET the active box catalogue."""

    queryset = Box.objects.filter(is_active=True)
    serializer_class = BoxSerializer


class ProductListView(ListAPIView):
    """GET the product catalogue (used to auto-fill order lines)."""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class IndexView(TemplateView):
    template_name = "selection/index.html"
