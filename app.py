"""Match & Meet – MVP server (runs locally and on Vercel).

Local:   python app.py
         http://localhost:8000           customer app
         http://localhost:8000/haendler  garage portal (login with access code)
         http://localhost:8000/admin     developer console (password "admin" locally)
         Without DATABASE_URL a local SQLite file is used.
Vercel:  set DATABASE_URL (Neon Postgres), ADMIN_PASSWORD and SECRET_KEY.

The MVP is deliberately rule-based (no LLM): instant, free, and it never invents car data.
The "advisor" section is where a Swiss-hosted LLM (e.g. Ollama) can plug in later.
"""
import datetime as dt
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import segno
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

BASE = Path(__file__).parent
DATABASE_URL = os.environ.get("DATABASE_URL", "")
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))
ON_VERCEL = bool(os.environ.get("VERCEL"))
# Local defaults only; on Vercel both must be set explicitly or logins stay disabled.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "" if ON_VERCEL else "admin")
SECRET_KEY = os.environ.get("SECRET_KEY", "" if ON_VERCEL else "local-dev-secret")
FEE_CHF = 49
SESSION_HOURS = 12
DEALER_COOKIE, ADMIN_COOKIE = "mm_haendler", "mm_admin"
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
EVENT_TYPES = {"chat_start", "chat_done", "swipe_like", "mission_open"}


# ---------- database (SQLite locally, Postgres online) ----------

