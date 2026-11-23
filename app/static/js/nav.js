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
 */
(function () {
  "use strict";

  var NAV_ITEMS = [
    { href: "index.html", key: "nav.home", fallback: "Ana sayfa" },
    { href: "survey.html", key: "nav.survey", fallback: "Anket" },
    { href: "results.html", key: "nav.results", fallback: "Sonuçlar" },
    { href: "catalog.html", key: "nav.catalog", fallback: "Katalog" },
    { href: "compare.html", key: "nav.compare", fallback: "Karşılaştır" },
    { href: "scenario.html", key: "nav.scenario", fallback: "Scenario Lab" }
  ];

  // Language codes, identical in every language.
  var LANGUAGES = ["tr", "en"];

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

  function createLanguageSwitcher() {
    var item = document.createElement("li");
    var label = document.createElement("span");
    var activeLang = (document.documentElement.lang || "tr").toLowerCase();

    label.id = "navLanguageLabel";
    label.setAttribute("data-i18n", "nav.language");
    label.textContent = "Dil";
    item.setAttribute("role", "group");
    item.setAttribute("aria-labelledby", label.id);
    item.appendChild(label);

    LANGUAGES.forEach(function (lang) {
      var button = document.createElement("button");
      var isActive = lang === activeLang;
      button.type = "button";
      button.lang = lang;
      button.setAttribute("data-lang", lang);
      button.setAttribute("aria-pressed", String(isActive));
      button.className = "btn " + (isActive ? "btn-primary" : "btn-secondary");
      button.textContent = lang.toUpperCase();
      // TODO(T15): i18n.js switches the language here (load tr.json / en.json,
      // update data-i18n texts, <html lang> and aria-pressed).
      item.appendChild(document.createTextNode(" "));
      item.appendChild(button);
    });

    return item;
  }

  function buildNav() {
    var page = currentPage();
    var nav = document.createElement("nav");
    var list = document.createElement("ul");

    nav.className = "site-nav";
    nav.appendChild(createLink("index.html", "nav.brand", "AutoMatch", "nav-brand"));

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
    list.appendChild(createLanguageSwitcher());

    nav.appendChild(list);
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
