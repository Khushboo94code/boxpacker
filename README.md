# 📦 AI-Assisted Box Selection System

A small Django application that recommends the **cheapest shipping box that
physically fits an entire order**, using real **3D bin packing** (via
[`py3dbp`](https://pypi.org/project/py3dbp/)) instead of naive
`L × W × H` volume math.

## Why 3D bin packing (and not volume)?

Comparing volumes answers *"is there enough space?"* but not *"does it actually
fit?"*. A **30 cm poster tube** has a tiny volume, yet it cannot go into a 20 cm
box in any orientation. Volume math would happily — and wrongly — recommend the
small box.

This system places every item in 3D space, trying all six orientations, so
geometry that can't fit is rejected. Weight capacity is enforced too, so a small
but heavy item won't be dropped into a flimsy box.

```
Poster 45×6×6 cm (1 620 cm³)  vs  Small Mailer 20×15×10 cm (3 000 cm³)
Volume says:      fits ✅  (1 620 < 3 000)   ← WRONG
Bin packing says: no fit ❌ (45 cm > 20 cm)  ← CORRECT → recommends Poster Tube
```

## Architecture

```
box-selector/
├── boxpacker/            # Django project (settings, urls, wsgi/asgi)
├── selection/            # the app
│   ├── packing.py        # ★ pure box-selection algorithm (no Django imports)
│   ├── models.py         # Box + Product catalogues
│   ├── serializers.py    # DRF request/response validation
│   ├── views.py          # /api/recommend/, /api/boxes/, /api/products/, page
│   ├── urls.py
│   ├── admin.py          # catalogues editable at /admin
│   ├── tests.py          # 17 tests (algorithm + API)
│   ├── fixtures/initial_data.json   # 5 boxes + 8 products
│   ├── management/commands/seed_boxes.py  # idempotent catalogue seeding
│   └── templates/selection/index.html   # lightweight vanilla-JS frontend
├── manage.py
├── requirements.txt
├── railway.json / Procfile / .python-version   # Railway deployment
├── README.md / AI_USAGE.md / TEST_OUTPUT.md
```

The **algorithm lives in `selection/packing.py`** and imports nothing from
Django, so the core logic is unit-testable in isolation and reusable outside the
web layer.

### How selection works

1. Compute the order's total weight and total item volume.
2. For each **active** box, run cheap *necessary-condition* pre-checks
   (weight ≤ capacity, item volume ≤ box volume, and every single item must fit
   the box in some orientation). These never cause a false rejection — they just
   skip obvious misfits before the costlier packer runs.
3. For boxes that survive, run the **3D packer** (`py3dbp`) with all units and
   confirm every unit is placed.
4. Among boxes that fit, pick the **lowest cost**, breaking ties by the
   **smallest volume** (tighter pack = less void fill).
5. Every box is reported with a `fits`/`reason`, so the UI can explain *why*
   boxes were rejected.

> **Conservative by design:** bin packing is heuristic. If the packer can't
> place everything, we treat the box as "no fit". We'd rather suggest a slightly
> larger box than one that fails on the warehouse floor.

## Units

| Quantity   | Unit |
|------------|------|
| Dimensions | centimetres (cm) |
| Weight     | kilograms (kg)   |
| Cost       | one currency (compared numerically; smaller = cheaper) |

## Setup & run

Requires **Python 3.11+** (developed on 3.14).

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up the database and seed the box/product catalogue
python manage.py migrate
python manage.py loaddata initial_data

# 4. (optional) create an admin user to edit catalogues at /admin
python manage.py createsuperuser

# 5. Run
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** for the frontend.

## Deploying to Railway

This repo is Railway-ready. The build is auto-detected (Nixpacks); on each
deploy it runs `collectstatic → migrate → seed_boxes → gunicorn` via
[`railway.json`](railway.json) (a `Procfile` is included too for portability).

**Steps:**

1. Push this repo to GitHub.
2. On [Railway](https://railway.app): **New Project → Deploy from GitHub repo**,
   pick this repo.
3. **Add a database:** in the project, **New → Database → PostgreSQL**. Railway
   injects a `DATABASE_URL` variable that the app picks up automatically.
   > Railway's container filesystem is **ephemeral**, so SQLite would reset on
   > every deploy/restart. Use Postgres in production. Without a database plugin
   > the app still boots on SQLite, but data won't persist.
4. **Set variables** on the web service (Variables tab):
   | Variable | Value |
   |----------|-------|
   | `DJANGO_SECRET_KEY` | a long random string |
   | `DJANGO_DEBUG` | `0` (already the default on Railway) |
5. **Generate a domain:** Settings → Networking → **Generate Domain**. The app
   reads Railway's `RAILWAY_PUBLIC_DOMAIN` automatically, so it's added to
   `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` with no extra config.
6. Deploy. The start command migrates the DB and seeds the catalogue on first
   boot (`seed_boxes` is idempotent — it won't overwrite boxes you edit in
   `/admin`).

**What makes it production-ready** (see `boxpacker/settings.py`):

- **gunicorn** WSGI server (not the dev server).
- **WhiteNoise** serves static files (admin + DRF UI) with compressed, hashed
  assets — no separate CDN needed.
- **`dj-database-url`** reads `DATABASE_URL` (Postgres on Railway, SQLite
  locally).
- Secrets and `DEBUG` come from the environment; HTTPS/HSTS, secure cookies and
  the proxy SSL header switch on automatically when `DEBUG` is off.

To create an admin user on Railway, open the service shell (`railway run` or the
web terminal) and run `python manage.py createsuperuser`.

## Running tests

```bash
python manage.py test
```

See [`TEST_OUTPUT.md`](TEST_OUTPUT.md) for a captured run (17 tests, all passing).

## API

### `POST /api/recommend/`

Request:

```json
{
  "items": [
    {"name": "Poster", "length": 45, "width": 6, "height": 6, "weight": 0.4, "quantity": 1}
  ]
}
```

Response:

```json
{
  "found": true,
  "recommended_box": {
    "id": 4, "name": "Poster Tube",
    "inner_length": 80, "inner_width": 12, "inner_height": 12,
    "max_weight": 3, "cost": 1.8
  },
  "order_summary": {
    "total_units": 1, "total_weight_kg": 0.4, "total_item_volume_cm3": 1620.0
  },
  "evaluations": [
    {"box": "Small Mailer", "cost": 0.5, "fits": false, "fill_rate": null,
     "reason": "Item 'Poster' (45x6x6 cm) is too large for this box in any orientation."},
    {"box": "Poster Tube", "cost": 1.8, "fits": true, "fill_rate": 0.1406, "reason": "All items fit."}
  ],
  "layout": [
    {
      "item": "Poster#1",
      "position": {"x": 0.0, "y": 0.0, "z": 0.0},
      "dimensions": {"length": 45.0, "width": 6.0, "height": 6.0},
      "rotation_type": 0,
      "rotated": false,
      "orientation": "As entered — original height runs vertically."
    }
  ]
}
```

If no box can hold the order, `found` is `false`, `recommended_box` is `null`,
`layout` is empty, and a human-readable `detail` explains the situation.

### Packing layout (angles / orientation)

`layout` reports, for the **chosen** box, exactly what `py3dbp`'s packer decides
for each unit:

| Field | Meaning |
|-------|---------|
| `item` | Unit label (quantities are expanded, e.g. `Book#1`, `Book#2`) |
| `position` | Lower-corner `(x, y, z)` in cm, measured from a box corner |
| `dimensions` | The item's extents **after rotation**, along the box's length / width / height |
| `rotation_type` | py3dbp's rotation code `0–5` (which of the 6 orientations was used) |
| `rotated` | `false` when the item is kept exactly as entered (`rotation_type == 0`) |
| `orientation` | Plain-English description, e.g. *"Rotated so the original height runs vertically."* |

This is what lets the warehouse see **at which angle** each item should be laid —
e.g. a book placed flat vs. stood on its edge — rather than just "it fits".

Try it from the command line:

```bash
curl -X POST http://127.0.0.1:8000/api/recommend/ \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"name":"Poster","length":45,"width":6,"height":6,"weight":0.4}]}'
```

### `GET /api/boxes/` — active box catalogue

### `GET /api/products/` — product catalogue (used to auto-fill order lines)

## Design decisions & trade-offs

- **Single box per order.** The task is to recommend *a* box for the order, so
  we look for one box that holds everything. Splitting an order across multiple
  boxes is a natural extension (noted below), not implemented here.
- **Boxes/products in the DB, order items in the request.** The box catalogue is
  the durable business data (seeded via fixtures, editable in `/admin`). Orders
  are transient input; the frontend can auto-fill lines from the product
  catalogue but also accepts ad-hoc items.
- **Pure algorithm module.** `packing.py` has zero Django imports, which keeps
  the core logic fast to test and easy to reason about.
- **Necessary-condition pre-filter.** Avoids invoking the packer for boxes that
  provably can't work, while never rejecting a box that could fit.

## Possible extensions

- Split large orders across multiple boxes (multi-bin packing).
- Account for packaging/void-fill margins and fragile-item rules.
- Cache/pre-compute for high request volume; expose packing as an async task.
- Add product weight/dimension sourcing from a real catalogue service.

## Tech stack

Django 6.1 · Django REST Framework 3.18 · py3dbp 1.1.2 · gunicorn · WhiteNoise ·
PostgreSQL (Railway) / SQLite (local) · vanilla JS frontend (no build step).
