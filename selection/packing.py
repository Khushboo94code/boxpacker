"""
Core box-selection logic.

This module is deliberately free of any Django imports so the packing algorithm
can be unit-tested in isolation and reused outside the web layer.

Why 3D bin packing instead of ``L x W x H`` volume math?
--------------------------------------------------------
Volume comparison answers "is there enough space?" but not "does it physically
fit?". A 30 cm poster tube has a tiny volume, yet it cannot go into a 20 cm cube
no matter how you rotate it. Comparing volumes would happily (and wrongly)
recommend the small box. We use the ``py3dbp`` library, which places each item
in 3D space trying all six orientations, so geometry that cannot fit is rejected.

Units
-----
* Dimensions: centimetres (cm)
* Weight:     kilograms (kg)
* Cost:       any single currency (compared numerically; smaller = cheaper)

The public entry point is :func:`recommend_box`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from py3dbp import Bin, Item, Packer

# py3dbp works in Decimals internally; 3 decimals is plenty for cm/kg and
# avoids floating-point noise while packing.
_NUMBER_OF_DECIMALS = 3

# We hand items to py3dbp as (width=length, height=width, depth=height), so its
# three axes line up with the box's (length, width, height) — call them the
# X, Y and Z axes. ``rotation_type`` (0-5) is which permutation py3dbp chose;
# this maps each rotation to the original edge that ends up along X / Y / Z.
# Derived directly from py3dbp's Item.get_dimension() source.
_ROTATION_AXIS_MAP = {
    0: ("length", "width", "height"),   # RT_WHD — as entered
    1: ("width", "length", "height"),   # RT_HWD
    2: ("width", "height", "length"),   # RT_HDW
    3: ("height", "width", "length"),   # RT_DHW
    4: ("height", "length", "width"),   # RT_DWH
    5: ("length", "height", "width"),   # RT_WDH
}


def _rotation_description(rotation_type: int) -> str:
    """Human-readable summary of how an item is oriented inside the box."""
    x, y, z = _ROTATION_AXIS_MAP[rotation_type]
    if rotation_type == 0:
        return f"As entered — original {z} runs vertically."
    return (
        f"Rotated so the original {z} runs vertically "
        f"(edges along box length/width/height: {x}/{y}/{z})."
    )


@dataclass(frozen=True)
class OrderItem:
    """A single product line in an order."""

    name: str
    length: float
    width: float
    height: float
    weight: float
    quantity: int = 1

    def __post_init__(self) -> None:
        if min(self.length, self.width, self.height) <= 0:
            raise ValueError(f"Item '{self.name}' has non-positive dimensions.")
        if self.weight < 0:
            raise ValueError(f"Item '{self.name}' has negative weight.")
        if self.quantity < 1:
            raise ValueError(f"Item '{self.name}' has quantity < 1.")

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height

    @property
    def sorted_dims(self) -> tuple[float, float, float]:
        """Dimensions largest-to-smallest (orientation-independent footprint)."""
        return tuple(sorted((self.length, self.width, self.height), reverse=True))


@dataclass(frozen=True)
class BoxSpec:
    """A candidate shipping box (internal dimensions)."""

    name: str
    length: float
    width: float
    height: float
    max_weight: float
    cost: float
    id: Optional[int] = None

    def __post_init__(self) -> None:
        if min(self.length, self.width, self.height) <= 0:
            raise ValueError(f"Box '{self.name}' has non-positive dimensions.")
        if self.max_weight <= 0:
            raise ValueError(f"Box '{self.name}' has non-positive max weight.")
        if self.cost < 0:
            raise ValueError(f"Box '{self.name}' has negative cost.")

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height

    @property
    def sorted_dims(self) -> tuple[float, float, float]:
        return tuple(sorted((self.length, self.width, self.height), reverse=True))


@dataclass
class Placement:
    """Where and how a single item unit sits inside the chosen box.

    Mirrors what py3dbp returns for a packed item: a lower-corner position and a
    rotation, plus the item's oriented extents along the box's length/width/height.
    All values are in centimetres.
    """

    item: str                       # unit label, e.g. "Book#2"
    position: tuple[float, float, float]      # (x, y, z) lower corner
    dimensions: tuple[float, float, float]    # extents along (length, width, height)
    rotation_type: int              # py3dbp rotation code, 0..5
    rotated: bool                   # False when kept exactly as entered
    orientation: str                # human-readable description


@dataclass
class BoxEvaluation:
    """The outcome of testing one box against the order."""

    box: BoxSpec
    fits: bool
    reason: str
    fill_rate: Optional[float] = None  # items volume / box volume, 0..1


@dataclass
class Recommendation:
    """Full result of a box-selection run."""

    recommended: Optional[BoxSpec]
    total_weight: float
    total_item_volume: float
    total_units: int
    evaluations: list[BoxEvaluation] = field(default_factory=list)
    layout: list[Placement] = field(default_factory=list)  # for the chosen box

    @property
    def found(self) -> bool:
        return self.recommended is not None


def _expand_units(items: list[OrderItem]) -> list[tuple[str, OrderItem]]:
    """Flatten quantities into individual units, keeping a stable label each."""
    units: list[tuple[str, OrderItem]] = []
    for item in items:
        for n in range(item.quantity):
            units.append((f"{item.name}#{n + 1}", item))
    return units


def _necessary_conditions_fail(box: BoxSpec, items: list[OrderItem],
                               total_weight: float,
                               total_volume: float) -> Optional[str]:
    """
    Cheap, always-correct pre-checks run before the (costlier) packer.

    Each check is a *necessary* condition for fitting, so a failure here means
    the box definitely cannot work. This never produces a false rejection; it
    just short-circuits obvious misfits.
    """
    if total_weight > box.max_weight:
        return (
            f"Order weight {total_weight:g} kg exceeds box capacity "
            f"{box.max_weight:g} kg."
        )
    if total_volume > box.volume:
        return (
            f"Combined item volume {total_volume:g} cm3 exceeds box volume "
            f"{box.volume:g} cm3."
        )
    # Every individual item must fit inside the box in *some* orientation.
    box_dims = box.sorted_dims
    for item in items:
        if any(i > b for i, b in zip(item.sorted_dims, box_dims)):
            return (
                f"Item '{item.name}' ({item.length}x{item.width}x{item.height} cm) "
                f"is too large for this box in any orientation."
            )
    return None


def _placement_from_item(packed: Item) -> Placement:
    """Translate a py3dbp packed Item into our Placement record."""
    pos = tuple(float(p) for p in packed.position)
    dims = tuple(float(d) for d in packed.get_dimension())
    rot = int(packed.rotation_type)
    return Placement(
        item=packed.name,
        position=pos,
        dimensions=dims,
        rotation_type=rot,
        rotated=rot != 0,
        orientation=_rotation_description(rot),
    )


def pack_order_into_box(box: BoxSpec,
                        items: list[OrderItem]) -> tuple[bool, list[Placement]]:
    """
    Try to pack the whole order into a single box.

    Returns ``(fits, placements)``. ``placements`` describes where and at what
    orientation each unit sits — mirroring py3dbp's per-item response — and is
    only meaningful when ``fits`` is True.

    Runs the necessary-condition pre-checks first, then defers to py3dbp for the
    real 3D placement. Because packing is heuristic, ``fits=False`` means "the
    packer could not place everything" — conservative by design (we would rather
    suggest a slightly larger box than one that fails on the warehouse floor).
    """
    total_weight = sum(i.weight * i.quantity for i in items)
    total_volume = sum(i.volume * i.quantity for i in items)
    if _necessary_conditions_fail(box, items, total_weight, total_volume):
        return False, []

    packer = Packer()
    bin_ = Bin(box.name, box.length, box.width, box.height, box.max_weight)
    packer.add_bin(bin_)
    for label, item in _expand_units(items):
        packer.add_item(Item(label, item.length, item.width, item.height, item.weight))

    # bigger_first improves placement quality for mixed item sizes.
    packer.pack(bigger_first=True, number_of_decimals=_NUMBER_OF_DECIMALS)

    if bin_.unfitted_items:
        return False, []
    return True, [_placement_from_item(it) for it in bin_.items]


def order_fits_in_box(box: BoxSpec, items: list[OrderItem]) -> bool:
    """Return True if every unit of the order can be packed into a single box."""
    fits, _ = pack_order_into_box(box, items)
    return fits


def recommend_box(items: list[OrderItem], boxes: list[BoxSpec]) -> Recommendation:
    """
    Pick the cheapest box that can hold the entire order.

    Every box is evaluated (so callers can show *why* boxes were rejected), then
    among those that fit we return the one with the lowest cost, breaking ties by
    the smallest volume (tighter pack = less void fill / dunnage).
    """
    if not items:
        raise ValueError("Cannot recommend a box for an empty order.")

    total_weight = sum(i.weight * i.quantity for i in items)
    total_volume = sum(i.volume * i.quantity for i in items)
    total_units = sum(i.quantity for i in items)

    evaluations: list[BoxEvaluation] = []
    # Remember the layout produced for each fitting box so we don't have to
    # re-pack the winner afterwards.
    layouts: dict[str, list[Placement]] = {}
    # Evaluate cheapest-first so the log reads naturally; the final pick is by
    # (cost, volume) regardless of iteration order.
    for box in sorted(boxes, key=lambda b: (b.cost, b.volume)):
        reason = _necessary_conditions_fail(box, items, total_weight, total_volume)
        if reason is not None:
            evaluations.append(BoxEvaluation(box, fits=False, reason=reason))
            continue
        fits, placements = pack_order_into_box(box, items)
        if fits:
            fill = round(total_volume / box.volume, 4) if box.volume else None
            evaluations.append(
                BoxEvaluation(box, fits=True, reason="All items fit.", fill_rate=fill)
            )
            layouts[box.name] = placements
        else:
            evaluations.append(
                BoxEvaluation(
                    box,
                    fits=False,
                    reason="Items could not be arranged to fit inside this box.",
                )
            )

    fitting = [e for e in evaluations if e.fits]
    best = min(fitting, key=lambda e: (e.box.cost, e.box.volume)) if fitting else None

    return Recommendation(
        recommended=best.box if best else None,
        total_weight=round(total_weight, 3),
        total_item_volume=round(total_volume, 3),
        total_units=total_units,
        evaluations=evaluations,
        layout=layouts.get(best.box.name, []) if best else [],
    )
