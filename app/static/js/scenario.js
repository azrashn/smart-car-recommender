/* Scenario Lab (T51): sliders -> POST /api/scenarios (debounced) -> before/after ranking.
 * All API data is written with textContent (never innerHTML). */
(function () {
  "use strict";

  const STORAGE_KEY_PREFERENCE = "automatch.preference";
  const DEBOUNCE_MS = 300;
  const DEFAULTS = { annual_km: 15000, fuel_price_try: 71.2, electricity_price_try: 8.5 };
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
      input.addEventListener("input", onChange);

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

  function updateOutputs() {
    $("annualKmOut").textContent = money.format(Number($("annualKm").value)) + " km";
    $("fuelPriceOut").textContent = nf.format(Number($("fuelPrice").value)) + " TL/L";
    $("electricityPriceOut").textContent = nf.format(Number($("electricityPrice").value)) + " TL/kWh";
    const w = currentWeights();
    const total = Object.values(w).reduce((a, b) => a + b, 0);
    CRITERIA.forEach(([key]) => {
      const pct = total ? (w[key] / total) * 100 : 0;
      $("prio_out_" + key).textContent = LEVEL_TR[w[key]] + " (" + w[key] + ") · %" + nf.format(pct);
    });
  }

  function setDefaults() {
    $("annualKm").value = String(preference.annual_km || DEFAULTS.annual_km);
    $("fuelPrice").value = String(DEFAULTS.fuel_price_try);
    $("electricityPrice").value = String(DEFAULTS.electricity_price_try);
    CRITERIA.forEach(([key]) => { $("prio_" + key).value = String(baseWeights[key]); });
    updateOutputs();
  }

  // ---- API ----------------------------------------------------------------
  function buildOverrides() {
    const priorities = {};
    const w = currentWeights();
    CRITERIA.forEach(([key]) => { priorities[key] = LEVEL[w[key]]; });
    return {
      annual_km: Number($("annualKm").value),
      fuel_price_try: Number($("fuelPrice").value),
      electricity_price_try: Number($("electricityPrice").value),
      priorities: priorities,
    };
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

  function renderConflict(report) {
    renderList($("afterList"), [], false);
    const msgs = (report.suggestions || []).map((s) => s.message).filter(Boolean);
    showAlert([report.reason].concat(msgs).filter(Boolean).join(" "), "warning");
  }

  // ---- Flow ---------------------------------------------------------------
  async function runScenario() {
    if (controller) controller.abort();
    controller = new AbortController();
    const seq = ++requestSeq;
    $("resultsRegion").setAttribute("aria-busy", "true");
    $("status").textContent = "Hesaplanıyor…";
    try {
      const data = await postJson(
        "/api/scenarios",
        { preference: preference, overrides: buildOverrides() },
        controller.signal
      );
      if (seq !== requestSeq) return; // a newer request superseded this one
      hideAlert();
      if (data.status === "conflict") {
        renderConflict(data);
      } else {
        renderList($("afterList"), data.recommendations, true);
      }
      $("status").textContent = "";
    } catch (err) {
      if (err.name === "AbortError") return;
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

  async function loadBefore() {
    try {
      const data = await postJson("/api/recommendations", preference);
      if (data.status === "success") {
        renderList($("beforeList"), data.recommendations, false);
        return;
      }
    } catch (e) { /* fall through */ }
    $("beforeCard").hidden = true; // "after" still works without the baseline column
  }

  function init() {
    preference = readPreference();
    if (!preference) {
      showAlert("Önce anket yapın. Anket sayfasına yönlendiriliyorsunuz…", "warning");
      setTimeout(function () { window.location.href = "survey.html"; }, 1800);
      return;
    }
    baseWeights = weightsOf(preference);
    buildPrioritySliders();
    ["annualKm", "fuelPrice", "electricityPrice"].forEach((id) => $(id).addEventListener("input", onChange));
    $("btnReset").addEventListener("click", function () {
      setDefaults();
      clearTimeout(timer);
      runScenario();
    });
    $("scenarioApp").hidden = false;
    setDefaults();
    loadBefore();
    runScenario();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
