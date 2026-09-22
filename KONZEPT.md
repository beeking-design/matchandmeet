# Match & Meet – Vom Match zur Probefahrt

> Studienprojekt UFENA1, Gruppe 2 · Arbeitsversion 14.09.2026
> **Alle Finanzzahlen, Marktgrössen und Vertriebsziele sind Planungsannahmen und müssen validiert werden.**

## Die Idee in einem Satz
Junge Autokäufer finden per **Antipp-Quiz** in zwei Minuten passende Modelle **aller Marken**, bekommen einen **persönlichen Probefahrt-Plan** und buchen direkt beim Händler in der Nähe. Der **Händler zahlt nur, wenn der Kunde wirklich zur Probefahrt erscheint**.

## Was macht die Idee besonders?
| Baustein | Was es ist | Warum es zählt |
|---|---|---|
| **Vorschläge mit Begründung** | Direkt nach dem Quiz: Fahrprofil („Team …“) und passende Modelle mit Match-% | Schnell und verständlich, passt zum Namen „Match“. Jede Karte begründet, *warum* das Auto zum Alltag passt. |
| **Probefahrt-Plan** | Aus den Quiz-Antworten entsteht eine persönliche Checkliste: „Fahr in deine Tiefgarage“, „Lade den Kinderwagen ein“, „Frag nach der Ladezeit an deiner Wallbox“ | Aus einer Spazierfahrt wird ein Test, der die *eigenen* Fragen beantwortet. Das gibt eine sichere Entscheidung. |
| **Kurzprofil für den Händler** | Der Berater sieht vorab Bedürfnisse und offene Fragen, nur mit Zustimmung des Kunden | Gespräch auf Augenhöhe statt Standard-Verkaufspitch |
| **Pay-per-Drive** | Abrechnung nur bei bestätigtem Check-in vor Ort | Null Risiko für Händler, damit leichter Markteintritt |
| **Datenschutz-KI** (Ausbaustufe Pilot) | Eigene KI (Open-Source-Modell via Ollama) auf eigener Infrastruktur in der Schweiz | Keine Kundendaten an US-Clouds (nDSG/DSGVO). Die KI erfindet keine Fahrzeugdaten, weil sie nur mit geprüften Daten arbeitet. |

## Customer Journey
1. **Einstieg:** QR-Code im Showroom/auf dem Plakat, TikTok/Instagram-Video („Finde dein nächstes Auto in 2 Minuten“), Link auf der Händler-Website
2. **Antipp-Quiz (≈ 30 Sek.):** 6 Fragen mit grossen Kacheln zu Alltag, Budget (Schieberegler), Parken, Laden, Mitfahrern und dem, was man bei der Probefahrt klären will. Keine Tipparbeit.
3. **Vorschläge:** Fahrprofil und passende Modelle mit „Match-%“, Begründung und Verbrauchsangaben
4. **Probefahrt buchen:** Modell wählen; dazu entsteht ein persönlicher Probefahrt-Plan (Checkliste)
5. **Buchen:** Händler in der Nähe und Termin wählen, Vor- und Nachname eingeben, Zustimmung zum Kurzprofil geben. Dann gibt es ein Ticket mit QR-Code.
6. **Meet:** Der Berater scannt beim Händler den QR-Code. Damit ist die Probefahrt **qualifiziert** und wird abgerechnet.

## MVP (Online-Prototyp)
- **Bewusst ohne KI:** Antipp-Quiz, regelbasiertes Matching, Probefahrt-Plan und Tipp. Antwortet sofort, kostet nichts und erfindet keine Fahrzeugdaten. Tests mit einer lokalen KI (Ollama) brauchten 17–110 Sekunden pro Antwort.
- **Was der MVP beweisen soll:** Buchen junge Kunden über Quiz und Vorschläge? Erscheinen sie? Zahlen Garagen dafür? Die KI ist nicht die riskante Annahme.
- **Drei Bereiche:** Kunden-App, Garagenportal (Login mit Zugangscode, Check-in, Abrechnung), Entwicklerkonsole (Funnel, Abrechnung pro Monat, Garagen und Fahrzeugdaten verwalten)
- **Garage in der Nähe:** Der Kunde gibt bei der Buchung seine PLZ ein und sieht die nächsten Garagen mit Distanz. In der Pilotregion (Kanton Zürich und Aargau Ost) ist jede Marke im Umkreis von 20 km erreichbar (fiktive Beispiel-Garagen).
- **White-Label für Hersteller:** Die Kunden-App läuft als „MATCH/MEET for CUPRA“: nur CUPRA-Modelle (17 Varianten mit Verbrauchs- und CO₂-Angaben), CUPRA-Farben, nur CUPRA-Partner. Dieselbe Plattform kann für jede Marke eingefärbt werden. Mögliches zusätzliches Geschäftsfeld (Planungsannahme): Lizenz pro Marke und Jahr zusätzlich zum Pay-per-Drive der Partner.
- **Technik:** GitHub → Vercel, Datenbank Neon (Postgres)

