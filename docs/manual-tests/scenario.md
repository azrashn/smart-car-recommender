# Manual test: Scenario Lab (T51)

Page: `scenario.html` · API: `POST /api/scenarios`, `POST /api/recommendations`.
Start the app (`python -m uvicorn app.main:app --reload`) and open `http://localhost:8000/survey.html`.

| # | Steps | Expected |
|---|---|---|
| 1 | Open `scenario.html` in a fresh browser tab (no survey done). | "Önce anket yapın" message, controls hidden, redirect to `survey.html` after ~2 s. |
| 2 | Fill and submit the survey, open `scenario.html`. | Controls visible, "ÖNCE" lists the base top 5, "SONRA" lists the same ranking with `=` badges and yearly costs. |
| 3 | Move "Yıllık km" up. | After ~0.15 s the yearly costs and the cost bar chart grow proportionally; the ranking does not change. |
| 4 | Lower "Yakıt ekonomisi" to 1 and raise "Performans" to 3. | Percentages next to the sliders update at once; the ranking and the ▲/▼ badges update after the debounce. |
| 5 | Drag a slider continuously. | Only the last position triggers a visible update (stale responses are ignored). |
| 6 | Click "Sıfırla". | Sliders return to the survey's values and default prices; "SONRA" equals "ÖNCE". |
| 7 | Use a very low budget in the survey, then open the lab. | A warning with the conflict reason and suggestions; the "SONRA" list is empty. |
| 8 | Stop the server and move a slider. | A red error message; the page keeps working after the server returns. |
| 9 | Enter 75 000 km (or 12 345 km) in the survey, open the lab, change only a priority slider. | The km output still shows the survey value exactly; the request carries only the moved slider in `overrides`. |
| 10 | Tab through the page with the keyboard. | Every slider and the reset button is reachable and shows a focus ring; changes are announced in the results region (`aria-live`). |

Known limits: priorities use 1–3 (Düşük/Orta/Yüksek); the engine does not accept 0 ("Hiç") yet.
The km and price sliders change only the yearly cost estimate, not the ranking.
