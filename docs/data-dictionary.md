# Vehicle Data Dictionary (`data/vehicles.csv`)

> **Module:** M1 — Vehicle Data & Catalogue (`app/catalog/`, `app/db/`, `data/`)  
> **Owner:** @Belisozcelik  
> **Related tasks:** T02 (this document), T03/T08 (catalogue data), T04 (seed and validation)  
> **Schema in code:** `app/schemas/vehicle.py` (`Vehicle`, `VEHICLE_CSV_COLUMNS`)

`data/vehicles.csv` is the single source of the vehicle catalogue. One row is one
vehicle **variant** (model + engine + trim). The seed script (T04) loads it into SQLite;
every module reads vehicles through the `Vehicle` schema, never straight from the CSV.

Changing a column name, unit or allowed value is a **schema change**: it needs a PR that
updates this document, `app/schemas/vehicle.py` and `tests/fixtures/sample_vehicles.csv`
together, approved by the M1 owner and the owners of affected modules.

---

## 1. File format

| Rule | Value |
| --- | --- |
| Encoding | UTF-8 (no BOM) |
| Separator | comma `,` |
| Decimal separator | dot `.` (`5.2`, never `5,2`) |
| Thousands separator | none (`1500000`, never `1.500.000` or `1,500,000`) |
| Dates | ISO 8601, `YYYY-MM-DD` |
| Header | first row, exactly the 19 columns below, in this order |
| Missing value | empty cell. Never `0`, `-`, `N/A`, `null` or an estimate |
| Quoting | only when a value contains a comma; avoid commas in values |
| Row order | ascending `id` |
| Line endings | LF (`\n`) |

### Column order (copy this header exactly)

```csv
id,brand,model,variant,year,body_type,fuel_type,transmission,consumption_l_100km,consumption_kwh_100km,range_km,power_hp,seats,trunk_l,euro_ncap_stars,price_try,price_checked_at,spec_source_url,price_source_url
```

---

## 2. Columns

**Req.** = required (the row is rejected if empty). Optional cells may be empty when the
official source does not publish the value (NFR-04: missing data is not guessed).