## Qualifizierte Probefahrt (Abrechnungsauslöser)
Eine Probefahrt wird nur abgerechnet, wenn **alle drei** Punkte erfüllt sind:
1. KI-Profil ausgefüllt (Bedürfnisse und offene Fragen bekannt)
2. Termin über Match & Meet gebucht
3. **Check-in vor Ort** vom Händler per QR-Scan bestätigt

*Schutz vor Missbrauch (später):* Nach der Fahrt bestätigt der Kunde mit einer kurzen Feedback-Frage. Buchungen mit Check-in ohne Kundenbestätigung werden stichprobenartig geprüft.

---

## Business Model Canvas (Rhino) – überarbeitet

### 1. Projektname
**Match & Meet** – Mit KI zum passenden Auto, gemeinsam erleben.

### 2. Projekt-Kurzversion
KI-Plattform für Autohäuser aller Marken. Junge Käufer (25–40) finden per Quiz passende Modelle, erhalten einen persönlichen Probefahrt-Plan und buchen direkt beim Händler. Händler zahlen pro qualifizierter Probefahrt, also nur für Kunden, die wirklich erscheinen.

### 3. Kundensegment
- **Zahlende Kunden:** Autohäuser in der Deutschschweiz (Marken- und Mehrmarkenhändler). Start im Raum Baden/Zürich.
- **Nutzer:** Kaufinteressierte von 25 bis 40 Jahren, digital-native, noch ohne festes Modell, oft vor dem ersten E-Auto oder Hybrid.
- **Early Adopter:** Händler mit Vorführflotte (v. a. E-Autos) und rückläufiger Showroom-Frequenz.

### 4. Probleme (Hypothesen, in Interviews prüfen)
**Kunden**
- Überforderung durch Antriebe, Reichweite, Laden und Preise
- Konfiguratoren sprechen die Sprache der Technik, nicht die des Alltags
- Hemmschwelle Autohaus: Angst vor Verkaufsdruck
- Probefahrten ohne Plan: Die wichtigen Fragen bleiben ungeklärt

**Händler**
- Online-Leads sind teuer, „kalt“ und oft ohne echtes Interesse
- No-Shows bei Probefahrtterminen
- Berater wissen vorher nichts über den Kunden

### 5. Nutzenversprechen
- **Kunden:** verständliche, markenneutrale Empfehlungen in drei Minuten, spielerisch statt Formular. Eine Probefahrt, die *ihre* Alltagsfragen beantwortet, ohne Verkaufsdruck.
- **Händler:** vorbereitete Kunden mit Kurzprofil, die wirklich erscheinen. **Kosten nur bei Erfolg.**

### 6. Lösungsfunktionen
- Antipp-Quiz mit 6 Alltagsfragen (Kacheln und Budget-Regler)
- Vorschläge auf Basis geprüfter Modelldaten mit Begründung pro Modell
- Persönlicher Probefahrt-Plan (Checkliste)
- Terminbuchung mit Ticket und QR-Code
- Händlerportal: Kurzprofil, QR-Check-in, Abrechnungsübersicht
- Eigene KI (Ollama) auf Schweizer Infrastruktur

### 7. Umsatzmodell (Planungsannahmen)
- **CHF 49 pro qualifizierter Probefahrt**, kein Abo, keine Einrichtungsgebühr im Pilot
- Später optional: Premium-Portal (mehrere Standorte, Meet-&-Drive-Events, Auswertungen) für CHF 99/Monat
- Beispiel: 10 Händler × 20 qualifizierte Fahrten/Monat × CHF 49 = **CHF 9'800/Monat**

