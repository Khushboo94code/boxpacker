# Test Run Output

Command:

```bash
python manage.py test -v 2
```

Environment: Python 3.14, Django 6.1, djangorestframework 3.18.0, py3dbp 1.1.2.

```
Found 21 test(s).
Operations to perform:
  Synchronize unmigrated apps: messages, rest_framework, staticfiles
  Apply all migrations: admin, auth, contenttypes, selection, sessions
Running migrations:

test_empty_order_raises (selection.tests.PackingLogicTests.test_empty_order_raises) ... ok
test_evaluations_explain_each_box (selection.tests.PackingLogicTests.test_evaluations_explain_each_box) ... ok
test_invalid_item_dimensions_raise (selection.tests.PackingLogicTests.test_invalid_item_dimensions_raise) ... ok
test_layout_reports_position_and_orientation (selection.tests.PackingLogicTests.test_layout_reports_position_and_orientation)
The packer's per-item placement (position + rotation) is surfaced. ... ok
test_multiple_items_need_larger_box (selection.tests.PackingLogicTests.test_multiple_items_need_larger_box)
Several items whose combined footprint exceeds the small box. ... ok
test_no_box_fits_returns_not_found (selection.tests.PackingLogicTests.test_no_box_fits_returns_not_found) ... ok
test_no_fit_has_empty_layout (selection.tests.PackingLogicTests.test_no_fit_has_empty_layout) ... ok
test_poster_tube_does_not_fit_small_box (selection.tests.PackingLogicTests.test_poster_tube_does_not_fit_small_box)
The headline edge case: a long item must be rejected by a short box ... ok
test_poster_tube_fits_tube_box (selection.tests.PackingLogicTests.test_poster_tube_fits_tube_box) ... ok
test_quantity_is_respected (selection.tests.PackingLogicTests.test_quantity_is_respected)
One book fits Small; twelve books should not. ... ok
test_recommendation_includes_layout_for_chosen_box (selection.tests.PackingLogicTests.test_recommendation_includes_layout_for_chosen_box) ... ok
test_recommendation_prefers_cheapest_fitting_box (selection.tests.PackingLogicTests.test_recommendation_prefers_cheapest_fitting_box) ... ok
test_single_small_item_uses_small_box (selection.tests.PackingLogicTests.test_single_small_item_uses_small_box) ... ok
test_weight_capacity_is_enforced (selection.tests.PackingLogicTests.test_weight_capacity_is_enforced)
An item that fits geometrically but is too heavy must be rejected. ... ok
test_boxes_endpoint_lists_catalog (selection.tests.RecommendApiTests.test_boxes_endpoint_lists_catalog) ... ok
test_empty_items_rejected_with_400 (selection.tests.RecommendApiTests.test_empty_items_rejected_with_400) ... ok
test_negative_dimension_rejected_with_400 (selection.tests.RecommendApiTests.test_negative_dimension_rejected_with_400) ... ok
test_oversized_order_reports_no_fit (selection.tests.RecommendApiTests.test_oversized_order_reports_no_fit) ... ok
test_recommend_endpoint_handles_poster_edge_case (selection.tests.RecommendApiTests.test_recommend_endpoint_handles_poster_edge_case) ... ok
test_recommend_endpoint_returns_cheapest_box (selection.tests.RecommendApiTests.test_recommend_endpoint_returns_cheapest_box) ... ok
test_recommend_response_includes_layout (selection.tests.RecommendApiTests.test_recommend_response_includes_layout) ... ok

----------------------------------------------------------------------
Ran 21 tests in 0.014s

OK
System check identified no issues (0 silenced).
```

## Manual end-to-end checks (dev server)

```
POST /api/recommend/  { Poster 45x6x6, 0.4kg }        -> found: Poster Tube  (£1.80)   ✅ short box rejected
POST /api/recommend/  { 2x Book + 1x Mug }            -> found: Medium Box               ✅
POST /api/recommend/  { Wardrobe 200x100x90 }         -> found: false, "no box fits"     ✅
GET  /api/products/                                    -> 8 products                       ✅
GET  /                                                 -> 200 (frontend page)              ✅
```
