/* AutoMatch - Results page (T44): POST /api/recommendations, render success or conflict.
 * API text only via textContent; missing values show "veri yok", never 0.
 * TODO(T15): i18n.js replaces the Turkish fallbacks through data-i18n. */
(function () {
  "use strict";

  var API_RECOMMENDATIONS = "/api/recommendations";
  var STORAGE_KEY_PREFERENCE = "automatch.preference";
  var COMPARE_MIN = 2;
  var COMPARE_MAX = 3;
  var HINT = ["results.compareHint", "Karşılaştırmak için 2 veya 3 araç seçin."];
  var LIMIT = ["results.compareMax", "En fazla 3 araç seçebilirsiniz."];
  var BREAKDOWN = [
    ["fuel_economy", "results.breakdown.fuelEconomy", "Yakıt ekonomisi"],
    ["interior_space", "results.breakdown.interiorSpace", "İç hacim"],
    ["performance", "results.breakdown.performance", "Performans"],
    ["budget_fit", "results.breakdown.budgetFit", "Fiyat avantajı"],
    ["safety", "results.breakdown.safety", "Güvenlik"]
  ];
  var views = {};

  function byId(id) { return document.getElementById(id); }
  function isNumber(value) { return typeof value === "number" && isFinite(value); }
  function hasText(value) { return typeof value === "string" && value.trim() !== ""; }

  function formatNumber(value, digits) {
    var lang = (document.documentElement.lang || "tr").slice(0, 2).toLowerCase();
    return value.toLocaleString(lang === "en" ? "en-US" : "tr-TR", { maximumFractionDigits: digits || 0 });
  }

  function el(tag, className, text, i18nKey) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (i18nKey) node.setAttribute("data-i18n", i18nKey);
    return node;
  }

  function noData() { return el("span", "result-no-data", "veri yok", "results.noData"); }

  function readPreference() {
    var parsed = null;
    try { parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY_PREFERENCE)); } catch (e) { return null; }
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  }

  async function getRecommendations(preference) {
    var response = await fetch(API_RECOMMENDATIONS, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(preference)
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }

  function showView(name) {
    Object.keys(views).forEach(function (key) { views[key].hidden = key !== name; });
  }

  function labelRow(i18nKey, fallback, valueNode, labelId) {
    var row = el("p", "result-row");
    var label = el("span", "result-label", fallback, i18nKey);
    if (labelId) label.id = labelId;
    row.append(label, " ", valueNode);
    return row;
  }

  function scoreBar(score, labelId) {
    var bar = el("div", "score-bar");
    var fill = el("div", "score-bar-fill");
    var attrs = { role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100",
      "aria-valuenow": String(score), "aria-labelledby": labelId };
    Object.keys(attrs).forEach(function (name) { bar.setAttribute(name, attrs[name]); });
    fill.style.width = Math.max(0, Math.min(100, score)) + "%";
    bar.appendChild(fill);
    return bar;
  }

  function breakdownList(breakdown) {
    var list = el("dl", "result-breakdown");
    BREAKDOWN.forEach(function (entry) {
      var value = breakdown ? breakdown[entry[0]] : null;
      var dd = el("dd");
      dd.append(isNumber(value) ? formatNumber(value, 1) + "/100" : noData());
      list.append(el("dt", null, entry[2], entry[1]), dd);
    });
    return list;
  }

  function section(i18nKey, fallback, content) {
    var wrapper = el("div", "result-section");
    wrapper.append(el("h3", "result-section-title", fallback, i18nKey), content);
    return wrapper;
  }

  function textList(items) {
    var list = el("ul", "result-list");
    items.forEach(function (text) { list.appendChild(el("li", null, text)); });
    return list;
  }

  function compareToggle(vehicleId) {
    var label = el("label", "compare-toggle");
    var input = el("input", "compare-checkbox");
    input.type = "checkbox";
    input.id = "compare-" + vehicleId;
    input.value = String(vehicleId);
    input.addEventListener("change", onCompareChange);
    label.htmlFor = input.id;
    label.append(input, el("span", null, "Karşılaştır", "results.compareSelect"));
    return label;
  }

  function renderCard(item) {
    var card = el("article", "card result-card");
    var header = el("div", "result-header");
    var rank = el("span", "result-rank");
    var scoreLabelId = "score-label-" + item.vehicle_id;
    var price = el("span", null, formatNumber(item.price_try) + " TL ");
    var cost = isNumber(item.estimated_annual_cost_try)
      ? el("span", null, formatNumber(item.estimated_annual_cost_try) + " TL") : noData();
    var title = item.brand + " " + item.model + " " + item.variant + " (" + item.year + ")";

    rank.append(el("span", "visually-hidden", "Sıra", "results.rank"), "#" + item.rank);
    header.append(rank, el("h2", "card-title result-title", title), compareToggle(item.vehicle_id));
    price.append(el("span", "result-tag", "örnek fiyat", "results.samplePrice"));
    card.append(header, labelRow("results.price", "Fiyat:", price),
      labelRow("results.score", "Skor:", el("span", null, formatNumber(item.score, 1) + "/100"), scoreLabelId),
      scoreBar(item.score, scoreLabelId), breakdownList(item.score_breakdown),
      labelRow("results.annualCost", "Yıllık tahmini enerji maliyeti:", cost));

    if (Array.isArray(item.strengths) && item.strengths.length) {
      card.appendChild(section("results.strengths", "Güçlü yönler", textList(item.strengths)));
    }
    if (Array.isArray(item.weaknesses) && item.weaknesses.length) {
      card.appendChild(section("results.weaknesses", "Zayıf yönler", textList(item.weaknesses)));
    }
    if (hasText(item.explanation)) {
      card.appendChild(section("results.explanation", "Açıklama", el("p", "result-text", item.explanation)));
    }
    return card;
  }

  function selectedIds() {
    return Array.prototype.map.call(document.querySelectorAll(".compare-checkbox:checked"),
      function (input) { return input.value; });
  }

  function updateCompare(message, isWarning) {
    var node = byId("compareMessage");
    var count = selectedIds().length;
    node.setAttribute("data-i18n", message[0]);
    node.textContent = message[1];
    node.classList.toggle("is-warning", isWarning);
    byId("compareButton").disabled = count < COMPARE_MIN || count > COMPARE_MAX;
  }

  function onCompareChange(event) {
    var overLimit = selectedIds().length > COMPARE_MAX;
    if (overLimit) event.target.checked = false;
    updateCompare(overLimit ? LIMIT : HINT, overLimit);
  }

  function renderSuccess(data) {
    var list = byId("resultsList");
    byId("totalMatches").textContent = isNumber(data.total_matches) ? formatNumber(data.total_matches) : "";
    list.replaceChildren();
    data.recommendations.forEach(function (item) { list.appendChild(renderCard(item)); });
    updateCompare(HINT, false);
  }

  function fillList(listId, blockId, items, renderItem) {
    var list = byId(listId);
    list.replaceChildren();
    (Array.isArray(items) ? items : []).forEach(function (item) { list.appendChild(renderItem(item)); });
    byId(blockId).hidden = list.children.length === 0;
  }

  function renderConflict(data) {
    byId("conflictReason").textContent = data.reason || "";
    fillList("conflictConstraints", "conflictConstraintsBlock", data.conflicting_constraints,
      function (name) { return el("li", null, name); });
    fillList("conflictSuggestions", "conflictSuggestionsBlock", data.suggestions, function (suggestion) {
      var li = el("li", "conflict-suggestion");
      var unlocks = el("p", "result-text results-muted");
      unlocks.append(el("span", null, "Açılacak ek araç sayısı:", "results.conflict.unlocks"),
        " " + suggestion.additional_matches_unlocked);
      li.append(el("p", "result-text", suggestion.message), unlocks);
      return li;
    });
    byId("conflictExplanation").textContent = hasText(data.explanation) ? data.explanation : "";
    byId("conflictExplanationBlock").hidden = !hasText(data.explanation);
  }

  async function load() {
    var preference = readPreference();
    if (!preference) { window.location.replace("survey.html"); return; }
    showView("loading");
    try {
      var data = await getRecommendations(preference);
      if (data && data.status === "success" && Array.isArray(data.recommendations)) {
        renderSuccess(data); showView("success");
      } else if (data && data.status === "conflict") {
        renderConflict(data); showView("conflict");
      } else {
        throw new Error("Unknown status: " + (data && data.status));
      }
    } catch (err) {
      console.warn("AutoMatch: recommendations could not be loaded.", err);
      showView("error");
    }
  }

  function init() {
    views = { loading: byId("resultsLoading"), error: byId("resultsError"),
      success: byId("resultsSuccess"), conflict: byId("resultsConflict") };
    byId("retryButton").addEventListener("click", load);
    byId("compareButton").addEventListener("click", function () {
      var ids = selectedIds();
      if (ids.length >= COMPARE_MIN && ids.length <= COMPARE_MAX) {
        window.location.href = "compare.html?ids=" + ids.join(",");
      }
    });
    load();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