| # | Column | Type | Unit | Req. | Allowed values / range | Description |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `id` | integer | – | Yes | ≥ 1, unique | Stable catalogue ID. Never change or reuse an ID; other modules and URLs refer to it (`/api/vehicles/3`, `/api/compare?ids=1,3`). |
| 2 | `brand` | text | – | Yes | 1–50 chars | Brand as written on the official site: `Toyota`, `Volkswagen`. |
| 3 | `model` | text | – | Yes | 1–50 chars | Model name: `Corolla`, `Golf`. |
| 4 | `variant` | text | – | Yes | 1–100 chars | Engine + trim as on the price list: `1.8 Hybrid Dream`. |
| 5 | `year` | integer | year | Yes | 2000–2100 | Model year of the price list used. |
| 6 | `body_type` | enum | – | Yes | `hatchback`, `sedan`, `suv`, `wagon`, `mpv` | Body style. See [§3](#3-allowed-values). |
| 7 | `fuel_type` | enum | – | Yes | `petrol`, `diesel`, `hybrid`, `electric` | Energy source. See [§3](#3-allowed-values). |
| 8 | `transmission` | enum | – | Yes | `manual`, `automatic` | Gearbox. See [§3](#3-allowed-values). |
| 9 | `consumption_l_100km` | decimal | L/100 km | No* | > 0 and ≤ 30 | WLTP combined fuel consumption. **Empty for `electric`.** |
| 10 | `consumption_kwh_100km` | decimal | kWh/100 km | No* | > 0 and ≤ 50 | WLTP combined energy consumption. **Only for `electric`.** |
| 11 | `range_km` | integer | km | No | > 0 and ≤ 1500 | WLTP combined electric range. **Only for `electric`.** |
| 12 | `power_hp` | integer | PS | No | > 0 and ≤ 2000 | Maximum power in PS (metric horsepower). For hybrids: total system power. |
| 13 | `seats` | integer | seats | Yes | 2–9 | Number of seats including the driver. |
| 14 | `trunk_l` | integer | litres | No | > 0 and ≤ 3000 | Boot volume (VDA) with all rear seats up. |
| 15 | `euro_ncap_stars` | integer | stars | No | 0–5 | Latest Euro NCAP rating of the model. Empty if never tested. |
| 16 | `price_try` | integer | TRY | Yes | > 0 | Example list price (turnkey, taxes included) from the official price list. Shown as "example price". |
| 17 | `price_checked_at` | date | – | Yes | `YYYY-MM-DD` | Date you read the price on the source page. |
| 18 | `spec_source_url` | URL | – | Yes | starts with `http://` or `https://` | Official page for the technical values. |
| 19 | `price_source_url` | URL | – | Yes | starts with `http://` or `https://` | Official page for the price. May equal `spec_source_url`. |

\* Not enforced by the schema, but always fill the one that matches `fuel_type`:
without it the vehicle gets no fuel-economy score (M3) and no annual cost (M5).

### Rules across columns

| Rule | Reason |
| --- | --- |
| `fuel_type = electric` → `consumption_l_100km` must be empty | An EV has no litres-per-100-km value. |
| `fuel_type ≠ electric` → `consumption_kwh_100km` and `range_km` must be empty | Only EVs are costed by kWh and have an electric range. |
| `id` values are unique | Duplicate IDs break the catalogue and comparison links. |

These rules are enforced by `app/schemas/vehicle.py`; the T04 seed script rejects a CSV
that breaks any of them and prints the row number and the reason.

---

## 3. Allowed values

The enum values are shared with `app/schemas/preference.py` (`FuelType`, `BodyType`,
`transmission`) and `app/engine/filters.py`. Use exactly these lowercase English words.

### `fuel_type`

| Value | Use for |
| --- | --- |
| `petrol` | Petrol (benzin) engines, including turbo petrol. |
| `diesel` | Diesel (dizel) engines. |
| `hybrid` | Full hybrids (HEV) and mild hybrids (MHEV) that cannot be charged from a socket. |
| `electric` | Battery electric vehicles (BEV). |

Plug-in hybrids (PHEV), LPG and CNG are **out of MVP scope**. Adding them means a new
enum value, so it needs a schema-change PR first.

### `transmission`

| Value | Use for |
| --- | --- |
| `manual` | Manual gearbox (düz vites). |
| `automatic` | Any gearbox without a clutch pedal: torque-converter, DCT/DSG/EDC, CVT, e-CVT and single-speed EV gearboxes. |

### `body_type`

| Value | Use for |
| --- | --- |
| `hatchback` | Hatchbacks, including compact and city cars. |
| `sedan` | Sedans (notchback with a separate boot). |
| `suv` | SUVs and crossovers. |
| `wagon` | Station wagons (estate, SW, Variant, Sports Tourer). |
| `mpv` | MPVs and leisure activity vehicles with up to 9 seats. |

When the manufacturer's label is unclear, use the category it is listed under on the
manufacturer's Turkish website.

---

## 4. Collecting values

1. Open the model page on the manufacturer's **official Turkish website**. Do not use
   dealers, classifieds or review sites as the source.
2. Pick one variant from the current price list and copy its values. If a value is not
   published, leave the cell empty.
3. For Euro NCAP use <https://www.euroncap.com>. That URL does not need its own column;
   list it in `data/SOURCES.md` (T03).
4. Write today's date into `price_checked_at`.
5. Use the next free `id` (last `id` + 1).

---

## 5. Example rows

```csv
id,brand,model,variant,year,body_type,fuel_type,transmission,consumption_l_100km,consumption_kwh_100km,range_km,power_hp,seats,trunk_l,euro_ncap_stars,price_try,price_checked_at,spec_source_url,price_source_url
1,ExampleBrand,ExampleModel,1.0 TSI Comfort,2025,hatchback,petrol,automatic,5.2,,,110,5,380,5,1500000,2026-11-17,https://example.com/specs,https://example.com/prices
2,ExampleBrand,ExampleEV,Long Range,2025,suv,electric,automatic,,16.2,480,204,5,520,,2400000,2026-11-17,https://example.com/ev-specs,https://example.com/ev-prices
```

- Row 1 (combustion): litres per 100 km is filled; the two EV columns are empty.
- Row 2 (electric): kWh per 100 km and range are filled; litres is empty. `euro_ncap_stars`
  is empty because the model was "not tested", not because it scored 0.

The values are illustrative. `data/vehicles.csv` starts with row 1 only as a format
example; **T03 replaces it with the first 10 real vehicles.**

---

## 6. Who uses which column

| Column(s) | Used by |
| --- | --- |
| `id`, `brand`, `model`, `variant`, `year` | M1 catalogue page, M3 results, M5 comparison |
| `body_type`, `fuel_type`, `transmission`, `seats`, `price_try` | M3 hard filters (T21) |
| `consumption_l_100km`, `consumption_kwh_100km` | M3 fuel-economy score (T22), M5 annual cost (T40), M6 Scenario Lab |
| `trunk_l`, `seats` | M3 interior-space score |
| `power_hp` | M3 performance score |
| `price_try` | M3 budget-fit score, M6 break-even km (T53) |
| `euro_ncap_stars` | M3 safety score (skipped when empty) |
| `range_km` | M1 catalogue and M5 comparison display only |
| `price_checked_at`, `spec_source_url`, `price_source_url` | M1 catalogue page: "example price, checked on …" and source links (FR-02, NFR-04) |

---

## 7. Adding vehicles (data tasks T08, T18, T28, T38, T47, T57)

```bash
git checkout main && git pull
git checkout -b data/T18-add-5-vehicles
# add 5 rows at the end of data/vehicles.csv, next free ids
python -m pytest tests/test_vehicle_csv.py
git add data/vehicles.csv
git commit -m "data(catalog): add 5 SUV variants with spec sources" -m "Refs #<issue>"
git push -u origin data/T18-add-5-vehicles
```

Open the PR and request a review from @Belisozcelik (M1 validates every data PR).
Checklist for the reviewer:

- [ ] Header unchanged, values in the right columns
- [ ] Every row has `spec_source_url`, `price_source_url` and `price_checked_at`
- [ ] Source links open an official manufacturer page
- [ ] Enum values are from [§3](#3-allowed-values); no thousands separators in prices
- [ ] No duplicate vehicle (same brand, model and variant)