### 8. Lebensdauerwert (Planungsannahmen)
| | Konservativ | Ziel |
|---|---|---|
| Qualifizierte Fahrten pro Händler/Monat | 8 | 20 |
| Umsatz/Monat | CHF 392 | CHF 980 |
| Direktkosten/Monat (KI-Hosting-Anteil, SMS, Support) | CHF 60 | CHF 80 |
| Deckungsbeitrag/Monat | CHF 332 | CHF 900 |
| Bindung | 24 Monate | 24 Monate |
| **CLV (DB-Basis)** | **≈ CHF 8'000** | **≈ CHF 21'600** |

Vor Akquisitionskosten und Gemeinkosten (CHF 1'500/Monat laut Kursvorgabe).

### 9. Erreichbarer Markt
- Start: Baden/Zürich. **Ziel bis Monat 12: 10 zahlende Händler** → CHF 47'000–118'000 Jahresumsatz (je nach Szenario)
- Danach: Deutschschweiz, Mehrmarken-Garagengruppen
- Marktgrösse (zu prüfen): Anzahl Garagenbetriebe in der Schweiz (AGVS), Neuzulassungen pro Jahr (auto-schweiz)

### 10. Timing – warum jetzt?
- Der Umstieg auf E-Autos erzeugt viel Beratungsbedarf (Reichweite, Laden, Kosten)
- Offene KI-Modelle laufen seit Kurzem gut auf eigener Hardware. Eigene KI ohne US-Cloud ist damit bezahlbar.
- Händler stehen unter Druck (Agenturmodell, Direktvertrieb, weniger Showroom-Besuche) und brauchen echte Frequenz
- Hackathon Barcelona: MVP bauen. Pitch am 23.10.2026.

### 11. Markteintritt
- **B2B:** einen Pilot-Händler in Baden gewinnen. Pay-per-Drive bedeutet kein Risiko und macht die Zusage leicht. Die Ergebnisse als Case Study nutzen, dann Garagengruppen und Verbände ansprechen.
- **B2C:** kurze TikTok/Instagram-Videos („Finde dein nächstes Auto in 2 Minuten“), QR-Codes im Showroom und auf Plakaten, Händler teilen den Link auf Website und Social Media

### 12. Akquisitionskosten (Planungsannahmen)
- **B2B:** CHF 200 Werbung + CHF 300 Vertriebsarbeit pro 2 neuen Händlern → **CAC ≈ CHF 250/Händler**
- **B2C:** Marketingkosten pro qualifizierter Fahrt müssen deutlich unter CHF 49 liegen. **Ziel: ≤ CHF 20.** Das wird im Pilot gemessen.

### 13. Wettbewerber
| Anbieter | Was sie tun | Lücke |
|---|---|---|
| Hersteller-Konfiguratoren (CUPRA, VW, …) | Modell konfigurieren | an eine Marke gebunden, technisch, kein Alltagsbezug |
| AutoScout24, comparis | Inserate und Vergleich | Suche statt Beratung, keine Probefahrt-Vorbereitung |
| Carwow | Angebote von Händlern einholen | Fokus auf Preis, nicht auf Passung und Erlebnis |
| LDB Carla | KI-Service und Terminierung für Händler | Werkzeug des Händlers, nicht markenneutrale Beratung |
| ChatGPT & Co. | allgemeine KI-Beratung | keine geprüften Daten, keine Buchung, Daten in US-Cloud |
| CUPRA City Garage | Events und Probefahrten | eine Marke, nur vor Ort |

### 14. Wettbewerbsvorteil
- **Einzige durchgehende Kette:** Beratung → Match → Probefahrt-Plan → erschienene Probefahrt
- **Erfolgsbasiert:** Händler zahlen nur für Kunden, die kommen
- **Vertrauen:** markenneutral, Platzierungen nicht kaufbar, KI lokal in der Schweiz
- **Lerneffekt:** Mit jeder Fahrt lernen wir, welche Alltagsfragen Kaufentscheidungen auslösen. Diese Daten hat kein Konfigurator.

### 15. Roadmap
- **Vor Barcelona:** 5–10 Kundeninterviews, 2 Händlergespräche, Modelldaten für 15 Autos prüfen
- **Hackathon Barcelona:** MVP fertigstellen (5 Ansichten + Händlerportal), 5 Personen testen lassen, Messwerte erfassen (Dauer, Likes, „Frage geklärt?“)
- **Bis 23.10.2026:** Finanzmodell schärfen, Testergebnisse aufbereiten, 5-Minuten-Pitch mit Live-Demo üben
- **Danach:** Pilot mit einem Händler (echte Buchungen, echter Check-in), Datenfreigaben, Hosting in der Schweiz

### 16. KPIs
- Quiz-Abschlussquote (Start → 6 Antworten)
- Likes pro Sitzung
- Buchungsquote (Match → Termin)
- **Show-up-Quote** (Check-in ÷ Buchungen)
- Fragen geklärt vor und nach der Probefahrt (Kurzumfrage)
- Umsatz pro Händler, CAC, Kündigungsrate

### 17. Das Warum
Wir möchten, dass Menschen ein Auto mit einem guten Gefühl und einer nachvollziehbaren Entscheidung wählen. Persönliche Wünsche sollen vom ersten digitalen Kontakt bis zum echten Fahrerlebnis ernst genommen werden.
**Leitgedanke: verstehen, gemeinsam erleben, selbst entscheiden.**

### 18. Fehlende Ressourcen
- Ein verbindlicher Pilot-Händler mit Vorführwagen und Ansprechperson
- Geprüfte Modell- und Preisdaten (später per Schnittstelle), Zugang zu Terminen und Fahrzeugverfügbarkeit
- Hosting in der Schweiz für die KI (Server mit GPU) und Datenschutzkonzept
- Testpersonen und Startbudget. Entwicklung und Integration zusätzlich kalkulieren.
- Nachweis von Zahlungsbereitschaft und Show-up-Quote

---

## Risiken und Antworten
| Risiko / kritische Frage | Unsere Antwort |
|---|---|
| „Händler zahlen, ist die Empfehlung dann neutral?“ | Das Ranking basiert nur auf Passung zum Profil und ist nicht kaufbar. Händler zahlen für den Termin, nicht für die Platzierung. |
| „Die KI erfindet falsche Daten“ | Modelldaten kommen nur aus der geprüften Datenbank. Die KI formuliert, rechnet aber nicht mit erfundenen Werten. |
| Händler bestätigen Check-ins nicht, um Gebühren zu sparen | Der Kunde bestätigt die Fahrt ebenfalls per Feedback. Abweichungen werden sichtbar. |
| Zu wenig Händler, um alle Marken abzudecken | Matches ohne Händler in der Nähe werden gekennzeichnet. Das Gebiet wird gezielt aufgebaut, zuerst dicht in einer Region. |
| Datenschutz | Nur Vor- und Nachname und Profil, Weitergabe nur mit Zustimmung, KI auf eigener Infrastruktur |

## Pitch-Gerüst (5 Minuten)
1. **Hook (30 s):** „Wer von euch hat schon mal eine Probefahrt gemacht und danach genauso wenig gewusst wie vorher?“
2. **Problem (45 s):** Kunden sind überfordert, Händler bekommen kalte Leads und No-Shows.
3. **Lösung und Live-Demo (2 Min.):** Quiz → Vorschläge → Buchung → Ticket → Händler scannt → CHF 49 erscheinen im Portal
4. **Geschäftsmodell (45 s):** Pay-per-qualified-Drive, Szenario 10 Händler, CLV und CAC
5. **Warum wir, warum jetzt (30 s):** eigene KI ohne Cloud, E-Auto-Umbruch, Testergebnisse aus Barcelona
6. **Ask (30 s):** Pilot-Händler, geprüfte Modelldaten, Startbudget

## Interviewfragen zur Validierung
**Kunden:** Wie hast du dein letztes Auto ausgewählt? Was war vor der Probefahrt unklar? Hättest du eine Checkliste genutzt? Würdest du dein Profil mit dem Händler teilen?
**Händler:** Was kostet euch heute ein Online-Lead? Wie hoch ist eure No-Show-Quote? Was wäre euch eine erschienene, vorbereitete Probefahrt wert?
