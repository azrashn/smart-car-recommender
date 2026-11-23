/*
 * AutoMatch - shared site navigation (T60). Single source of the menu.
 *
 * Usage on any page:
 *   1. Optional placeholder as the first element of <body> (avoids layout shift):
 *        <header class="site-header" data-site-nav></header>
 *      Without it, a .site-header is inserted as the first child of <body>.
 *   2. Load the script (after base.css, before page scripts):
 *        <script src="js/nav.js"></script>
 *
 * Labels carry data-i18n="nav.*"; the Turkish strings below are only the
 * fallback shown until i18n.js (T15) replaces them from tr.json / en.json.
 * On mobile (<= 600px) the links collapse behind the "nav.menu" button; the
 * CSS in base.css hides them while the button has aria-expanded="false".
 */
(function () {
  "use strict";

  var LINKS_ID = "siteNavLinks";
  var LANGUAGE_ID = "navLanguage";

  var NAV_ITEMS = [
    { href: "index.html", key: "nav.home", fallback: "Ana sayfa" },
    { href: "survey.html", key: "nav.survey", fallback: "Anket" },
    { href: "results.html", key: "nav.results", fallback: "Sonuçlar" },
    { href: "catalog.html", key: "nav.catalog", fallback: "Katalog" },
    { href: "compare.html", key: "nav.compare", fallback: "Karşılaştır" },
    { href: "scenario.html", key: "nav.scenario", fallback: "Scenario Lab" }
  ];

  // Language names are written in their own language (endonyms), so they are
  // the same in every UI language and are not translated.
  var LANGUAGES = [
    { code: "tr", name: "Türkçe" },
    { code: "en", name: "English" }
  ];

  function currentPage() {
    var path = window.location.pathname;
    var page = path.substring(path.lastIndexOf("/") + 1);
    return page === "" ? "index.html" : page;
  }

  function createLink(href, key, fallback, className) {
    var link = document.createElement("a");
    link.href = href;
    link.setAttribute("data-i18n", key);
    link.textContent = fallback;
    if (className) {
      link.className = className;
    }
    return link;
  }

  function createLinkList() {
    var page = currentPage();
    var list = document.createElement("ul");
    list.id = LINKS_ID;
    list.className = "nav-links";

    NAV_ITEMS.forEach(function (navItem) {
      var item = document.createElement("li");
      var link = createLink(navItem.href, navItem.key, navItem.fallback);
      if (navItem.href === page) {
        link.classList.add("active");
        link.setAttribute("aria-current", "page");
      }
      item.appendChild(link);
      list.appendChild(item);
    });
    return list;
  }

  function createLanguageSelect() {
    var wrapper = document.createElement("div");
    var label = document.createElement("label");
    var select = document.createElement("select");
    var htmlLang = (document.documentElement.lang || "").toLowerCase().slice(0, 2);

    wrapper.className = "nav-language";
    label.className = "visually-hidden";
    label.htmlFor = LANGUAGE_ID;
    label.setAttribute("data-i18n", "nav.language");
    label.textContent = "Dil";

    select.id = LANGUAGE_ID;
    select.className = "nav-language-select";
    LANGUAGES.forEach(function (language) {
      var option = document.createElement("option");
      option.value = language.code;
      option.lang = language.code;
      option.textContent = language.name;
      select.appendChild(option);
    });
    select.value = htmlLang === "en" ? "en" : "tr";

    // TODO(T15): i18n.js handles the "change" event (load tr.json / en.json,
    // update data-i18n texts and <html lang>). Until then it does nothing.

    wrapper.appendChild(label);
    wrapper.appendChild(select);
    return wrapper;
  }

  function createMenuToggle() {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-secondary nav-toggle";
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", LINKS_ID);
    button.setAttribute("data-i18n", "nav.menu");
    button.textContent = "Menü";
    return button;
  }

  function setExpanded(button, expanded) {
    button.setAttribute("aria-expanded", String(expanded));
  }

  function bindMenuToggle(button) {
    button.addEventListener("click", function () {
      setExpanded(button, button.getAttribute("aria-expanded") !== "true");
    });

    document.addEventListener("keydown", function (event) {
      var isOpen = button.getAttribute("aria-expanded") === "true";
      // offsetParent is null when the button is hidden (desktop layout).
      if (event.key === "Escape" && isOpen && button.offsetParent !== null) {
        setExpanded(button, false);
        button.focus();
      }
    });
  }

  function buildNav() {
    var nav = document.createElement("nav");
    var toggle = createMenuToggle();

    // DOM order: brand, toggle, links, language. The toggle sits right before
    // the list it controls; CSS reorders the mobile top row visually.
    nav.className = "site-nav";
    nav.appendChild(createLink("index.html", "nav.brand", "AutoMatch", "nav-brand"));
    nav.appendChild(toggle);
    nav.appendChild(createLinkList());
    nav.appendChild(createLanguageSelect());
    bindMenuToggle(toggle);
    return nav;
  }

  function mountNav() {
    var header = document.querySelector("[data-site-nav]");
    if (!header) {
      header = document.createElement("header");
      document.body.insertBefore(header, document.body.firstChild);
    }
    header.classList.add("site-header");
    header.replaceChildren(buildNav());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountNav);
  } else {
    mountNav();
  }
})();
