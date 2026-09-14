# Match & Meet – vom Swipe zur Probefahrt

Study project prototype: young car buyers answer 6 questions, swipe matched models of all brands, get a personal test-drive mission and book at a garage. Garages pay CHF 49 per *qualified* test drive (check-in on site). Business concept: [KONZEPT.md](KONZEPT.md).

| Area | URL | Login |
|---|---|---|
| Customer | `/` | none |
| Garage portal | `/haendler` | access code (created in the developer console) |
| Developer console | `/admin` | `ADMIN_PASSWORD` |

## Run locally
```bash
pip install fastapi uvicorn segno
python app.py
```
Uses a local SQLite file (`matchmeet.db`). Admin password locally: `admin`. Delete `matchmeet.db` to reset.

## Deploy (GitHub + Vercel + Neon)
1. Push this folder to a GitHub repository.
2. Vercel → **Add New Project** → import the repository (framework is detected as FastAPI, entrypoint `app.py`).
3. Vercel project → **Storage** → **Create Database** → **Neon** → connect to the project. This sets `DATABASE_URL`.
4. Vercel project → **Settings → Environment Variables**:
   - `ADMIN_PASSWORD` – your developer password
   - `SECRET_KEY` – random string, e.g. `python -c "import secrets; print(secrets.token_hex(32))"`
5. Redeploy. Tables and sample data are created on the first request.
6. Open `/admin` → **Garagen** → create access codes for the garages.

## Notes
- No LLM in the MVP on purpose (instant, free, no invented car data). The rule-based advisor in `app.py` is the seam for a Swiss-hosted LLM later.
- Car and garage data are samples; edit them in the developer console.
