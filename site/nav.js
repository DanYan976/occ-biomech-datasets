(function () {
  var header = document.querySelector(".site-header");
  var nav = header && header.querySelector(".nav");
  if (!nav) return;

  /* ---------- Libraries dropdown (desktop) ---------- */
  function closeAll() {
    nav.querySelectorAll(".dropdown.open").forEach(function (dd) {
      dd.classList.remove("open");
      dd.querySelector(".dropdown-toggle").setAttribute("aria-expanded", "false");
    });
  }
  nav.querySelectorAll(".dropdown").forEach(function (dd) {
    var btn = dd.querySelector(".dropdown-toggle");
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var willOpen = !dd.classList.contains("open");
      closeAll();
      if (willOpen) {
        dd.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });

  /* ---------- mobile menu toggle ----------
     The hamburger is injected here (rather than written into every page)
     so all 30+ pages and the dataset template pick it up automatically.
     Below 820px style.css hides .nav until .site-header gets .menu-open. */
  if (!nav.id) nav.id = "site-nav";
  var toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "nav-toggle";
  toggle.setAttribute("aria-controls", nav.id);
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", "Open menu");
  toggle.innerHTML = '<span class="bars" aria-hidden="true"></span>';
  nav.parentNode.insertBefore(toggle, nav);

  function setMenu(open) {
    header.classList.toggle("menu-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    if (!open) closeAll();
  }
  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    setMenu(!header.classList.contains("menu-open"));
  });
  // tapping a link closes the panel (matters for same-page anchors like #about)
  nav.addEventListener("click", function (e) {
    e.stopPropagation();
    if (e.target.closest("a")) setMenu(false);
  });
  // leaving the mobile breakpoint resets the panel so desktop nav isn't stuck open
  var desktop = window.matchMedia("(min-width: 821px)");
  var onBreakpoint = function (e) { if (e.matches) setMenu(false); };
  if (desktop.addEventListener) desktop.addEventListener("change", onBreakpoint);
  else if (desktop.addListener) desktop.addListener(onBreakpoint);

  document.addEventListener("click", function () { setMenu(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setMenu(false);
  });
})();
