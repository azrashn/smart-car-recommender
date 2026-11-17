/**
 * AutoMatch - Multi-Step Survey Form Script (T11)
 *
 * Implements a 5-step wizard form collecting vehicle preferences
 * conforming strictly to the app.schemas.preference.Preference schema.
 *
 * Steps:
 * 1. Budget (budget_max_try, budget_min_try)
 * 2. Usage profile (usage_type, annual_km)
 * 3. Vehicle constraints (transmission, fuel_types, body_types, min_seats)
 * 4. Priority weights (fuel_economy, interior_space, performance, budget_fit, safety)
 * 5. Summary review and submission
 */

(function () {
  "use strict";

  // Storage keys
  const STORAGE_KEY_PREFERENCE = "automatch.preference";
  const STORAGE_KEY_DRAFT = "automatch.survey_draft";

  // Step title map for progress bar
  const STEP_TITLES = {
    1: "Bütçe Belirleme",
    2: "Kullanım Profili",
    3: "Araç Tercihleri",
    4: "Öncelikler",
    5: "Tercih Özeti",
  };

  // State object
  const state = {
    currentStep: 1,
    totalSteps: 5,
    priorities: {
      fuel_economy: "medium",
      interior_space: "medium",
      performance: "medium",
      budget_fit: "medium",
      safety: "medium",
    },
  };

  // DOM Elements
  const form = document.getElementById("surveyForm");
  const stepIndicator = document.getElementById("stepIndicator");
  const stepHeading = document.getElementById("stepHeading");
  const progressFill = document.getElementById("progressFill");
  const progressBar = document.getElementById("progressBar");
  const btnPrev = document.getElementById("btnPrev");
  const btnNext = document.getElementById("btnNext");
  const btnSubmit = document.getElementById("btnSubmit");
  const surveyAlert = document.getElementById("surveyAlert");
  const alertMessage = document.getElementById("alertMessage");
  const alertActions = document.getElementById("alertActions");

  // Step elements
  const stepPanes = {
    1: document.getElementById("step1"),
    2: document.getElementById("step2"),
    3: document.getElementById("step3"),
    4: document.getElementById("step4"),
    5: document.getElementById("step5"),
  };

  // Form Inputs
  const inputBudgetMax = document.getElementById("budgetMax");
  const inputBudgetMin = document.getElementById("budgetMin");
  const inputAnnualKm = document.getElementById("annualKm");
  const inputMinSeats = document.getElementById("minSeats");

  // Error containers
  const errors = {
    budgetMax: document.getElementById("budgetMaxError"),
    budgetMin: document.getElementById("budgetMinError"),
    annualKm: document.getElementById("annualKmError"),
    minSeats: document.getElementById("minSeatsError"),
  };

  /**
   * Initialize wizard on DOM load
   */
  function init() {
    setupOptionCardListeners();
    setupPriorityButtonListeners();
    setupNavigationListeners();
    setupEditButtonListeners();
    restoreDraft();
    goToStep(state.currentStep);
  }

  // =========================================================================
  // Option Card & Radio/Checkbox Styling
  // =========================================================================

  function setupOptionCardListeners() {
    // Radio buttons in option-card
    document.querySelectorAll(".option-card input[type='radio']").forEach((radio) => {
      radio.addEventListener("change", function () {
        const groupName = this.name;
        document.querySelectorAll(`input[name='${groupName}']`).forEach((r) => {
          r.closest(".option-card").classList.remove("selected");
        });
        if (this.checked) {
          this.closest(".option-card").classList.add("selected");
        }
        saveDraft();
      });
    });

    // Checkbox buttons in option-card
    document.querySelectorAll(".option-card input[type='checkbox']").forEach((cb) => {
      cb.addEventListener("change", function () {
        if (this.checked) {
          this.closest(".option-card").classList.add("selected");
        } else {
          this.closest(".option-card").classList.remove("selected");
        }
        saveDraft();
      });
    });

    // Input change saves draft
    [inputBudgetMax, inputBudgetMin, inputAnnualKm, inputMinSeats].forEach((input) => {
      if (input) {
        input.addEventListener("input", function () {
          clearFieldError(this);
          saveDraft();
        });
      }
    });
  }

  // =========================================================================
  // Priority Button Toggles (Step 4)
  // =========================================================================

  function setupPriorityButtonListeners() {
    document.querySelectorAll(".priority-btn-group").forEach((group) => {
      const field = group.dataset.field;
      group.querySelectorAll(".priority-btn").forEach((btn) => {
        btn.addEventListener("click", function () {
          group.querySelectorAll(".priority-btn").forEach((b) => b.classList.remove("active"));
          this.classList.add("active");
          state.priorities[field] = this.dataset.value;
          saveDraft();
        });
      });
    });
  }

  // =========================================================================
  // Navigation & Step Control
  // =========================================================================

  function setupNavigationListeners() {
    btnNext.addEventListener("click", function () {
      if (validateCurrentStep()) {
        if (state.currentStep < state.totalSteps) {
          goToStep(state.currentStep + 1);
        }
      }
    });

    btnPrev.addEventListener("click", function () {
      if (state.currentStep > 1) {
        goToStep(state.currentStep - 1);
      }
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (validateAllSteps()) {
        submitPreferences();
      }
    });
  }

  function setupEditButtonListeners() {
    document.querySelectorAll(".btn-edit").forEach((btn) => {
      btn.addEventListener("click", function () {
        const targetStep = parseInt(this.dataset.targetStep, 10);
        if (targetStep >= 1 && targetStep <= state.totalSteps) {
          goToStep(targetStep);
        }
      });
    });
  }

  function goToStep(step) {
    state.currentStep = step;

    // Toggle active panes
    Object.keys(stepPanes).forEach((key) => {
      const pane = stepPanes[key];
      if (parseInt(key, 10) === step) {
        pane.classList.add("active");
      } else {
        pane.classList.remove("active");
      }
    });

    // Update Progress header
    stepIndicator.textContent = `Adım ${step} / ${state.totalSteps}`;
    stepHeading.textContent = STEP_TITLES[step] || "";
    const pct = Math.round((step / state.totalSteps) * 100);
    progressFill.style.width = `${pct}%`;
    progressBar.setAttribute("aria-valuenow", pct);

    // Update Prev / Next / Submit buttons
    btnPrev.style.display = step > 1 ? "inline-flex" : "none";
    if (step === state.totalSteps) {
      btnNext.style.display = "none";
      btnSubmit.style.display = "inline-flex";
      renderSummary();
    } else {
      btnNext.style.display = "inline-flex";
      btnSubmit.style.display = "none";
    }

    // Scroll to top of card smoothly and set focus for accessibility
    document.querySelector(".survey-card").scrollIntoView({ behavior: "smooth", block: "start" });
    if (stepHeading) {
      stepHeading.focus();
    }
  }

  // =========================================================================
  // Step Validation
  // =========================================================================

  function clearFieldError(input) {
    if (!input) return;
    input.classList.remove("has-error");
    const errEl = errors[input.id === "budgetMax" ? "budgetMax" : input.id === "budgetMin" ? "budgetMin" : input.id === "annualKm" ? "annualKm" : "minSeats"];
    if (errEl) errEl.textContent = "";
  }

  function setFieldError(input, message) {
    if (!input) return;
    input.classList.add("has-error");
    const errEl = errors[input.id === "budgetMax" ? "budgetMax" : input.id === "budgetMin" ? "budgetMin" : input.id === "annualKm" ? "annualKm" : "minSeats"];
    if (errEl) errEl.textContent = message;
  }

  function validateCurrentStep() {
    clearAlert();
    let valid = true;

    if (state.currentStep === 1) {
      // Step 1: Budget
      const maxValStr = inputBudgetMax.value.trim();
      const minValStr = inputBudgetMin.value.trim();

      if (!maxValStr) {
        setFieldError(inputBudgetMax, "Maksimum bütçe zorunludur.");
        valid = false;
      } else {
        const maxVal = parseInt(maxValStr, 10);
        if (isNaN(maxVal) || maxVal <= 0) {
          setFieldError(inputBudgetMax, "Maksimum bütçe 0'dan büyük bir tamsayı olmalıdır.");
          valid = false;
        } else {
          clearFieldError(inputBudgetMax);
        }
      }

      if (minValStr) {
        const minVal = parseInt(minValStr, 10);
        const maxVal = parseInt(maxValStr, 10);
        if (isNaN(minVal) || minVal < 0) {
          setFieldError(inputBudgetMin, "Minimum bütçe 0 veya daha büyük olmalıdır.");
          valid = false;
        } else if (!isNaN(maxVal) && minVal > maxVal) {
          setFieldError(inputBudgetMin, "Minimum bütçe maksimum bütçeden büyük olamaz.");
          valid = false;
        } else {
          clearFieldError(inputBudgetMin);
        }
      } else {
        clearFieldError(inputBudgetMin);
      }
    } else if (state.currentStep === 2) {
      // Step 2: Usage
      const kmStr = inputAnnualKm.value.trim();
      if (kmStr) {
        const km = parseInt(kmStr, 10);
        if (isNaN(km) || km < 1000 || km > 200000) {
          setFieldError(inputAnnualKm, "Yıllık km 1.000 ile 200.000 arasında olmalıdır.");
          valid = false;
        } else {
          clearFieldError(inputAnnualKm);
        }
      } else {
        clearFieldError(inputAnnualKm);
      }
    } else if (state.currentStep === 3) {
      // Step 3: Vehicle Specs
      const seatsStr = inputMinSeats.value.trim();
      if (seatsStr) {
        const seats = parseInt(seatsStr, 10);
        if (isNaN(seats) || seats < 2 || seats > 9) {
          setFieldError(inputMinSeats, "Koltuk sayısı 2 ile 9 arasında olmalıdır.");
          valid = false;
        } else {
          clearFieldError(inputMinSeats);
        }
      } else {
        clearFieldError(inputMinSeats);
      }
    }

    return valid;
  }

  function validateAllSteps() {
    for (let s = 1; s <= 4; s++) {
      state.currentStep = s;
      if (!validateCurrentStep()) {
        goToStep(s);
        return false;
      }
    }
    state.currentStep = 5;
    return true;
  }

  // =========================================================================
  // Payload Builder conforming to Preference Schema
  // =========================================================================

  function buildPayload() {
    const maxVal = parseInt(inputBudgetMax.value.trim(), 10);
    const minValStr = inputBudgetMin.value.trim();
    const minVal = minValStr ? parseInt(minValStr, 10) : null;

    // Usage type
    const selectedUsage = document.querySelector("input[name='usage_type']:checked");
    const usageType = selectedUsage ? selectedUsage.value : null;

    // Annual km
    const kmStr = inputAnnualKm.value.trim();
    const annualKm = kmStr ? parseInt(kmStr, 10) : null;

    // Transmission
    const selectedTrans = document.querySelector("input[name='transmission']:checked");
    const transmission = selectedTrans && selectedTrans.value ? selectedTrans.value : null;

    // Fuel types
    const fuelTypes = [];
    document.querySelectorAll("input[name='fuel_types']:checked").forEach((cb) => {
      fuelTypes.push(cb.value);
    });

    // Body types
    const bodyTypes = [];
    document.querySelectorAll("input[name='body_types']:checked").forEach((cb) => {
      bodyTypes.push(cb.value);
    });

    // Min seats
    const seatsStr = inputMinSeats.value.trim();
    const minSeats = seatsStr ? parseInt(seatsStr, 10) : null;

    return {
      budget_max_try: maxVal,
      budget_min_try: minVal,
      usage_type: usageType,
      annual_km: annualKm,
      transmission: transmission,
      fuel_types: fuelTypes,
      body_types: bodyTypes,
      min_seats: minSeats,
      priorities: {
        fuel_economy: state.priorities.fuel_economy || "medium",
        interior_space: state.priorities.interior_space || "medium",
        performance: state.priorities.performance || "medium",
        budget_fit: state.priorities.budget_fit || "medium",
        safety: state.priorities.safety || "medium",
      },
      language: "tr",
    };
  }

  // =========================================================================
  // Step 5: Render Summary
  // =========================================================================

  function formatTRY(amount) {
    if (amount === null || amount === undefined || isNaN(amount)) return "Belirtilmedi";
    return new Intl.NumberFormat("tr-TR").format(amount) + " TL";
  }

  const USAGE_LABELS = {
    city: "Şehir İçi",
    highway: "Uzun Yol",
    mixed: "Karma",
    family: "Aile",
  };

  const TRANS_LABELS = {
    manual: "Manuel",
    automatic: "Otomatik",
  };

  const FUEL_LABELS = {
    petrol: "Benzin",
    diesel: "Dizel",
    hybrid: "Hibrit",
    electric: "Elektrik",
  };

  const BODY_LABELS = {
    hatchback: "Hatchback",
    sedan: "Sedan",
    suv: "SUV",
    wagon: "Station Wagon",
    mpv: "MPV",
  };

  const PRIO_LABELS = {
    low: "Düşük (1)",
    medium: "Orta (2)",
    high: "Yüksek (3)",
  };

  function renderSummary() {
    const payload = buildPayload();

    // Budget
    document.getElementById("sumBudgetMax").textContent = formatTRY(payload.budget_max_try);
    document.getElementById("sumBudgetMin").textContent = payload.budget_min_try !== null ? formatTRY(payload.budget_min_try) : "Belirtilmedi";

    // Usage
    document.getElementById("sumUsageType").textContent = payload.usage_type ? USAGE_LABELS[payload.usage_type] || payload.usage_type : "Belirtilmedi";
    document.getElementById("sumAnnualKm").textContent = payload.annual_km ? `${new Intl.NumberFormat("tr-TR").format(payload.annual_km)} km` : "Belirtilmedi";

    // Vehicle
    document.getElementById("sumTransmission").textContent = payload.transmission ? TRANS_LABELS[payload.transmission] || payload.transmission : "Fark etmez";
    document.getElementById("sumFuelTypes").textContent = payload.fuel_types.length > 0 ? payload.fuel_types.map((f) => FUEL_LABELS[f] || f).join(", ") : "Fark etmez";
    document.getElementById("sumBodyTypes").textContent = payload.body_types.length > 0 ? payload.body_types.map((b) => BODY_LABELS[b] || b).join(", ") : "Fark etmez";
    document.getElementById("sumMinSeats").textContent = payload.min_seats ? `En az ${payload.min_seats} koltuk` : "Fark etmez";

    // Priorities
    document.getElementById("sumPrioFuel").textContent = PRIO_LABELS[payload.priorities.fuel_economy] || payload.priorities.fuel_economy;
    document.getElementById("sumPrioSpace").textContent = PRIO_LABELS[payload.priorities.interior_space] || payload.priorities.interior_space;
    document.getElementById("sumPrioPerf").textContent = PRIO_LABELS[payload.priorities.performance] || payload.priorities.performance;
    document.getElementById("sumPrioBudget").textContent = PRIO_LABELS[payload.priorities.budget_fit] || payload.priorities.budget_fit;
    document.getElementById("sumPrioSafety").textContent = PRIO_LABELS[payload.priorities.safety] || payload.priorities.safety;
  }

  // =========================================================================
  // Draft Persistence (sessionStorage)
  // =========================================================================

  function saveDraft() {
    try {
      const draft = {
        budget_max_try: inputBudgetMax.value,
        budget_min_try: inputBudgetMin.value,
        usage_type: (document.querySelector("input[name='usage_type']:checked") || {}).value || "",
        annual_km: inputAnnualKm.value,
        transmission: (document.querySelector("input[name='transmission']:checked") || {}).value || "",
        fuel_types: Array.from(document.querySelectorAll("input[name='fuel_types']:checked")).map((cb) => cb.value),
        body_types: Array.from(document.querySelectorAll("input[name='body_types']:checked")).map((cb) => cb.value),
        min_seats: inputMinSeats.value,
        priorities: { ...state.priorities },
      };
      sessionStorage.setItem(STORAGE_KEY_DRAFT, JSON.stringify(draft));
    } catch (e) {
      // Storage access blocked or quota exceeded
    }
  }

  function restoreDraft() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY_DRAFT);
      if (!raw) return;
      const draft = JSON.parse(raw);

      if (draft.budget_max_try !== undefined) inputBudgetMax.value = draft.budget_max_try;
      if (draft.budget_min_try !== undefined) inputBudgetMin.value = draft.budget_min_try;

      if (draft.usage_type) {
        const r = document.querySelector(`input[name='usage_type'][value='${draft.usage_type}']`);
        if (r) {
          r.checked = true;
          r.closest(".option-card").classList.add("selected");
        }
      }

      if (draft.annual_km !== undefined) inputAnnualKm.value = draft.annual_km;

      if (draft.transmission !== undefined) {
        const t = document.querySelector(`input[name='transmission'][value='${draft.transmission}']`);
        if (t) {
          document.querySelectorAll("input[name='transmission']").forEach((item) => item.closest(".option-card").classList.remove("selected"));
          t.checked = true;
          t.closest(".option-card").classList.add("selected");
        }
      }

      if (Array.isArray(draft.fuel_types)) {
        draft.fuel_types.forEach((val) => {
          const cb = document.querySelector(`input[name='fuel_types'][value='${val}']`);
          if (cb) {
            cb.checked = true;
            cb.closest(".option-card").classList.add("selected");
          }
        });
      }

      if (Array.isArray(draft.body_types)) {
        draft.body_types.forEach((val) => {
          const cb = document.querySelector(`input[name='body_types'][value='${val}']`);
          if (cb) {
            cb.checked = true;
            cb.closest(".option-card").classList.add("selected");
          }
        });
      }

      if (draft.min_seats !== undefined) inputMinSeats.value = draft.min_seats;

      if (draft.priorities && typeof draft.priorities === "object") {
        Object.keys(draft.priorities).forEach((k) => {
          const val = draft.priorities[k];
          state.priorities[k] = val;
          const group = document.querySelector(`.priority-btn-group[data-field='${k}']`);
          if (group) {
            group.querySelectorAll(".priority-btn").forEach((b) => {
              if (b.dataset.value === val) b.classList.add("active");
              else b.classList.remove("active");
            });
          }
        });
      }
    } catch (e) {
      // Draft parse error, ignore
    }
  }

  // =========================================================================
  // Alert & Feedback Box
  // =========================================================================

  function clearAlert() {
    surveyAlert.style.display = "none";
    surveyAlert.className = "alert-box";
    alertMessage.innerHTML = "";
    alertActions.style.display = "none";
  }

  function showAlert(message, type, showContinueBtn) {
    surveyAlert.className = `alert-box alert-${type}`;
    alertMessage.innerHTML = message;
    alertActions.style.display = showContinueBtn ? "flex" : "none";
    surveyAlert.style.display = "block";
    surveyAlert.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // =========================================================================
  // API Submission (POST /api/preferences/form)
  // =========================================================================

  async function submitPreferences() {
    clearAlert();
    btnSubmit.disabled = true;
    btnSubmit.textContent = "Kaydediliyor...";

    const payload = buildPayload();

    try {
      const response = await fetch("/api/preferences/form", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        // HTTP 200 OK
        const validatedPref = await response.json();
        sessionStorage.setItem(STORAGE_KEY_PREFERENCE, JSON.stringify(validatedPref));
        sessionStorage.removeItem(STORAGE_KEY_DRAFT);
        // Automatic redirect on 200 OK
        window.location.href = "results.html";
        return;
      }

      if (response.status === 422) {
        // HTTP 422 Unprocessable Entity (FastAPI validation error)
        btnSubmit.disabled = false;
        btnSubmit.textContent = "Önerileri Gör";
        const errData = await response.json();
        render422Errors(errData);
        return;
      }

      // Other HTTP error (e.g. 404 Not Found before T12 is implemented)
      throw new Error(`HTTP ${response.status}`);
    } catch (err) {
      console.warn("AutoMatch: /api/preferences/form unavailable or network error. Falling back to local storage.", err);

      // Graceful fallback: save validated local payload to sessionStorage
      sessionStorage.setItem(STORAGE_KEY_PREFERENCE, JSON.stringify(payload));
      sessionStorage.removeItem(STORAGE_KEY_DRAFT);

      btnSubmit.disabled = false;
      btnSubmit.textContent = "Önerileri Gör";

      showAlert(
        "<strong>Bilgi:</strong> Tercih API servisine ulaşılamadı (henüz aktif olmayabilir). Tercihleriniz yerel olarak tarayıcınıza kaydedildi. Sonuçları görüntülemek için aşağıdaki butonla devam edebilirsiniz.",
        "warning",
        true // Show "Sonuçlara Devam Et" button
      );
    }
  }

  function render422Errors(errData) {
    let msg = "<strong>Lütfen formdaki hataları düzeltin:</strong><ul>";
    if (Array.isArray(errData.detail)) {
      errData.detail.forEach((item) => {
        const fieldName = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "Form";
        msg += `<li><code>${fieldName}</code>: ${item.msg}</li>`;
      });
    } else {
      msg += `<li>${errData.detail || "Doğrulama hatası"}</li>`;
    }
    msg += "</ul>";
    showAlert(msg, "danger", false);
  }

  // Run init on script execution or load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
