/* Scenario Lab (T51): sliders -> POST /api/scenarios (debounced) -> before/after ranking + cost chart.
 *
 * - Defaults for km and prices come from the API (a call with empty overrides), so the
 *   numbers live in one place (app/scenarios/service.py).
 * - Only controls the user actually moved are sent as overrides; the survey's own values
 *   are never silently rounded or replaced.
 * - All API data is written with textContent (never innerHTML). */
(function () {
  "use strict";

  const STORAGE_KEY_PREFERENCE = "automatch.preference";
  const DEBOUNCE_MS = 150; // keeps "slider change -> updated list" under the 300 ms criterion
  const WEIGHT = { low: 1, medium: 2, high: 3 };
  const LEVEL = { 1: "low", 2: "medium", 3: "high" };
  const LEVEL_TR = { 1: "Düşük", 2: "Orta", 3: "Yüksek" };
  const CRITERIA = [
    ["fuel_economy", "Yakıt ekonomisi"],
    ["interior_space", "İç hacim"],
    ["performance", "Performans"],
    ["budget_fit", "Fiyat avantajı"],
    ["safety", "Güvenlik"],
  ];

  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });
  const money = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });

  let preference = null;
  let baseWeights = {};
  let base = null; // { annual_km, fuel_price_try, electricity_price_try } as returned by the API
  let touched = { annual_km: false, fuel_price_try: false, electricity_price_try: false, priorities: new Set() };
  let timer = null;
  let controller = null;
  let requestSeq = 0;

  function showAlert(message, kind) {
    const box = $("scenarioAlert");
    box.className = "alert-box alert-" + (kind || "warning");
    box.textContent = message;
    box.hidden = false;
  }
  function hideAlert() { $("scenarioAlert").hidden = true; }

  function readPreference() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY_PREFERENCE);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  // ---- Controls -----------------------------------------------------------
  function weightsOf(pref) {
    const out = {};
    CRITERIA.forEach(([key]) => {
      const v = pref && pref.priorities && pref.priorities[key];
      out[key] = WEIGHT[v] || 2;
    });
    return out;
  }

  function buildPrioritySliders() {
    const host = $("prioritySliders");
    host.textContent = "";
    CRITERIA.forEach(([key, label]) => {
      const row = document.createElement("div");
      row.className = "slider-row";

      const lab = document.createElement("label");
      lab.className = "form-label";
      lab.htmlFor = "prio_" + key;
      lab.textContent = label;

      const input = document.createElement("input");
      input.type = "range";
      input.id = "prio_" + key;
      input.min = "1";
      input.max = "3";
      input.step = "1";
      input.dataset.key = key;
      input.value = String(baseWeights[key]);
      input.addEventListener("input", function () {
        touched.priorities.add(key);
        onChange();
      });

      const out = document.createElement("output");
      out.id = "prio_out_" + key;
      out.htmlFor = input.id;

      row.append(lab, input, out);
      host.appendChild(row);
    });
  }

  function currentWeights() {
    const w = {};
    CRITERIA.forEach(([key]) => { w[key] = Number($("prio_" + key).value); });
    return w;
  }

  // Shown value: the survey's exact value until the user moves the slider.
  function shownKm() { return touched.annual_km ? Number($("annualKm").value) : base.annual_km; }

  function setOutput(id, text) {
    $(id).textContent = text;
    const input = $(id.replace(/Out$/, ""));
    if (input) input.setAttribute("aria-valuetext", text);
  }

  function updateOutputs() {
    setOutput("annualKmOut", money.format(shownKm()) + " km");
    setOutput("fuelPriceOut", nf.format(touched.fuel_price_try ? Number($("fuelPrice").value) : base.fuel_price_try) + " TL/L");
    setOutput("electricityPriceOut", nf.format(touched.electricity_price_try ? Number($("electricityPrice").value) : base.electricity_price_try) + " TL/kWh");
    const w = currentWeights();
    const total = Object.values(w).reduce((a, b) => a + b, 0);
    CRITERIA.forEach(([key]) => {
      const pct = total ? (w[key] / total) * 100 : 0;
      const text = LEVEL_TR[w[key]] + " (" + w[key] + ") · %" + nf.format(pct);
      $("prio_out_" + key).textContent = text;
      $("prio_" + key).setAttribute("aria-valuetext", text);
    });
  }

  function resetControls() {
    touched = { annual_km: false, fuel_price_try: false, electricity_price_try: false, priorities: new Set() };
    $("annualKm").value = String(base.annual_km);
    $("fuelPrice").value = String(base.fuel_price_try);
    $("electricityPrice").value = String(base.electricity_price_try);
    CRITERIA.forEach(([key]) => { $("prio_" + key).value = String(baseWeights[key]); });
    updateOutputs();
  }

  // ---- API ----------------------------------------------------------------
  function buildOverrides() {
    const o = {};
    if (touched.annual_km) o.annual_km = Number($("annualKm").value);
    if (touched.fuel_price_try) o.fuel_price_try = Number($("fuelPrice").value);
    if (touched.electricity_price_try) o.electricity_price_try = Number($("electricityPrice").value);
    if (touched.priorities.size) {
      o.priorities = {};
      touched.priorities.forEach((key) => { o.priorities[key] = LEVEL[Number($("prio_" + key).value)]; });
    }
    return o;
  }

  async function postJson(url, body, signal) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: signal,
    });
    if (!res.ok) {
      const err = new Error("HTTP " + res.status);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  // ---- Rendering ----------------------------------------------------------
  function badge(item) {
    const b = document.createElement("span");
    b.className = "badge";
    if (item.rank_change === null || item.rank_change === undefined) {
      b.classList.add("badge-new");
      b.textContent = "yeni";
    } else if (item.rank_change > 0) {
      b.classList.add("badge-up");
      b.textContent = "▲ " + item.rank_change;
      b.setAttribute("aria-label", item.rank_change + " sıra yükseldi");
    } else if (item.rank_change < 0) {
      b.classList.add("badge-down");
      b.textContent = "▼ " + Math.abs(item.rank_change);
      b.setAttribute("aria-label", Math.abs(item.rank_change) + " sıra düştü");
    } else {
      b.classList.add("badge-same");
      b.textContent = "=";
      b.setAttribute("aria-label", "sıra değişmedi");
    }
    return b;
  }

  function renderList(listEl, items, withBadge) {
    listEl.textContent = "";
    if (!items || !items.length) {
      const li = document.createElement("li");
      li.className = "rank-empty";
      li.textContent = "Gösterilecek araç yok.";
      listEl.appendChild(li);
      return;
    }
    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "rank-item";

      const no = document.createElement("span");
      no.className = "rank-no";
      no.textContent = item.rank + ".";

      const name = document.createElement("span");
      name.className = "rank-name";
      name.textContent = item.brand + " " + item.model;
      const meta = document.createElement("span");
      meta.className = "rank-meta";
      const parts = [item.variant, "skor " + nf.format(item.score)];
      if (typeof item.estimated_annual_cost_try === "number") {
        parts.push("≈ " + money.format(item.estimated_annual_cost_try) + " TL/yıl");
      }
      meta.textContent = parts.join(" · ");
      name.appendChild(meta);

      li.append(no, name);
      if (withBadge) li.appendChild(badge(item));
      listEl.appendChild(li);
    });
  }

  function renderChart(items) {
    const host = $("costChart");
    host.textContent = "";
    const costs = (items || []).map((i) => (typeof i.estimated_annual_cost_try === "number" ? i.estimated_annual_cost_try : 0));
    const max = Math.max.apply(null, costs.concat([1]));
    (items || []).forEach((item, idx) => {
      const row = document.createElement("div");
      row.className = "cost-row";
      const name = document.createElement("span");
      name.className = "cost-name";
      name.textContent = item.rank + ". " + item.brand + " " + item.model;
      const track = document.createElement("div");
      track.className = "cost-track";
      const bar = document.createElement("div");
      bar.className = "cost-bar";
      bar.style.width = (costs[idx] / max) * 100 + "%";
      track.appendChild(bar);
      const value = document.createElement("span");
      value.className = "cost-value";
      value.textContent = costs[idx] ? money.format(costs[idx]) + " TL" : "tüketim verisi yok";
      row.append(name, track, value);
      host.appendChild(row);
    });
    $("costChartCard").hidden = !(items && items.length);
  }

  function renderConflict(report) {
    renderList($("afterList"), [], false);
    renderChart([]);
    const msgs = (report.suggestions || []).map((s) => s.message).filter(Boolean);
    showAlert([report.reason].concat(msgs).filter(Boolean).join(" "), "warning");
  }

  function renderAfter(data) {
    hideAlert();
    if (data.status === "conflict") {
      renderConflict(data);
    } else {
      renderList($("afterList"), data.recommendations, true);
      renderChart(data.recommendations);
    }
  }

  // ---- Flow ---------------------------------------------------------------
  async function runScenario() {
    if (controller) controller.abort();
    controller = new AbortController();
    const seq = ++requestSeq;
    $("resultsRegion").setAttribute("aria-busy", "true");
    $("status").textContent = "Hesaplanıyor…";
    try {
      const data = await postJson("/api/scenarios", { preference: preference, overrides: buildOverrides() }, controller.signal);
      if (seq !== requestSeq) return; // a newer request superseded this one
      renderAfter(data);
      $("status").textContent = "";
    } catch (err) {
      if (err.name === "AbortError" || seq !== requestSeq) return;
      $("status").textContent = "";
      if (err.status === 422) {
        showAlert("Tercihleriniz doğrulanamadı. Lütfen anketi yeniden doldurun.", "danger");
      } else {
        showAlert("Senaryo servisine ulaşılamadı (" + err.message + "). Daha sonra tekrar deneyin.", "danger");
      }
    } finally {
      if (seq === requestSeq) $("resultsRegion").setAttribute("aria-busy", "false");
    }
  }

  function onChange() {
    updateOutputs();
    clearTimeout(timer);
    timer = setTimeout(runScenario, DEBOUNCE_MS);
  }

  async function init() {
    preference = readPreference();
    if (!preference) {
      showAlert("Önce anket yapın. Anket sayfasına yönlendiriliyorsunuz…", "warning");
      setTimeout(function () { window.location.href = "survey.html"; }, 1800);
      return;
    }
    baseWeights = weightsOf(preference);

    // One call with empty overrides gives the "before" list AND the default km/prices.
    let first;
    try {
      first = await postJson("/api/scenarios", { preference: preference, overrides: {} });
    } catch (err) {
      showAlert(
        err.status === 422
          ? "Tercihleriniz doğrulanamadı. Lütfen anketi yeniden doldurun."
          : "Senaryo servisine ulaşılamadı (" + err.message + "). Daha sonra tekrar deneyin.",
        "danger"
      );
      return;
    }

    if (first.status === "conflict") {
      // No vehicle matches the survey answers, so there is nothing to re-rank.
      // Defaults are not available in this response; show the reasons and stop.
      renderConflict(first);
      return;
    }
    base = {
      annual_km: first.annual_km_used,
      fuel_price_try: first.fuel_price_try_used,
      electricity_price_try: first.electricity_price_try_used,
    };
    renderList($("beforeList"), first.recommendations, false);

    buildPrioritySliders();
    $("annualKm").addEventListener("input", function () { touched.annual_km = true; onChange(); });
    $("fuelPrice").addEventListener("input", function () { touched.fuel_price_try = true; onChange(); });
    $("electricityPrice").addEventListener("input", function () { touched.electricity_price_try = true; onChange(); });
    $("btnReset").addEventListener("click", function () {
      resetControls();
      clearTimeout(timer);
      runScenario();
    });
    $("scenarioApp").hidden = false;
    resetControls();
    renderAfter(first);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
