# AutoMatch — Smart Car Recommender

[Türkçe](README.md) | **English**

> An AI-assisted, explainable and scenario-based vehicle recommendation and decision support web platform.
> SENG 461 term project.

![CI](https://github.com/azrashn/smart-car-recommender/actions/workflows/ci.yml/badge.svg)

---

## Contents

1. [Purpose](#purpose)
2. [Scope](#scope)
3. [Features](#features)
4. [Architecture](#architecture)
5. [Tech stack](#tech-stack)
6. [Installation](#installation)
7. [Usage](#usage)
8. [API](#api)
9. [Testing](#testing)
10. [Data sources](#data-sources)
11. [Project structure](#project-structure)
12. [Development process](#development-process)
13. [Team](#team)
14. [License](#license)

---

## Purpose

Buying a car means weighing budget, fuel consumption, usage, space and safety at the same time. AutoMatch collects the user's needs through a questionnaire or free text, then **scores and explains** matching vehicles. It also shows **how the ranking changes** when annual mileage or priorities change.

<!-- TODO (T19): 2-3 sentence problem statement and target users -->

## Scope

**In scope:**

- A catalog of 40 vehicle variants, each with a source link and check date
- Preference input via questionnaire and free text (TR/EN)
- Rule-based filtering and weighted scoring (0–100)
- Recommendation explanations and explanations of conflicting preferences
- Side-by-side comparison of 2–3 vehicles with annual fuel/energy cost
- Scenario Lab: instant re-ranking when mileage, fuel price or priorities change

**Deliberately out of scope:** user accounts, live listing scraping, used-car price prediction, maintenance/insurance costs, vehicle photos, deployment.

## Features

<!-- TODO: each module owner adds 1-2 sentences and a screenshot -->

| Feature | Description | Screenshot |
| --- | --- | --- |
| Vehicle catalog | <!-- M1 --> | |
| Needs analysis | <!-- M2 --> | |
| Recommendation engine | Hard constraint filtering (budget, transmission, fuel type, seats, body type), 0–100 weighted scoring, strengths/weaknesses detection, and constraint relaxation suggestions. `app/engine/filters.py` is a pure Python module with no database dependency. | |
| AI explanations | <!-- M4 --> | |
| Comparison and cost | <!-- M5 --> | |
| Scenario Lab | <!-- M6 --> | |

## Architecture

A single FastAPI app serves both the JSON API and static pages. Filtering, scoring and cost calculation are deterministic Python functions. The LLM only extracts preferences from text and explains computed results; **the system works fully with AI turned off.**

```
Browser (HTML/CSS/JS) ──HTTP──▶ FastAPI
                                  ├── catalog   (M1) ──▶ SQLite ◀── data/vehicles.csv
                                  ├── preferences (M2)
                                  ├── engine    (M3)
                                  ├── ai        (M4) ──▶ Gemini API (optional)
                                  ├── cost / compare (M5)
                                  └── scenarios (M6)
```

Details: [docs/architecture.md](docs/architecture.md)

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| Database | SQLite, SQLAlchemy 2 |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| AI | Google Gemini API (optional), rule-based fallback |
| Testing and quality | pytest, pytest-cov, ruff, GitHub Actions |

## Installation

**Requirements:** Python 3.11+ and Git.

```bash
git clone https://github.com/azrashn/smart-car-recommender.git
cd smart-car-recommender

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env

python -m app.db.seed       # data/vehicles.csv → automatch.db
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000> — API docs: <http://127.0.0.1:8000/docs>

### Enabling AI (optional)

1. Get an API key from [Google AI Studio](https://aistudio.google.com/).
2. Set the following in `.env`:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
```

With `AI_PROVIDER=none` (default), rule-based and template fallbacks are used.

## Usage

<!-- TODO (T17): step-by-step usage with screenshots. Full guide: docs/user-guide.md -->

1. **Home:** choose "Start questionnaire" or "Describe your needs".
2. **Questionnaire / text:** enter your budget, usage and priorities. Example: *"Mostly city driving, automatic, fuel efficient, budget 1.5 million TRY."*
3. **Results:** the top 5 vehicles with score, strengths, weaknesses and an explanation.
4. **Compare:** select up to 3 vehicles and compare them side by side.
5. **Scenario Lab:** change annual mileage, fuel price and priorities and watch the ranking update.

## API

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/vehicles` | Vehicle list and filters |
| GET | `/api/vehicles/{id}` | Vehicle detail |
| POST | `/api/preferences/form` | Preferences from questionnaire |
| POST | `/api/preferences/text` | Preferences from free text |
| POST | `/api/recommendations` | Recommendations or conflict report |
| GET | `/api/compare?ids=1,2,3` | Comparison |
| POST | `/api/scenarios` | Scenario-based re-ranking |

Contract: [docs/api-contract.md](docs/api-contract.md)

## Testing

```bash
pip install -r requirements-dev.txt
pytest --cov=app
ruff check .
```

### Cost tests

The annual energy cost (`app/cost/calculator.py`) is computed as
`annual_cost = annual_km / 100 * consumption_per_100km * unit_price`
(L/100 km and TRY/L for combustion and hybrid vehicles, kWh/100 km and TRY/kWh for electric).
The tests live in `tests/test_cost.py`. They check the documented example (12,000 km,
5.2 L/100 km, 50 TRY/L → 31,200 TRY) and a real catalogue row (Corolla 1.8 Hybrid Dream).
Edge cases covered:

- 0, 1, 100 and 10,000,000 km; zero price
- missing or wrong-unit consumption → `None`, never estimated (NFR-04)
- negative, `nan` and `inf` inputs, zero consumption → `ValueError`
- unsupported or upper-case `fuel_type` → `ValueError`
- determinism, linearity in km, no rounding, inputs left unchanged

```bash
pytest tests/test_cost.py -v
pytest --cov=app/cost --cov-report=term-missing --cov-fail-under=70
```

<!-- TODO (T56): test summary, link to docs/test-report.md and ablation result (T37) -->

## Data sources

Vehicle specifications were collected from manufacturers' official websites. Each row has a source link and a check date. **Prices are examples and may be outdated.** List: [data/SOURCES.md](data/SOURCES.md)

Columns, units and allowed values: [docs/data-dictionary.md](docs/data-dictionary.md)

## Project structure

```
app/        application code (one folder per module)
data/       vehicle data (CSV) and source list
docs/       architecture, API, algorithm, testing and user docs
scripts/    helper scripts (ablation experiment)
tests/      pytest tests and fixtures
```

## Development process

- Tasks: [GitHub Issues](https://github.com/azrashn/smart-car-recommender/issues) and the [Projects board](https://github.com/azrashn/smart-car-recommender/projects)
- Branch and commit rules: [CONTRIBUTING.md](CONTRIBUTING.md)
- Releases: [Releases](https://github.com/azrashn/smart-car-recommender/releases)

## Team

| Member | GitHub | Module | Responsibility |
| --- | --- | --- | --- |
| Belis Özçelik | [@Belisozcelik](https://github.com/Belisozcelik) | M1 | Vehicle data and catalog |
| (full name) | [@fatihoguzkaya](https://github.com/fatihoguzkaya) | M2 | Preference input and i18n |
| (full name) | [@karya-karya](https://github.com/karya-karya) | M3 | Recommendation engine |
| Orhan Çardak | [@orhancardak](https://github.com/orhancardak) | M4 | AI layer |
| Sude Karakoç | [@SudeKarakoc1](https://github.com/SudeKarakoc1) | M5 | Comparison, cost and results UI |
| Esma Azra Şahin | [@azrashn](https://github.com/azrashn) | M6 | Scenario Lab, testing and CI |

## License

<!-- Team decision: MIT or "educational use only" -->
This project was developed for educational purposes as part of the SENG 461 course.
