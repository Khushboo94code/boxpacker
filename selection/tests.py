"""
Test suite for the box-selection system.

Two layers:
  * ``PackingLogicTests`` — pure algorithm tests (no DB, no HTTP). These are the
    important ones: they pin down the geometric behaviour, especially the case
    that motivated using 3D bin packing over naive volume math.
  * ``RecommendApiTests`` — end-to-end tests of the DRF endpoint against the DB.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Box
from .packing import (
    BoxSpec,
    OrderItem,
    order_fits_in_box,
    pack_order_into_box,
    recommend_box,
)


# --- shared fixtures for the pure-logic tests -------------------------------
SMALL = BoxSpec("Small", 20, 15, 10, max_weight=2, cost=0.50, id=1)
MEDIUM = BoxSpec("Medium", 30, 25, 20, max_weight=8, cost=1.20, id=2)
LARGE = BoxSpec("Large", 45, 35, 30, max_weight=20, cost=2.50, id=3)
TUBE = BoxSpec("Tube", 80, 12, 12, max_weight=3, cost=1.80, id=4)
CATALOG = [SMALL, MEDIUM, LARGE, TUBE]


class PackingLogicTests(TestCase):
    def test_poster_tube_does_not_fit_small_box(self):
        """The headline edge case: a long item must be rejected by a short box
        even though its volume is tiny."""
        poster = OrderItem("A2 Poster", length=45, width=6, height=6, weight=0.4)
        # Volume of poster (1620 cm3) < Small box volume (3000 cm3) — naive
        # volume math would wrongly accept it. 3D packing must reject it.
        self.assertLess(poster.volume, SMALL.volume)
        self.assertFalse(order_fits_in_box(SMALL, [poster]))

    def test_poster_tube_fits_tube_box(self):
        poster = OrderItem("A2 Poster", length=45, width=6, height=6, weight=0.4)
        self.assertTrue(order_fits_in_box(TUBE, [poster]))

    def test_recommendation_prefers_cheapest_fitting_box(self):
        poster = OrderItem("A2 Poster", length=45, width=6, height=6, weight=0.4)
        result = recommend_box([poster], CATALOG)
        self.assertTrue(result.found)
        # Both Tube (1.80) and Large (2.50) fit; Tube is cheaper -> chosen.
        self.assertEqual(result.recommended.name, "Tube")

    def test_single_small_item_uses_small_box(self):
        book = OrderItem("Book", length=18, width=12, height=2, weight=0.3)
        result = recommend_box([book], CATALOG)
        self.assertTrue(result.found)
        self.assertEqual(result.recommended.name, "Small")

    def test_weight_capacity_is_enforced(self):
        """An item that fits geometrically but is too heavy must be rejected."""
        anvil = OrderItem("Anvil", length=10, width=10, height=5, weight=5)
        self.assertFalse(order_fits_in_box(SMALL, [anvil]))  # cap is 2 kg
        result = recommend_box([anvil], CATALOG)
        self.assertTrue(result.found)
        # Small (2kg) too light; Medium (8kg) is cheapest that carries 5 kg.
        self.assertEqual(result.recommended.name, "Medium")

    def test_multiple_items_need_larger_box(self):
        """Several items whose combined footprint exceeds the small box."""
        items = [OrderItem("Mug", 12, 9, 11, 0.4, quantity=6)]
        result = recommend_box(items, CATALOG)
        self.assertTrue(result.found)
        self.assertIn(result.recommended.name, {"Medium", "Large"})

    def test_no_box_fits_returns_not_found(self):
        giant = OrderItem("Wardrobe", length=200, width=100, height=90, weight=5)
        result = recommend_box([giant], CATALOG)
        self.assertFalse(result.found)
        self.assertIsNone(result.recommended)
        self.assertTrue(all(not e.fits for e in result.evaluations))

    def test_quantity_is_respected(self):
        """One book fits Small; twelve books should not."""
        one = OrderItem("Book", 18, 12, 2, 0.3, quantity=1)
        many = OrderItem("Book", 18, 12, 2, 0.15, quantity=12)
        self.assertTrue(order_fits_in_box(SMALL, [one]))
        self.assertFalse(order_fits_in_box(SMALL, [many]))

    def test_empty_order_raises(self):
        with self.assertRaises(ValueError):
            recommend_box([], CATALOG)

    def test_invalid_item_dimensions_raise(self):
        with self.assertRaises(ValueError):
            OrderItem("Bad", length=0, width=5, height=5, weight=1)

    def test_layout_reports_position_and_orientation(self):
        """The packer's per-item placement (position + rotation) is surfaced."""
        items = [
            OrderItem("Book", 20, 13, 3, 0.3, quantity=2),
            OrderItem("Mug", 12, 9, 11, 0.4, quantity=1),
        ]
        fits, placements = pack_order_into_box(MEDIUM, items)
        self.assertTrue(fits)
        self.assertEqual(len(placements), 3)  # 2 books + 1 mug = 3 units
        for p in placements:
            self.assertEqual(len(p.position), 3)
            self.assertEqual(len(p.dimensions), 3)
            self.assertIn(p.rotation_type, range(6))
            self.assertIsInstance(p.rotated, bool)
            self.assertTrue(p.orientation)
        # Every placed unit stays within the box bounds along each axis.
        for p in placements:
            self.assertLessEqual(p.position[0] + p.dimensions[0], MEDIUM.length + 1e-6)
            self.assertLessEqual(p.position[1] + p.dimensions[1], MEDIUM.width + 1e-6)
            self.assertLessEqual(p.position[2] + p.dimensions[2], MEDIUM.height + 1e-6)

    def test_recommendation_includes_layout_for_chosen_box(self):
        poster = OrderItem("A2 Poster", length=45, width=6, height=6, weight=0.4)
        result = recommend_box([poster], CATALOG)
        self.assertTrue(result.found)
        self.assertEqual(len(result.layout), 1)
        self.assertEqual(result.layout[0].item, "A2 Poster#1")

    def test_no_fit_has_empty_layout(self):
        giant = OrderItem("Wardrobe", 200, 100, 90, 5)
        result = recommend_box([giant], CATALOG)
        self.assertFalse(result.found)
        self.assertEqual(result.layout, [])

    def test_evaluations_explain_each_box(self):
        poster = OrderItem("A2 Poster", length=45, width=6, height=6, weight=0.4)
        result = recommend_box([poster], CATALOG)
        names = {e.box.name for e in result.evaluations}
        self.assertEqual(names, {"Small", "Medium", "Large", "Tube"})
        small_eval = next(e for e in result.evaluations if e.box.name == "Small")
        self.assertFalse(small_eval.fits)
        self.assertTrue(small_eval.reason)  # non-empty explanation


class RecommendApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Box.objects.create(
            name="Small Mailer", inner_length=20, inner_width=15, inner_height=10,
            max_weight=2, cost="0.50",
        )
        Box.objects.create(
            name="Medium Box", inner_length=30, inner_width=25, inner_height=20,
            max_weight=8, cost="1.20",
        )
        Box.objects.create(
            name="Poster Tube", inner_length=80, inner_width=12, inner_height=12,
            max_weight=3, cost="1.80",
        )

    def test_recommend_endpoint_returns_cheapest_box(self):
        resp = self.client.post(
            reverse("recommend"),
            {"items": [
                {"name": "Book", "length": 18, "width": 12, "height": 2,
                 "weight": 0.3, "quantity": 1},
            ]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["found"])
        self.assertEqual(data["recommended_box"]["name"], "Small Mailer")

    def test_recommend_endpoint_handles_poster_edge_case(self):
        resp = self.client.post(
            reverse("recommend"),
            {"items": [
                {"name": "Poster", "length": 45, "width": 6, "height": 6,
                 "weight": 0.4, "quantity": 1},
            ]},
            format="json",
        )
        data = resp.json()
        self.assertTrue(data["found"])
        # Small Mailer is cheapest but too short; Poster Tube must be chosen.
        self.assertEqual(data["recommended_box"]["name"], "Poster Tube")

    def test_empty_items_rejected_with_400(self):
        resp = self.client.post(reverse("recommend"), {"items": []}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_negative_dimension_rejected_with_400(self):
        resp = self.client.post(
            reverse("recommend"),
            {"items": [{"length": -1, "width": 5, "height": 5, "weight": 1}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_oversized_order_reports_no_fit(self):
        resp = self.client.post(
            reverse("recommend"),
            {"items": [
                {"name": "Wardrobe", "length": 200, "width": 100, "height": 90,
                 "weight": 5, "quantity": 1},
            ]},
            format="json",
        )
        data = resp.json()
        self.assertFalse(data["found"])
        self.assertIsNone(data["recommended_box"])
        self.assertIn("detail", data)

    def test_boxes_endpoint_lists_catalog(self):
        resp = self.client.get(reverse("box-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 3)

    def test_recommend_response_includes_layout(self):
        resp = self.client.post(
            reverse("recommend"),
            {"items": [
                {"name": "Book", "length": 18, "width": 12, "height": 2,
                 "weight": 0.3, "quantity": 1},
            ]},
            format="json",
        )
        data = resp.json()
        self.assertTrue(data["found"])
        self.assertEqual(len(data["layout"]), 1)
        place = data["layout"][0]
        self.assertIn("position", place)
        self.assertIn("x", place["position"])
        self.assertIn("dimensions", place)
        self.assertIn("orientation", place)
        self.assertIn("rotation_type", place)
