# AI Usage

> **⚠️ Please review and edit this file in your own words before submitting.**
> It is a factual draft of how AI was used to build this project. Confirm every
> line matches your own recollection, adjust anything that doesn't, and add your
> own observations. The reviewer wants *your* honest account — not a generated
> one.

## Which AI tool(s) I used

- **Claude Code** (Anthropic, Claude Opus) — used to scaffold the Django
  project, write the packing algorithm, models, DRF API, frontend, tests, and
  documentation.

## The prompts I gave

- Asked it to build a production-ready Django "Box Selection API" that returns
  the cheapest box fitting an entire order, using **3D bin packing (`py3dbp`)**
  rather than naive `L × W × H` volume math, to avoid real-world edge cases
  (e.g. a 30 cm poster tube being wrongly recommended for a 20 cm box).
- Asked for a lightweight frontend for input plus a Django backend for the
  calculation/selection.
- Answered follow-up design questions: chose **DRF + a template frontend**, and
  **editable line-items with an optional product-catalogue dropdown**.

## What I accepted

- The **`py3dbp`-based packing core** in `selection/packing.py`, kept free of
  Django imports so it is unit-testable in isolation.
- The **necessary-condition pre-filter** (weight, volume, per-item longest-
  dimension) that short-circuits obvious misfits before running the packer.
- **Cheapest-then-smallest-volume** tie-breaking for box selection.
- The **Box / Product models**, DRF serializers with validation, the
  `/api/recommend/`, `/api/boxes/`, `/api/products/` endpoints, admin
  registration, and seed fixtures.
- The **vanilla-JS single-page frontend** (no build step) and the test suite
  covering the poster-tube edge case, weight limits, quantities, per-item
  packing layout, and the API.
- The **per-item packing layout** in the response (position + rotation +
  orientation), surfacing what `py3dbp` decides for each unit.
- **Railway deployment setup**: gunicorn, WhiteNoise, `dj-database-url`
  (Postgres via `DATABASE_URL`, SQLite locally), env-driven secrets/`DEBUG`,
  auto-trusting Railway's domain, `railway.json`/`Procfile`, and an idempotent
  `seed_boxes` command. Verified `python manage.py check --deploy` is clean.

## What I rejected or modified

- **Float `min_value` on serializer/model fields** produced a DRF
  `UserWarning: min_value should be an integer or Decimal instance`. Replaced
  the serializer float bounds with an explicit `validate()` method and switched
  the model validator to `Decimal("0.001")` so the run is warning-free.
- **A redundant second migration** was generated when the model validator
  changed. Collapsed the migrations back into a single clean `0001_initial`.

## Mistakes the AI made (and how they were caught)

- Initially used `FloatField(min_value=...)` / `MinValueValidator(0.001)` with
  floats, which DRF warns about. Caught by running `python manage.py test -v 2`
  and reading the warning in the output; fixed as above.
- Generated an extra migration on a model tweak; caught by inspecting the
  `makemigrations` output and squashed.

## How I verified the final code

1. Installed dependencies in a fresh virtualenv and confirmed `py3dbp` imports
   on Python 3.14.
2. Directly probed `py3dbp` to confirm the intended geometry: a 30 cm item is
   **rejected** by a 20 cm box but **accepted** by a 35 cm box, and weight
   overflow is rejected.
3. Ran the full test suite: **17 tests, all passing, no warnings**
   (see `TEST_OUTPUT.md`).
4. Started the dev server and exercised the endpoints with `curl`:
   - Poster (45×6×6) → **Poster Tube** (the short/cheap box is correctly skipped).
   - 2 books + 1 mug → **Medium Box**.
   - Oversized item → `found: false` with an explanatory `detail`.
   - `GET /api/products/` returns the seeded catalogue; `GET /` serves the page.
