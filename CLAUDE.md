# Match & Meet

Study project (UFENA1, group 2): brand-neutral platform that turns young car buyers' daily-life needs into matched models, a personal test-drive "mission" and a booked test drive. Garages pay per *qualified* test drive (check-in on site). Business concept: `KONZEPT.md` (German). Deploy steps: `README.md`.

## Run
```bash
python app.py
```
Customer http://localhost:8000 · Garage http://localhost:8000/haendler · Developer http://localhost:8000/admin (local password `admin`). On Windows: `start.bat`.

## Files
| File | Purpose |
|---|---|
| `app.py` | FastAPI app: DB layer, auth, rule-based advisor (`QUIZ` config → `build_profile`, matching, mission, tip), all APIs |
| `static/index.html` | Customer app (start → tap quiz → swipe → matches → mission → booking → ticket) |
| `static/haendler.html` | Garage portal: access-code login, KPIs, check-in, bookings with customer briefing |
| `static/admin.html` | Developer console: funnel, billing per garage/month, garages + access codes, bookings, car data |
| `cars.json`, `dealers.json` | Seed data, copied into the DB on first start |
| `plz.json` | Postcodes of the pilot region (canton Zurich + eastern Aargau) with coordinates; other PLZ are looked up live via api3.geo.admin.ch (`lookup_plz`) |

## Architecture
- Hosting target: Vercel (Python/FastAPI) + Neon Postgres via `DATABASE_URL`. Without it: local SQLite `matchmeet.db`.
- SQL is written with `?` placeholders; `q()` converts them for Postgres. Keep SQL portable (no SQLite-only functions, no autoincrement).
- Schema is created lazily per process (`ensure_schema`) so serverless cold starts work.
- Auth: HMAC-signed cookies (`SECRET_KEY`); garages log in with access codes (PBKDF2 hashes), developer with `ADMIN_PASSWORD`. On Vercel both env vars are required.
- No LLM on purpose: CPU tests with Ollama took 17–110 s per call. The advisor functions are the seam for a hosted LLM later.

## Notes
- User-facing strings in German (Swiss spelling, "ss" instead of "ß"); code and comments in English
- No CDN; the only external assets are car photos hotlinked from Wikimedia Commons (`bild_url`) with a mandatory credit (`bild_quelle`, `bild_link`). The SVG silhouette is the fallback.
- Seed data syncs on start: new ids from `cars.json`/`dealers.json` are inserted, photos are added to cars without one; admin edits are never overwritten.
- Fee per qualified test drive: `FEE_CHF` in `app.py`
- White-label: `WHITELABEL_MARKE` (default `CUPRA`, empty = all brands) limits the customer app (`customer_cars`) to one brand; `find_matches` then diversifies by `familie`. Theme, logo lockup ("MATCH/MEET for CUPRA") and texts in `static/index.html` are CUPRA-styled. Garage portal and admin stay multi-brand.
- CUPRA studio images in `static/assets/cupra/` (served at `/assets`) are © CUPRA, used for the study project with a visible disclaimer on the start page. Consumption/CO₂ fields (`leistung`, `verbrauch`, `co2`, `co2_klasse`) come from the maker's WLTP data and are shown on every card.
- Seed cars with a higher `rev` than the stored car replace it completely (use to push data updates; overrides admin edits).
- Customers enter their PLZ at booking; dealers are sorted by crow-flies distance (`RADIUS_KM` = 20). Sample garages in `dealers.json` are placed so every brand is within 20 km of every town in `plz.json` (three brand groups per location).