@contextmanager
def db():
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        conn = sqlite3.connect(BASE / "matchmeet.db")
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def q(conn, sql, args=()):
    """Run SQL written with '?' placeholders on either database."""
    return conn.execute(sql.replace("?", "%s") if IS_POSTGRES else sql, args)


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS dealers (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, ort TEXT NOT NULL, adresse TEXT NOT NULL,
        distanz_km INTEGER NOT NULL, marken TEXT NOT NULL, code_hash TEXT, aktiv INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS cars (id TEXT PRIMARY KEY, data TEXT NOT NULL, aktiv INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS bookings (
        code TEXT PRIMARY KEY, created TEXT NOT NULL, dealer_id TEXT NOT NULL, car_id TEXT NOT NULL,
        slot TEXT NOT NULL, vorname TEXT NOT NULL, profil_freigabe INTEGER NOT NULL,
        profile_json TEXT NOT NULL, mission_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'gebucht',
        fee_chf INTEGER NOT NULL DEFAULT 0, checked_in TEXT, UNIQUE (dealer_id, slot))""",
    """CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, created TEXT NOT NULL, sid TEXT NOT NULL, typ TEXT NOT NULL)""",
]
_schema_ready = False


def ensure_schema():
    """Create tables and seed sample dealers/cars on first use (works on serverless cold starts)."""
    global _schema_ready
    if _schema_ready:
        return
    with db() as conn:
        for stmt in SCHEMA:
            q(conn, stmt)
        # Seed sync: add new sample dealers/cars and photos, but never overwrite edits made in the admin console.
        for d in json.loads((BASE / "dealers.json").read_text(encoding="utf-8"))["haendler"]:
            q(conn, "INSERT INTO dealers (id, name, ort, adresse, distanz_km, marken) VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT (id) DO NOTHING",
              (d["id"], d["name"], d["ort"], d["adresse"], d["distanz_km"], json.dumps(d["marken"], ensure_ascii=False)))
        existing = {r["id"]: json.loads(r["data"]) for r in q(conn, "SELECT id, data FROM cars").fetchall()}
        for c in json.loads((BASE / "cars.json").read_text(encoding="utf-8"))["modelle"]:
            if c["id"] not in existing:
                q(conn, "INSERT INTO cars (id, data) VALUES (?, ?)", (c["id"], json.dumps(c, ensure_ascii=False)))
            elif c.get("bild_url") and not existing[c["id"]].get("bild_url"):
                photo = {k: c[k] for k in PHOTO_FIELDS if k in c}
                q(conn, "UPDATE cars SET data = ? WHERE id = ?",
                  (json.dumps({**existing[c["id"]], **photo}, ensure_ascii=False), c["id"]))
    _schema_ready = True


def load_cars(conn, only_active=True):
    rows = q(conn, "SELECT id, data, aktiv FROM cars").fetchall()
    return {r["id"]: {**json.loads(r["data"]), "id": r["id"], "aktiv": bool(r["aktiv"])}
            for r in rows if r["aktiv"] or not only_active}


def load_dealers(conn, only_active=True):
    rows = q(conn, "SELECT * FROM dealers ORDER BY distanz_km, name").fetchall()
    return {r["id"]: {"id": r["id"], "name": r["name"], "ort": r["ort"], "adresse": r["adresse"],
                      "distanz_km": r["distanz_km"], "marken": json.loads(r["marken"]),
                      "aktiv": bool(r["aktiv"]), "hat_zugang": r["code_hash"] is not None}
            for r in rows if r["aktiv"] or not only_active}


def public_dealer(d):
    return {k: d[k] for k in ("id", "name", "ort", "adresse", "distanz_km", "marken")}


# ---------- helpers ----------

def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def chf(n):
    return "CHF " + f"{n:,}".replace(",", "’")


def slot_label(slot_id):
    t = dt.datetime.fromisoformat(slot_id)
    return f"{WEEKDAYS[t.weekday()]} {t:%d.%m.} · {t:%H:%M}"


def slots_for(conn, dealer_id):
    booked = {r["slot"] for r in q(conn, "SELECT slot FROM bookings WHERE dealer_id = ?", (dealer_id,)).fetchall()}
    slots, day = [], dt.date.today()
    while len({s["tag"] for s in slots}) < 4:
        day += dt.timedelta(days=1)
        if day.weekday() == 6:
            continue
        times = ["10:00", "13:00"] if day.weekday() == 5 else ["09:00", "11:30", "14:00", "17:00"]
        for time_ in times:
            slot_id = f"{day.isoformat()}T{time_}"
            if slot_id not in booked:
                slots.append({"id": slot_id, "tag": f"{WEEKDAYS[day.weekday()]} {day:%d.%m.}", "zeit": time_})
    return slots


def booking_out(row, cars, dealers):
    car, dealer = cars.get(row["car_id"], {}), dealers.get(row["dealer_id"], {})
    return {
        "code": row["code"], "created": row["created"], "vorname": row["vorname"],
        "status": row["status"], "fee_chf": row["fee_chf"], "checked_in": row["checked_in"],
        "slot": row["slot"], "slot_label": slot_label(row["slot"]),
        "car_id": row["car_id"], "auto": f"{car.get('marke', '')} {car.get('modell', '')}".strip(),
        "dealer_id": row["dealer_id"], "haendler": dealer.get("name", ""), "adresse": dealer.get("adresse", ""),
        "profil_freigabe": bool(row["profil_freigabe"]),
        "profil": json.loads(row["profile_json"]), "mission": json.loads(row["mission_json"]),
    }


def billing(conn, dealer_id=None):
    where, args = ("WHERE dealer_id = ?", (dealer_id,)) if dealer_id else ("", ())
    row = q(conn, "SELECT COUNT(*) AS gebucht, "
                  "COALESCE(SUM(CASE WHEN status = 'qualifiziert' THEN 1 ELSE 0 END), 0) AS qualifiziert, "
                  f"COALESCE(SUM(fee_chf), 0) AS summe FROM bookings {where}", args).fetchone()
    gebucht, qualifiziert = int(row["gebucht"]), int(row["qualifiziert"])
    return {"gebucht": gebucht, "qualifiziert": qualifiziert,
            "checkin_quote": round(100 * qualifiziert / gebucht) if gebucht else 0,
            "summe_chf": int(row["summe"]), "fee_chf": FEE_CHF}


# ---------- auth (access codes for garages, password for the developer) ----------

def require_config():
    if not ADMIN_PASSWORD or not SECRET_KEY:
        raise HTTPException(503, "ADMIN_PASSWORD und SECRET_KEY müssen als Umgebungsvariablen gesetzt sein")


def normalize_code(code):
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def new_code():
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def hash_code(code):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", normalize_code(code).encode(), salt, 100_000)
    return f"{salt.hex()}${digest.hex()}"


def check_code(code, stored):
    salt, _, digest = stored.partition("$")
    candidate = hashlib.pbkdf2_hmac("sha256", normalize_code(code).encode(), bytes.fromhex(salt), 100_000)
    return hmac.compare_digest(candidate.hex(), digest)


def _mac(value):
    return hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def set_session(response, request, cookie, subject):
    value = f"{subject}:{int(time.time()) + SESSION_HOURS * 3600}"
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    # The cookie name is part of the MAC, so a garage cookie can never pass as an admin cookie.
    response.set_cookie(cookie, f"{value}:{_mac(cookie + value)}", max_age=SESSION_HOURS * 3600,
                        httponly=True, samesite="lax", secure=https)


def read_session(request, cookie):
    require_config()
    value, _, mac = request.cookies.get(cookie, "").rpartition(":")
    if not value or not hmac.compare_digest(mac, _mac(cookie + value)):
        return None
    subject, _, expires = value.rpartition(":")
    return subject if expires.isdigit() and int(expires) > time.time() else None


def require_dealer(request: Request):
    dealer_id = read_session(request, DEALER_COOKIE)
    if dealer_id:
        with db() as conn:
            row = q(conn, "SELECT aktiv FROM dealers WHERE id = ?", (dealer_id,)).fetchone()
        if row and row["aktiv"]:
            return dealer_id
    raise HTTPException(401, "Bitte mit Zugangscode einloggen")


def require_admin(request: Request):
    if read_session(request, ADMIN_COOKIE) != "admin":
        raise HTTPException(401, "Bitte als Admin einloggen")


# ---------- advisor (rule-based; LLM seam for later) ----------

TOPICS = [
    {"key": "alltag", "frage": "Hi! 👋 Wofür brauchst du das Auto im Alltag und wie viele Kilometer fährst du an einem normalen Tag?",
     "chips": ["Pendeln, ca. 40 km", "Stadt, unter 20 km", "Viel Autobahn, 100+ km"]},
    {"key": "budget", "frage": "Mit welchem Budget rechnest du ungefähr (Kaufpreis in CHF)?",
     "chips": ["bis 30'000", "30'000–45'000", "45'000–60'000"]},
    {"key": "parken", "frage": "Wo parkst du meistens: enge Tiefgarage, an der Strasse oder auf einem eigenen Platz?",
     "chips": ["Enge Tiefgarage", "An der Strasse", "Eigener Parkplatz"]},
    {"key": "laden", "frage": "Könntest du zuhause oder bei der Arbeit laden?",
     "chips": ["Ja, Wallbox möglich", "Bei der Arbeit", "Nein, keine Lademöglichkeit"]},
    {"key": "platz", "frage": "Wer fährt meistens mit und was muss regelmässig in den Kofferraum?",
     "chips": ["Meist allein", "Partner:in + Sporttasche", "Familie mit Kinderwagen"]},
    {"key": "fragen", "frage": "Letzte Frage: Was ist deine grösste offene Frage oder Sorge beim Autokauf?",
     "chips": ["Reicht die Reichweite im Winter?", "Was kostet mich das Auto im Monat?", "Passt es in meine Garage?"]},
]
BIG_CARGO = r"kinderwagen|hund|velo|bike|ski|sport|familie|kinder|gross|viel"


def parse_chf(text):
    t = text.lower().replace("’", "").replace("'", "").replace(" ", "")
    t = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", t)
    nums = []
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)(k|tsd|tausend)?", t):
        value = float(m.group(1).replace(",", "."))
        nums.append(value * 1000 if m.group(2) else value)
    nums = [n for n in nums if n >= 5000]
    return int(max(nums)) if nums else 0


def parse_km(text):
    t = text.lower()
    m = re.search(r"(\d+)\s*\+?\s*km", t) or re.search(r"(\d+)", t)
    if m:
        return int(m.group(1))
    if "stadt" in t or "kurz" in t:
        return 15
    if "autobahn" in t or "weit" in t:
        return 100
    return 0


def parse_parken(text):
    t = text.lower()
    if re.search(r"tiefgarage|eng|schmal|parkhaus", t):
        return "eng"
    if re.search(r"strasse|straße|blaue zone|quartier", t):
        return "strasse"
    if re.search(r"eigen|garage|carport|einfahrt|platz|hof", t):
        return "eigener_platz"
    return "unklar"


def parse_laden(text):
    t = text.lower()
    if re.search(r"arbeit|büro|job|geschäft|firma", t):
        return "arbeit"
    if re.search(r"\b(nein|kein|keine|nicht)\b", t):
        return "nein"
    if re.search(r"\bja\b|wallbox|zuhause|daheim|garage|steckdose|solar", t):
        return "zuhause"
    return "unklar"


def parse_personen(text):
    t = text.lower()
    m = re.search(r"(\d+)", t)
    if m:
        n = int(m.group(1))
        return n + 2 if "kind" in t else n
    if re.search(r"familie|kinder|kind", t):
        return 4
    if re.search(r"partner|freund|zu zweit|zwei", t):
        return 2
    if re.search(r"allein|solo|nur ich", t):
        return 1
    return 0


def rule_profile(a):
    alltag, budget, parken, laden, platz, fragen = (a.get(k, "") for k in ("alltag", "budget", "parken", "laden", "platz", "fragen"))
    return {
        "nutzung": alltag[:80], "km_pro_tag": parse_km(alltag), "budget_max_chf": parse_chf(budget),
        "parken": parse_parken(parken), "laden": parse_laden(laden), "personen": parse_personen(platz),
        "grosser_kofferraum": bool(re.search(BIG_CARGO, platz.lower())), "gepaeck": platz[:80],
        "offene_fragen": [fragen[:120]] if fragen else [],
    }


def react(key, answer):
    """Short, answer-aware reaction so the guided chat feels like a conversation."""
    if key == "alltag":
        km = parse_km(answer)
        if km >= 100:
            return f"{km} km pro Tag sind eine Ansage, da zählen Reichweite und Komfort."
        return f"{km} km pro Tag schafft heute fast jedes Auto locker." if km else "Danke, das hilft mir weiter."
    if key == "budget":
        budget = parse_chf(answer)
        return f"Bis {chf(budget)} gibt es spannende Optionen." if budget else "Kein Problem, ich zeige dir eine breite Auswahl."
    if key == "parken":
        return {"eng": "Enge Tiefgaragen merke ich mir, da zählt jeder Zentimeter.",
                "strasse": "An der Strasse sind kompakte Autos ein Vorteil.",
                "eigener_platz": "Ein eigener Platz macht vieles einfacher."}.get(parse_parken(answer), "Alles klar.")
    if key == "laden":
        return {"zuhause": "Laden zuhause ist die günstigste Art, elektrisch zu fahren.",
                "arbeit": "Laden bei der Arbeit ist super praktisch.",
                "nein": "Kein Problem, dann schaue ich auch auf Hybride und schnelles Laden unterwegs."}.get(parse_laden(answer), "Verstanden.")
    if key == "platz":
        return "Dann achte ich auf genug Kofferraum." if re.search(BIG_CARGO, answer.lower()) else "Gut zu wissen."
    return "Gute Frage, die kommt in deine Probefahrt-Mission!"


def score_car(car, p, ignore_budget=False):
    score, reasons = 0.0, []
    budget = p.get("budget_max_chf") or 0
    km = p.get("km_pro_tag") or 0
    laden = p.get("laden", "unklar")
    parken = p.get("parken", "unklar")
    personen = p.get("personen") or 1
    gross = bool(p.get("grosser_kofferraum"))
    price = car["preis_chf"]
    elektro = car["antrieb"] == "Elektro"
    plugin = car["antrieb"] == "Plug-in-Hybrid"

    if budget:
        if price <= budget:
            score += 20 + 3 * (budget - price) / budget
            if budget - price >= 5000:
                reasons.append((6, f"{chf(budget - price)} unter deinem Budget"))
        elif price <= budget * 1.1:
            score += 5
            reasons.append((9, "Knapp über Budget: beim Händler nach Angeboten fragen"))
        elif ignore_budget:
            score -= 3 * (price - budget) / 1000
            reasons.append((20, f"{chf(price - budget)} über deinem Budget"))
        else:
            return None

    if km:
        if elektro:
            days = car["reichweite_km"] // km
            if days >= 4:
                score += 15
                reasons.append((10, f"{car['reichweite_km']} km Reichweite: reicht für rund {min(days, 30)} Tage deines Alltags"))
            if km >= 100:
                score += 10 if car["reichweite_km"] >= 500 else (-15 if car["reichweite_km"] < 400 else 0)
        if plugin and km <= car["e_reichweite_km"] and laden != "nein":
            score += 12
            reasons.append((14, f"Deine {km} km pro Tag schaffst du rein elektrisch"))
        if not elektro and not plugin and km >= 100:
            score += 6

    if laden == "zuhause":
        if elektro:
            score += 15
            reasons.append((12, "Über Nacht zuhause laden: die günstigste Art zu fahren"))
        elif plugin:
            score += 8
    elif laden == "arbeit":
        if elektro:
            score += 10
            reasons.append((10, "Laden während der Arbeit, zuhause brauchst du nichts"))
    elif laden == "nein":
        if elektro:
            if car["dc_kw"] >= 130:
                reasons.append((8, f"Schnellladen mit bis zu {car['dc_kw']} kW, ideal ohne eigene Wallbox"))
            else:
                score -= 12
        elif plugin:
            score -= 5
        else:
            score += 15
            reasons.append((12, "Kein Ladeplatz nötig: tanken wie gewohnt"))
    elif elektro:
        score += 3

    length_m, width_m = car["laenge_mm"] / 1000, car["breite_mm"] / 1000
    if parken == "eng":
        if car["breite_mm"] <= 1830 and car["laenge_mm"] <= 4400:
            score += 15
            reasons.append((13, f"Nur {length_m:.2f} m lang und {width_m:.2f} m breit, gut für enge Tiefgaragen"))
        elif car["breite_mm"] > 1860 or car["laenge_mm"] > 4650:
            score -= 12
    elif parken == "strasse" and car["laenge_mm"] <= 4350:
        score += 6
        reasons.append((7, f"Kompakte {length_m:.2f} m: findet auch an der Strasse einen Platz"))

    if personen >= 6:
        if car["sitze"] >= 7:
            score += 30
            reasons.append((16, f"{car['sitze']} Sitze: Platz für die ganze Familie"))
        else:
            score -= 30
    elif personen >= 3 or gross:
        if car["kofferraum_l"] >= 500:
            score += 12
            reasons.append((11, f"{car['kofferraum_l']} l Kofferraum für Kinderwagen, Sportsachen & Co."))
        elif car["kofferraum_l"] < 450:
            score -= 12
        if car["sitze"] < 5:
            score -= 20
        score += car["kofferraum_l"] / 100
    elif car["laenge_mm"] < 4400:
        score += 4

    if elektro:
        score += car["reichweite_km"] / 200
    reasons.append((5, car["highlight"]))
    reasons.sort(key=lambda r: -r[0])
    return score, [text for _, text in reasons[:3]]


def find_matches(profile, cars, dealers, limit=8):
    scored = [(car, *res) for car in cars.values() if (res := score_car(car, profile))]
    if len(scored) < 4:
        scored = [(car, *score_car(car, profile, ignore_budget=True)) for car in cars.values()]
    scored.sort(key=lambda s: -s[1])

    picked, per_brand = [], {}
    for car, score, reasons in scored:
        if per_brand.get(car["marke"], 0) >= 2:
            continue
        per_brand[car["marke"]] = per_brand.get(car["marke"], 0) + 1
        picked.append((car, score, reasons))
        if len(picked) == limit:
            break
    if not picked:
        return []

    hi, lo = picked[0][1], picked[-1][1]
    brands_with_dealer = {m for d in dealers.values() for m in d["marken"]}
    return [{**car, "match_pct": round(62 + 36 * (score - lo) / (hi - lo)) if hi > lo else 90,
             "gruende": reasons, "haendler_verfuegbar": car["marke"] in brands_with_dealer}
            for car, score, reasons in picked]


def rule_mission(p, car):
    name = f"{car['marke']} {car['modell']}"
    km = p.get("km_pro_tag") or 0
    items = []
    if km:
        items.append({"titel": "Fahr ein Stück deines Arbeitswegs",
                      "warum": f"So spürst du, wie sich der {name} bei deinen {km} km pro Tag anfühlt."})
    else:
        items.append({"titel": "Fahr Stadt und Autobahn im Wechsel", "warum": "So lernst du das Auto in beiden Situationen kennen."})
    if p.get("parken") == "eng":
        items.append({"titel": "Park in einer engen Tiefgarage ein",
                      "warum": f"Mit {car['breite_mm'] / 1000:.2f} m Breite willst du wissen, ob es bei dir passt."})
    elif p.get("parken") == "strasse":
        items.append({"titel": "Park rückwärts an der Strasse ein", "warum": "Teste Übersicht und Parkhilfen im Alltag."})
    if car["antrieb"] in ("Elektro", "Plug-in-Hybrid"):
        if p.get("laden") == "nein":
            items.append({"titel": "Such mit dem Berater die nächste Schnellladestation",
                          "warum": "Ohne eigene Lademöglichkeit zählt das Laden unterwegs."})
        else:
            items.append({"titel": "Lass dir das Laden an der Wallbox zeigen",
                          "warum": "Dann weisst du, wie dein Alltag mit Laden aussieht."})
    if p.get("grosser_kofferraum") or (p.get("personen") or 0) >= 3:
        items.append({"titel": "Lade Kinderwagen oder Gepäck ein",
                      "warum": f"{car['kofferraum_l']} l Kofferraum: teste es mit deinen eigenen Sachen."})
    else:
        items.append({"titel": "Setz dich auf die Rückbank", "warum": "So prüfst du Platz und Einstieg für Mitfahrende."})
    for question in (p.get("offene_fragen") or [])[:1]:
        items.append({"titel": f"Frag den Berater: {question[:70]}",
                      "warum": "Deine offene Frage aus dem Chat: hier bekommst du die Antwort."})
    items.append({"titel": "Verbinde dein Handy mit dem Infotainment", "warum": "Navi und Musik sind im Alltag wichtiger, als man denkt."})
    return items[:5]


def rule_tip(p, car):
    """Personal tip that answers the customer's open question with the car's data."""
    name = f"{car['marke']} {car['modell']}"
    question = " ".join(p.get("offene_fragen") or []).lower()
    electric = car["antrieb"] in ("Elektro", "Plug-in-Hybrid")
    km = p.get("km_pro_tag") or 0
    if electric and re.search(r"winter|kälte|kalt|reichweite", question):
        reach = car["e_reichweite_km"] if car["antrieb"] == "Plug-in-Hybrid" else car["reichweite_km"]
        return (f"Im Winter sinkt die Reichweite bei E-Autos spürbar. Die {reach} km des {name} sind der Normwert: "
                "Frag den Berater, ob eine Wärmepumpe verbaut ist und was im Winter realistisch bleibt.")
    if re.search(r"kost|monat|preis|leasing|versicherung", question):
        energy = "Strom" if electric else "Benzin"
        daily = f" für deine {km} km pro Tag" if km else ""
        return (f"Der {name} startet bei {chf(car['preis_chf'])}. Lass dir beim Termin eine Monatsrechnung "
                f"mit Leasing, Versicherung und {energy}{daily} machen.")
    if re.search(r"garage|passt|parkplatz|gross|breit", question):
        return (f"Der {name} ist {car['laenge_mm'] / 1000:.2f} m lang und {car['breite_mm'] / 1000:.2f} m breit (ohne Spiegel). "
                "Miss vorher deinen Parkplatz und fahr bei der Probefahrt in eine enge Tiefgarage.")
    if car["dc_kw"] and re.search(r"lade|laden|wallbox", question):
        return f"Der {name} lädt unterwegs mit bis zu {car['dc_kw']} kW. Frag nach der Ladezeit an einer Wallbox und nach Ladetarifen."
    if p.get("offene_fragen"):
        return f"Nimm deine Frage «{p['offene_fragen'][0][:100]}» mit: Der Berater kann sie dir am {name} direkt zeigen."
    return f"Fahr den {name} so, wie du ihn im Alltag nutzen würdest. So merkst du am schnellsten, ob er passt."


CAR_FIELDS = {"marke": str, "modell": str, "segment": str, "antrieb": str, "preis_chf": int, "reichweite_km": int,
              "e_reichweite_km": int, "kofferraum_l": int, "laenge_mm": int, "breite_mm": int, "sitze": int,
              "dc_kw": int, "highlight": str}
ANTRIEBE = {"Elektro", "Plug-in-Hybrid", "Hybrid", "Mild-Hybrid", "Benzin", "Diesel"}
PHOTO_FIELDS = ("bild_url", "bild_quelle", "bild_link")  # optional; photos need a credit line (CC licenses)


def validate_car(car_id, data):
    if not re.fullmatch(r"[a-z0-9-]{2,60}", car_id):
        raise HTTPException(400, "ID: nur Kleinbuchstaben, Zahlen und Bindestriche")
    wrong = [k for k, t in CAR_FIELDS.items() if not isinstance(data.get(k), t) or isinstance(data.get(k), bool)]
    if wrong:
        raise HTTPException(400, f"Fehlende oder falsche Felder: {', '.join(wrong)}")
    if data["antrieb"] not in ANTRIEBE:
        raise HTTPException(400, f"antrieb muss eines davon sein: {', '.join(sorted(ANTRIEBE))}")
    farbe = data.get("farbe")
    if not (isinstance(farbe, list) and len(farbe) == 2
            and all(isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in farbe)):
        raise HTTPException(400, 'farbe: zwei Hex-Farben, z. B. ["#1c2b2f", "#b8733a"]')
    photo = {}
    for key in PHOTO_FIELDS:
        value = data.get(key)
        if value in (None, ""):
            continue
        if not isinstance(value, str) or (key != "bild_quelle" and not value.startswith("https://")):
            raise HTTPException(400, f"{key}: muss eine https-Adresse sein" if key != "bild_quelle" else "bild_quelle: Text erwartet")
        photo[key] = value[:300]
    return {"id": car_id, **{k: data[k] for k in CAR_FIELDS}, "farbe": farbe, **photo}


# ---------- app ----------

app = FastAPI(title="Match & Meet")


@app.middleware("http")
async def prepare_database(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if ON_VERCEL and not IS_POSTGRES:
            return JSONResponse({"detail": "DATABASE_URL fehlt: Neon-Datenbank im Vercel-Projekt verbinden"}, status_code=503)
        ensure_schema()
    return await call_next(request)


class ChatRequest(BaseModel):
    step: int
    answer: str


class Answer(BaseModel):
    key: str = ""
    frage: str = ""
    antwort: str = ""


class ProfileRequest(BaseModel):
    answers: list[Answer]


class MatchRequest(BaseModel):
    profile: dict


class MissionRequest(BaseModel):
    profile: dict
    car_id: str


class BookingRequest(BaseModel):
    car_id: str
    dealer_id: str
    slot: str
    vorname: str
    consent: bool = False
    profile: dict = {}
    mission: list[dict] = []


class EventRequest(BaseModel):
    typ: str
    sid: str


class CodeRequest(BaseModel):
    code: str


class PasswordRequest(BaseModel):
    password: str


class DealerCreate(BaseModel):
    name: str
    ort: str
    adresse: str = ""
    distanz_km: int = 0
    marken: list[str] = []


class ActiveRequest(BaseModel):
    aktiv: bool


class CarRequest(BaseModel):
    data: dict
    aktiv: bool = True


@app.get("/")
def page_customer():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/haendler")
def page_dealer():
    return FileResponse(BASE / "static" / "haendler.html")


@app.get("/admin")
def page_admin():
    return FileResponse(BASE / "static" / "admin.html")


# --- customer ---

@app.get("/api/topics")
def topics():
    return {"topics": TOPICS}


@app.post("/api/chat")
def chat(req: ChatRequest):
    step = max(0, min(req.step, len(TOPICS) - 1))
    follow = TOPICS[step + 1]["frage"] if step + 1 < len(TOPICS) else "Ich suche jetzt passende Modelle aller Marken für dich. ✨"
    return {"text": f"{react(TOPICS[step]['key'], req.answer[:500])} {follow}"}


@app.post("/api/profile")
def profile(req: ProfileRequest):
    return {"profil": rule_profile({a.key: a.antwort.strip()[:500] for a in req.answers})}


@app.post("/api/matches")
def matches(req: MatchRequest):
    with db() as conn:
        return {"cars": find_matches(req.profile, load_cars(conn), load_dealers(conn))}


@app.post("/api/mission")
def mission(req: MissionRequest):
    with db() as conn:
        car = load_cars(conn).get(req.car_id)
    if not car:
        raise HTTPException(404, "Modell nicht gefunden")
    return {"items": rule_mission(req.profile, car), "tipp": rule_tip(req.profile, car)}


@app.get("/api/dealers")
def dealers(brand: str = ""):
    with db() as conn:
        found = [d for d in load_dealers(conn).values() if not brand or brand in d["marken"]]
        return {"dealers": [{**public_dealer(d), "slots": slots_for(conn, d["id"])} for d in found]}


@app.post("/api/bookings")
def create_booking(req: BookingRequest):
    vorname = req.vorname.strip()[:40]
    with db() as conn:
        car, dealer = load_cars(conn).get(req.car_id), load_dealers(conn).get(req.dealer_id)
        if not car or not dealer or car["marke"] not in dealer["marken"]:
            raise HTTPException(400, "Dieser Händler führt das Modell nicht")
        if not vorname:
            raise HTTPException(400, "Bitte gib deinen Vornamen ein")
        if req.slot not in {s["id"] for s in slots_for(conn, dealer["id"])}:
            raise HTTPException(409, "Dieser Termin ist leider nicht mehr frei")
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        # Profile and mission reach the garage only with the customer's consent.
        q(conn, "INSERT INTO bookings (code, created, dealer_id, car_id, slot, vorname, profil_freigabe, profile_json, mission_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
          (code, now(), dealer["id"], car["id"], req.slot, vorname, int(req.consent),
           json.dumps(req.profile if req.consent else {}, ensure_ascii=False),
           json.dumps(req.mission[:6] if req.consent else [], ensure_ascii=False)))
        row = q(conn, "SELECT * FROM bookings WHERE code = ?", (code,)).fetchone()
        return booking_out(row, {car["id"]: car}, {dealer["id"]: dealer})


@app.get("/api/bookings/{code}/qr.svg")
def booking_qr(code: str, request: Request):
    code = code.strip().upper()
    with db() as conn:
        if not q(conn, "SELECT 1 FROM bookings WHERE code = ?", (code,)).fetchone():
            raise HTTPException(404, "Ticket nicht gefunden")
    buf = io.BytesIO()
    # The QR opens the garage portal with the code prefilled, which simulates the scan.
    segno.make(f"{request.base_url}haendler?code={code}", error="m").save(
        buf, kind="svg", scale=8, border=2, dark="#0b0d12", light="#ffffff")
    return Response(buf.getvalue(), media_type="image/svg+xml")


@app.post("/api/event")
def track_event(req: EventRequest):
    if req.typ not in EVENT_TYPES:
        raise HTTPException(400, "Unbekanntes Ereignis")
    with db() as conn:
        q(conn, "INSERT INTO events (id, created, sid, typ) VALUES (?, ?, ?, ?)", (secrets.token_hex(8), now(), req.sid[:64], req.typ))
    return {"ok": True}


# --- garage ---

@app.post("/api/haendler/login")
def dealer_login(req: CodeRequest, request: Request, response: Response):
    require_config()
    with db() as conn:
        rows = q(conn, "SELECT id, name, code_hash FROM dealers WHERE aktiv = 1 AND code_hash IS NOT NULL").fetchall()
    for r in rows:
        if check_code(req.code, r["code_hash"]):
            set_session(response, request, DEALER_COOKIE, r["id"])
            return {"id": r["id"], "name": r["name"]}
    raise HTTPException(401, "Zugangscode ungültig")


@app.post("/api/haendler/logout")
def dealer_logout(response: Response):
    response.delete_cookie(DEALER_COOKIE)
    return {"ok": True}


@app.get("/api/haendler/me")
def dealer_me(dealer_id: str = Depends(require_dealer)):
    with db() as conn:
        return public_dealer(load_dealers(conn)[dealer_id])


@app.get("/api/haendler/bookings")
def dealer_bookings(dealer_id: str = Depends(require_dealer)):
    with db() as conn:
        cars, dealers_ = load_cars(conn, False), load_dealers(conn, False)
        rows = q(conn, "SELECT * FROM bookings WHERE dealer_id = ? ORDER BY slot", (dealer_id,)).fetchall()
        return {"bookings": [booking_out(r, cars, dealers_) for r in rows], "billing": billing(conn, dealer_id)}


@app.post("/api/haendler/checkin/{code}")
def dealer_checkin(code: str, dealer_id: str = Depends(require_dealer)):
    code = code.strip().upper()
    with db() as conn:
        row = q(conn, "SELECT * FROM bookings WHERE code = ?", (code,)).fetchone()
        if not row:
            raise HTTPException(404, f"Kein Ticket mit Code {code} gefunden")
        if row["dealer_id"] != dealer_id:
            raise HTTPException(403, "Dieses Ticket gehört zu einer anderen Garage")
        already = row["status"] == "qualifiziert"
        if not already:
            q(conn, "UPDATE bookings SET status = 'qualifiziert', fee_chf = ?, checked_in = ? WHERE code = ?", (FEE_CHF, now(), code))
            row = q(conn, "SELECT * FROM bookings WHERE code = ?", (code,)).fetchone()
        return {**booking_out(row, load_cars(conn, False), load_dealers(conn, False)), "bereits": already}


# --- developer ---

@app.post("/api/admin/login")
def admin_login(req: PasswordRequest, request: Request, response: Response):
    require_config()
    if not hmac.compare_digest(req.password.encode(), ADMIN_PASSWORD.encode()):
        raise HTTPException(401, "Passwort falsch")
    set_session(response, request, ADMIN_COOKIE, "admin")
    return {"ok": True}


@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE)
    return {"ok": True}


@app.get("/api/admin/me", dependencies=[Depends(require_admin)])
def admin_me():
    return {"ok": True, "datenbank": "Postgres" if IS_POSTGRES else "SQLite (lokal)"}


@app.get("/api/admin/overview", dependencies=[Depends(require_admin)])
def admin_overview():
    with db() as conn:
        funnel = {r["typ"]: int(r["n"]) for r in q(conn, "SELECT typ, COUNT(DISTINCT sid) AS n FROM events GROUP BY typ").fetchall()}
        names = {d["id"]: d["name"] for d in load_dealers(conn, False).values()}
        rows = q(conn, "SELECT dealer_id, SUBSTR(checked_in, 1, 7) AS monat, COUNT(*) AS fahrten, SUM(fee_chf) AS summe "
                       "FROM bookings WHERE status = 'qualifiziert' GROUP BY dealer_id, SUBSTR(checked_in, 1, 7) "
                       "ORDER BY monat DESC").fetchall()
        return {"funnel": funnel, "total": billing(conn),
                "abrechnung": [{"haendler": names.get(r["dealer_id"], r["dealer_id"]), "monat": r["monat"],
                                "fahrten": int(r["fahrten"]), "summe_chf": int(r["summe"])} for r in rows]}


@app.get("/api/admin/dealers", dependencies=[Depends(require_admin)])
def admin_dealers():
    with db() as conn:
        return {"dealers": list(load_dealers(conn, False).values())}


@app.post("/api/admin/dealers", dependencies=[Depends(require_admin)])
def admin_create_dealer(req: DealerCreate):
    name = req.name.strip()[:80]
    if not name or not req.ort.strip():
        raise HTTPException(400, "Name und Ort sind Pflicht")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "garage"
    dealer_id, code = f"{slug}-{secrets.token_hex(2)}", new_code()
    marken = [m.strip() for m in req.marken if m.strip()][:12]
    with db() as conn:
        q(conn, "INSERT INTO dealers (id, name, ort, adresse, distanz_km, marken, code_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
          (dealer_id, name, req.ort.strip()[:60], req.adresse.strip()[:120], max(0, req.distanz_km),
           json.dumps(marken, ensure_ascii=False), hash_code(code)))
    return {"id": dealer_id, "name": name, "code": code}


@app.post("/api/admin/dealers/{dealer_id}/code", dependencies=[Depends(require_admin)])
def admin_reset_code(dealer_id: str):
    code = new_code()
    with db() as conn:
        if q(conn, "UPDATE dealers SET code_hash = ? WHERE id = ?", (hash_code(code), dealer_id)).rowcount == 0:
            raise HTTPException(404, "Garage nicht gefunden")
    return {"id": dealer_id, "code": code}


@app.post("/api/admin/dealers/{dealer_id}/aktiv", dependencies=[Depends(require_admin)])
def admin_dealer_active(dealer_id: str, req: ActiveRequest):
    with db() as conn:
        if q(conn, "UPDATE dealers SET aktiv = ? WHERE id = ?", (int(req.aktiv), dealer_id)).rowcount == 0:
            raise HTTPException(404, "Garage nicht gefunden")
    return {"ok": True}


@app.get("/api/admin/bookings", dependencies=[Depends(require_admin)])
def admin_bookings():
    with db() as conn:
        cars, dealers_ = load_cars(conn, False), load_dealers(conn, False)
        rows = q(conn, "SELECT * FROM bookings ORDER BY created DESC").fetchall()
        return {"bookings": [booking_out(r, cars, dealers_) for r in rows]}


@app.get("/api/admin/cars", dependencies=[Depends(require_admin)])
def admin_cars():
    with db() as conn:
        return {"cars": sorted(load_cars(conn, False).values(), key=lambda c: (c["marke"], c["modell"]))}


@app.put("/api/admin/cars/{car_id}", dependencies=[Depends(require_admin)])
def admin_save_car(car_id: str, req: CarRequest):
    car = validate_car(car_id, req.data)
    with db() as conn:
        q(conn, "INSERT INTO cars (id, data, aktiv) VALUES (?, ?, ?) "
                "ON CONFLICT (id) DO UPDATE SET data = excluded.data, aktiv = excluded.aktiv",
          (car_id, json.dumps(car, ensure_ascii=False), int(req.aktiv)))
    return {**car, "aktiv": req.aktiv}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"Kunde: http://localhost:{port}  ·  Garage: /haendler  ·  Entwickler: /admin (Passwort lokal: admin)")
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=port)
