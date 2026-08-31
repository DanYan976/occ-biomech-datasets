/* Occupational Biomechanics Catalog — client logic.
   Reads the JSON injected by scripts/build_catalog.py and renders whichever of
   the three views the current document asks for: the landing page (stats +
   recently added), the catalog page (filters, sort, cards/table views), or the
   exoskeleton collection (grouped by supported body region).
   No build step needed to view: serve the site/ folder. */

(function () {
  "use strict";

  // ---- read injected catalog -------------------------------------------
  var raw = document.getElementById("catalog-data");
  var CATALOG = { datasets: [] };
  try { CATALOG = JSON.parse(raw.textContent); } catch (e) { console.error("Bad catalog JSON", e); }
  var DATA = CATALOG.datasets || [];

  // ---- display labels ---------------------------------------------------
  var TASK_LABEL = {
    lifting: "Lifting", lowering: "Lowering", carrying: "Carrying",
    pushing: "Pushing", pulling: "Pulling", holding: "Holding",
    reaching: "Reaching", squatting: "Squatting", walking: "Walking",
    assembly: "Assembly", mmh: "MMH"
  };
  // Modalities = what was captured, grouped kinematics / kinetics / EMG / physio / vision / self-report.
  var MOD_LABEL = {
    mocap: "Optical mocap", imu: "IMU", force_plate: "Force plate",
    pressure: "Pressure insole / glove", emg: "EMG", physiological: "Physiological",
    video: "Video", egocentric_video: "Egocentric video", depth: "Depth / LiDAR", survey: "Survey"
  };
  var MOD_ORDER = ["mocap", "imu", "force_plate", "pressure", "emg", "physiological",
                   "video", "egocentric_video", "depth", "survey"];
  var STATUS_LABEL = { open: "Open", coming_soon: "Coming soon", restricted: "Restricted" };
  // source.country holds ISO 3166-1 alpha-2 codes; unknown codes fall back to the code itself.
  var COUNTRY_LABEL = {
    AT: "Austria", AU: "Australia", BE: "Belgium", BR: "Brazil", CA: "Canada", CH: "Switzerland",
    CN: "China", CZ: "Czechia", DE: "Germany", DK: "Denmark", ES: "Spain", FI: "Finland",
    FR: "France", GB: "United Kingdom", GR: "Greece", HK: "Hong Kong", IE: "Ireland", IL: "Israel",
    IN: "India", IT: "Italy", JP: "Japan", KR: "South Korea", MX: "Mexico", NL: "Netherlands",
    NO: "Norway", NZ: "New Zealand", PL: "Poland", PT: "Portugal", SE: "Sweden", SG: "Singapore",
    SI: "Slovenia", TR: "Türkiye", TW: "Taiwan", US: "United States"
  };
  function countryName(c) { return COUNTRY_LABEL[c] || c; }
  function countries(d) { return (d.source && d.source.country) || []; }

  var EXO_ROLE_LABEL = { evaluation: "Device evaluation", control_input: "Controller training data" };
  var EXO_ROLE_BADGE = { evaluation: "Exo evaluation" }; // control-input records carry no card badge
  var EXO_REGION_LABEL = {
    back: "Back", shoulder: "Shoulder", knee: "Knee", hip: "Hip",
    ankle: "Ankle", neck: "Neck", wrist: "Wrist", full_body: "Full body"
  };
  var REGION_ORDER = ["back", "shoulder", "knee", "hip", "ankle", "neck", "wrist", "full_body"];
  var EXO_ACTUATION_LABEL = { passive: "Passive", active: "Active", quasi_passive: "Quasi-passive" };
  var ACTUATION_ORDER = ["passive", "active", "quasi_passive"];

  // License strings are free text; bucket them for filtering.
  var LICENSE_BUCKETS = [
    { key: "cc0", label: "CC0 / Public domain", test: /cc0|public domain/i },
    { key: "cc-by-nc", label: "CC-BY-NC", test: /cc-by-nc/i },
    { key: "cc-by", label: "CC-BY", test: /cc-by/i },
    { key: "on-request", label: "On request", test: /request/i }
  ];
  function licenseBucket(d) {
    var lic = (d.access && d.access.license) || "";
    for (var i = 0; i < LICENSE_BUCKETS.length; i++) {
      if (LICENSE_BUCKETS[i].test.test(lic)) return LICENSE_BUCKETS[i].key;
    }
    return "other";
  }

  function detailUrl(d) { return "datasets/" + d.id + ".html"; }

  // ---- exoskeleton helpers ---------------------------------------------
  function exo(d) { return d.exoskeleton || null; }
  function exoRole(d) { return exo(d) ? d.exoskeleton.role : null; }
  function exoList(d, key) { return (exo(d) && d.exoskeleton[key]) || []; }
  function exoActuations(d) {
    var a = exoList(d, "actuation");
    return ACTUATION_ORDER.filter(function (k) { return a.indexOf(k) !== -1; });
  }
  var EXO_DATA = DATA.filter(exo);

  function setExoStats() {
    function put(id, value) {
      var node = document.getElementById(id);
      if (node) node.textContent = value;
    }
    var devices = new Set(), regions = new Set(), evals = 0, control = 0;
    EXO_DATA.forEach(function (d) {
      if (exoRole(d) === "evaluation") evals++;
      if (exoRole(d) === "control_input") control++;
      exoList(d, "devices").forEach(function (v) { devices.add(v); });
      exoList(d, "body_region").forEach(function (v) { regions.add(v); });
    });
    put("stat-exo", EXO_DATA.length);
    put("exo-eval-count", evals);
    put("exo-device-count", devices.size);
    put("exo-region-count", regions.size);
    put("exo-control-count", control);
  }

  // ---- shared helpers ---------------------------------------------------
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  function setStats() {
    var totalEl = document.getElementById("stat-total");
    if (!totalEl) return;
    var ctry = new Set();
    DATA.forEach(function (d) {
      countries(d).forEach(function (c) { ctry.add(c); });
    });
    totalEl.textContent = DATA.length;
    var ctryEl = document.getElementById("stat-countries");
    if (ctryEl) ctryEl.textContent = ctry.size;
  }

  function metric(k, v, title) {
    var m = el("div", "metric");
    m.appendChild(el("span", "k", k));
    var val = el("span", "v", v);
    if (title) val.title = title;
    m.appendChild(val);
    return m;
  }

  function samplingText(d, compact) {
    if (!d.sampling) return null;
    var keys = Object.keys(d.sampling);
    if (!keys.length) return null;
    if (compact) return keys.map(function (k) { return d.sampling[k]; }).join("/") + " Hz";
    return keys.map(function (k) { return k + " " + d.sampling[k] + " Hz"; }).join(" · ");
  }

  function shorten(s, n) { return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  function card(d) {
    var c = el("article", "card" + (d.status === "coming_soon" ? " is-coming" : ""));
    c.id = "dataset-" + d.id;

    var top = el("div", "card-top");
    var left = el("div");
    var permalink = el("a", "cid", d.id);
    permalink.href = detailUrl(d);
    permalink.title = "Dataset page";
    left.appendChild(permalink);
    var badges = el("div");
    badges.style.cssText = "display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end";
    badges.appendChild(el("span", "badge " + d.status, STATUS_LABEL[d.status] || d.status));
    if (EXO_ROLE_BADGE[exoRole(d)]) badges.appendChild(el("span", "badge exo", EXO_ROLE_BADGE[exoRole(d)]));
    var acts = exoActuations(d);
    if (acts.length) {
      badges.appendChild(el("span", "badge actuation " + acts.join(" "),
        acts.map(function (a) { return EXO_ACTUATION_LABEL[a] || a; }).join(" + ")));
    }
    if (d.sample) badges.appendChild(el("span", "badge sample", "sample"));
    top.appendChild(left);
    top.appendChild(badges);
    c.appendChild(top);

    var h = el("h3");
    var titleLink = el("a", "title-link", d.title);
    titleLink.href = detailUrl(d);
    h.appendChild(titleLink);
    c.appendChild(h);

    var src = d.source || {};
    c.appendChild(el("div", "src", [src.institution, src.year].filter(Boolean).join(" · ")));
    if (d.description) c.appendChild(el("p", "desc", d.description.trim()));

    // modality + task tags
    var tags = el("div", "tags");
    (d.modalities || []).forEach(function (m) { tags.appendChild(el("span", "tag mod", MOD_LABEL[m] || m)); });
    (d.tasks || []).forEach(function (t) { tags.appendChild(el("span", "tag", TASK_LABEL[t] || t)); });
    c.appendChild(tags);

    // metric readout
    var metrics = el("div", "metrics");
    var subj = d.subjects || {};
    metrics.appendChild(metric("Subjects", subj.n ? String(subj.n) : "—"));
    metrics.appendChild(metric("Load", d.load ? shorten(d.load, 22) : "—", d.load));
    metrics.appendChild(metric("Rate", samplingText(d, true) || "—", samplingText(d, false)));
    metrics.appendChild(metric("Formats", (d.formats || []).join(", ") || "—"));
    var devices = exoList(d, "devices");
    if (devices.length) {
      var joined = devices.join(", ");
      metrics.appendChild(metric("Device", shorten(joined, 46), joined));
    }
    c.appendChild(metrics);

    // footer: license + link out / pending
    var foot = el("div", "card-foot");
    var acc = d.access || {};
    foot.appendChild(el("span", "lic", acc.license || (d.status === "coming_soon" ? "license: TBD" : "—")));
    if (d.status !== "coming_soon" && acc.url) {
      var a = el("a", "out", "View source ↗");
      a.href = acc.url; a.target = "_blank"; a.rel = "noopener";
      foot.appendChild(a);
    } else {
      foot.appendChild(el("span", "pending", d.status === "coming_soon" ? "Release pending" : "—"));
    }
    c.appendChild(foot);
    return c;
  }

  // ======================================================================
  // Landing page: stats + recently added
  // ======================================================================
  var recentGrid = document.getElementById("recent-grid");
  if (recentGrid) {
    setStats();
    setExoStats();
    DATA.slice()
      .sort(function (a, b) { return String(b.added || "").localeCompare(String(a.added || "")); })
      .slice(0, 3)
      .forEach(function (d) { recentGrid.appendChild(card(d)); });
  }

  // ======================================================================
  // Exoskeleton collection: device index + groups by supported body region
  // ======================================================================
  var exoGroups = document.getElementById("exo-groups");
  if (exoGroups) {
    setExoStats();

    var deviceFilter = null;      // null = show every record
    var actuationFilter = null;   // null | "passive" | "active" | "quasi_passive"

    var inActuation = function (d) {
      return !actuationFilter || exoList(d, "actuation").indexOf(actuationFilter) !== -1;
    };
    var inFilter = function (d) {
      return inActuation(d) && (!deviceFilter || exoList(d, "devices").indexOf(deviceFilter) !== -1);
    };

    // Actuation toggle: All / Passive / Active (quasi-passive only once the catalog has one)
    var actuationToggle = function () {
      var box = document.getElementById("actuation-toggle");
      if (!box) return;
      var present = ACTUATION_ORDER.filter(function (a) {
        return EXO_DATA.some(function (d) { return exoList(d, "actuation").indexOf(a) !== -1; });
      });
      box.innerHTML = "";
      if (!present.length) { box.parentNode.hidden = true; return; }
      [null].concat(present).forEach(function (a) {
        var b = document.createElement("button");
        b.className = "tbtn";
        b.type = "button";
        b.textContent = a ? EXO_ACTUATION_LABEL[a] : "All";
        b.setAttribute("aria-pressed", actuationFilter === a ? "true" : "false");
        b.addEventListener("click", function () {
          actuationFilter = a;
          renderCollection();
        });
        box.appendChild(b);
      });
    };

    var deviceIndex = function () {
      var box = document.getElementById("device-index");
      if (!box) return;
      var counts = new Map();
      EXO_DATA.filter(inActuation).forEach(function (d) {
        exoList(d, "devices").forEach(function (name) {
          counts.set(name, (counts.get(name) || 0) + 1);
        });
      });
      box.innerHTML = "";
      if (!counts.size) {
        box.appendChild(el("p", "gov", actuationFilter
          ? "No " + EXO_ACTUATION_LABEL[actuationFilter].toLowerCase() + " devices indexed yet."
          : "No devices indexed yet."));
        return;
      }
      Array.from(counts.keys()).sort().forEach(function (name) {
        var b = document.createElement("button");
        b.className = "device-chip";
        b.type = "button";
        b.setAttribute("aria-pressed", deviceFilter === name ? "true" : "false");
        b.appendChild(el("span", "dname", name));
        b.appendChild(el("span", "dcount", String(counts.get(name))));
        b.addEventListener("click", function () {
          deviceFilter = deviceFilter === name ? null : name;
          renderCollection();
        });
        box.appendChild(b);
      });
    };

    var group = function (title, note, items) {
      if (!items.length) return null;
      var sec = el("section", "exo-group");
      var head = el("div", "section-head");
      head.appendChild(el("h2", null, title));
      head.appendChild(el("span", "count-note", items.length + (items.length === 1 ? " study" : " studies")));
      sec.appendChild(head);
      if (note) sec.appendChild(el("p", "section-lede", note));
      var g = el("div", "grid");
      items.forEach(function (d) { g.appendChild(card(d)); });
      sec.appendChild(g);
      return sec;
    };

    var renderCollection = function () {
      // a device that vanished under the new actuation filter can't stay selected
      if (deviceFilter && !EXO_DATA.some(function (d) {
        return inActuation(d) && exoList(d, "devices").indexOf(deviceFilter) !== -1;
      })) deviceFilter = null;
      actuationToggle();
      deviceIndex();
      exoGroups.innerHTML = "";

      var shown = EXO_DATA.filter(inFilter);
      var evaluations = shown.filter(function (d) { return exoRole(d) === "evaluation"; });
      var controls = shown.filter(function (d) { return exoRole(d) === "control_input"; });

      if (deviceFilter || actuationFilter) {
        var bar = el("div", "filter-note");
        var what = actuationFilter ? EXO_ACTUATION_LABEL[actuationFilter].toLowerCase() + "-device studies" : "studies";
        bar.appendChild(el("span", null,
          "Showing " + what + (deviceFilter ? " of " + deviceFilter : "") + "."));
        var clear = document.createElement("button");
        clear.className = "linkbtn";
        clear.type = "button";
        clear.textContent = "Show all";
        clear.addEventListener("click", function () {
          deviceFilter = null; actuationFilter = null; renderCollection();
        });
        bar.appendChild(clear);
        exoGroups.appendChild(bar);
      }

      REGION_ORDER.forEach(function (region) {
        var items = evaluations.filter(function (d) {
          return exoList(d, "body_region").indexOf(region) !== -1;
        });
        var sec = group((EXO_REGION_LABEL[region] || region) + " support", null, items);
        if (sec) exoGroups.appendChild(sec);
      });

      var unplaced = evaluations.filter(function (d) { return !exoList(d, "body_region").length; });
      var other = group("Other evaluations", null, unplaced);
      if (other) exoGroups.appendChild(other);

      var ctrl = group(
        "Training data for exoskeleton controllers",
        "No device was worn during capture. These recordings exist to train and validate the " +
        "intent detection, payload estimation, and joint-load models an exoskeleton controller needs.",
        controls
      );
      if (ctrl) exoGroups.appendChild(ctrl);

      if (!shown.length) {
        var e = el("div", "empty");
        e.appendChild(el("b", null, "Nothing to show."));
        e.appendChild(el("span", null, "No exoskeleton record matches this selection."));
        exoGroups.appendChild(e);
      }
    };

    renderCollection();
  }

  // ======================================================================
  // Catalog page: filters, sort, cards/table views
  // ======================================================================
  var grid = document.getElementById("grid");
  var taskBox = document.getElementById("task-chips");
  if (!grid || !taskBox) return;

  var state = { q: "", tasks: new Set(), mods: new Set(), status: new Set(), lic: new Set(), country: new Set() };
  var sortKey = "added-desc";
  var view = "cards";
  try { view = localStorage.getItem("ob-view") || "cards"; } catch (e) {}

  document.getElementById("total").textContent = DATA.length;

  // ---- filter chips -----------------------------------------------------
  function uniqueSorted(key) {
    var s = new Set();
    DATA.forEach(function (d) { (d[key] || []).forEach(function (v) { s.add(v); }); });
    return Array.from(s).sort();
  }

  function makeChip(container, value, label, bucket, statusClass) {
    var b = document.createElement("button");
    b.className = "chip" + (statusClass ? " status-" + value : "");
    b.type = "button";
    b.textContent = label;
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () {
      var on = b.getAttribute("aria-pressed") === "true";
      b.setAttribute("aria-pressed", on ? "false" : "true");
      if (on) bucket.delete(value); else bucket.add(value);
      render();
    });
    container.appendChild(b);
  }

  function buildFilters() {
    var modBox = document.getElementById("modality-chips");
    var statBox = document.getElementById("status-chips");
    var licBox = document.getElementById("license-chips");
    uniqueSorted("tasks").forEach(function (t) {
      makeChip(taskBox, t, TASK_LABEL[t] || t, state.tasks, false);
    });
    var presentMods = new Set(uniqueSorted("modalities"));
    MOD_ORDER.concat(Array.from(presentMods).filter(function (m) { return MOD_ORDER.indexOf(m) === -1; }))
      .filter(function (m) { return presentMods.has(m); })
      .forEach(function (m) { makeChip(modBox, m, MOD_LABEL[m] || m, state.mods, false); });
    ["open", "coming_soon", "restricted"].forEach(function (s) {
      makeChip(statBox, s, STATUS_LABEL[s], state.status, true);
    });
    var present = new Set(DATA.map(licenseBucket));
    LICENSE_BUCKETS.forEach(function (b) {
      if (present.has(b.key)) makeChip(licBox, b.key, b.label, state.lic, false);
    });
    if (present.has("other")) makeChip(licBox, "other", "Other", state.lic, false);

    // Country chips, most records first so the catalog's footprint reads at a glance.
    var ctryBox = document.getElementById("country-chips");
    if (ctryBox) {
      var counts = {};
      DATA.forEach(function (d) { countries(d).forEach(function (c) { counts[c] = (counts[c] || 0) + 1; }); });
      Object.keys(counts).sort(function (a, b) {
        return (counts[b] - counts[a]) || countryName(a).localeCompare(countryName(b));
      }).forEach(function (c) {
        makeChip(ctryBox, c, countryName(c) + " (" + counts[c] + ")", state.country, false);
      });
    }
  }

  // ---- filtering + sorting ---------------------------------------------
  function matches(d) {
    if (state.status.size && !state.status.has(d.status)) return false;
    if (state.lic.size && !state.lic.has(licenseBucket(d))) return false;
    if (state.tasks.size && !(d.tasks || []).some(function (t) { return state.tasks.has(t); })) return false;
    if (state.mods.size && !(d.modalities || []).some(function (m) { return state.mods.has(m); })) return false;
    if (state.country.size && !countries(d).some(function (c) { return state.country.has(c); })) return false;
    if (state.q) {
      var hay = [
        d.title, d.id, (d.source && d.source.institution), (d.source && d.source.authors),
        countries(d).map(countryName).join(" "),
        (d.tasks || []).join(" "), (d.tags || []).join(" "), d.description,
        exoList(d, "devices").join(" ")
      ].join(" ").toLowerCase();
      if (hay.indexOf(state.q) === -1) return false;
    }
    return true;
  }

  var SORTS = {
    "added-desc": function (a, b) { return String(b.added || "").localeCompare(String(a.added || "")); },
    "year-desc": function (a, b) { return ((b.source || {}).year || 0) - ((a.source || {}).year || 0); },
    "year-asc": function (a, b) { return ((a.source || {}).year || 9999) - ((b.source || {}).year || 9999); },
    "title-asc": function (a, b) { return String(a.title).localeCompare(String(b.title)); },
    "subjects-desc": function (a, b) { return ((b.subjects || {}).n || 0) - ((a.subjects || {}).n || 0); }
  };

  // ---- table view -------------------------------------------------------
  function row(d) {
    var tr = document.createElement("tr");
    var src = d.source || {}, subj = d.subjects || {};

    var tdName = document.createElement("td");
    var a = el("a", "title-link", d.title);
    a.href = detailUrl(d);
    tdName.appendChild(a);
    tdName.appendChild(el("div", "cid", d.id));
    tr.appendChild(tdName);

    var tdInst = el("td", null, src.institution || "—");
    if (countries(d).length) tdInst.appendChild(el("div", "cid", countries(d).map(countryName).join(", ")));
    tr.appendChild(tdInst);
    tr.appendChild(el("td", "mono", src.year ? String(src.year) : "—"));
    tr.appendChild(el("td", "mono", subj.n ? String(subj.n) : "—"));
    tr.appendChild(el("td", "mono", (d.modalities || []).map(function (m) { return MOD_LABEL[m] || m; }).join(", ")));
    tr.appendChild(el("td", null, exoList(d, "devices").join(", ") || (exoRole(d) ? EXO_ROLE_LABEL[exoRole(d)] : "—")));

    var tdStatus = document.createElement("td");
    tdStatus.appendChild(el("span", "badge " + d.status, STATUS_LABEL[d.status] || d.status));
    tr.appendChild(tdStatus);

    tr.appendChild(el("td", "mono", d.added || "—"));
    return tr;
  }

  function setView(v) {
    view = v;
    try { localStorage.setItem("ob-view", v); } catch (e) {}
    document.getElementById("view-cards").setAttribute("aria-pressed", v === "cards" ? "true" : "false");
    document.getElementById("view-table").setAttribute("aria-pressed", v === "table" ? "true" : "false");
    grid.hidden = v !== "cards";
    document.getElementById("tablewrap").hidden = v !== "table";
  }

  // ---- rendering --------------------------------------------------------
  function render() {
    var shown = DATA.filter(matches).sort(SORTS[sortKey] || SORTS["added-desc"]);
    document.getElementById("shown").textContent = shown.length;

    grid.innerHTML = "";
    var tbody = document.getElementById("tbody");
    tbody.innerHTML = "";

    if (!shown.length) {
      var e = el("div", "empty");
      e.appendChild(el("b", null, "No datasets match these filters."));
      e.appendChild(el("span", null, "Try clearing a filter or broadening your search."));
      grid.appendChild(e);
      return;
    }
    shown.forEach(function (d) {
      grid.appendChild(card(d));
      tbody.appendChild(row(d));
    });
  }

  // ---- permalinks -------------------------------------------------------
  // Cards are rendered by JS, so the browser's own anchor scroll on page load
  // fires before the target exists. Re-do it once the grid is in the DOM.
  function focusHash() {
    if (location.hash.indexOf("#dataset-") !== 0) return;
    var target = document.getElementById(location.hash.slice(1));
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---- wiring -----------------------------------------------------------
  document.getElementById("search").addEventListener("input", function (e) {
    state.q = e.target.value.trim().toLowerCase();
    render();
  });
  document.getElementById("sort").addEventListener("change", function (e) {
    sortKey = e.target.value;
    render();
  });
  document.getElementById("view-cards").addEventListener("click", function () { setView("cards"); });
  document.getElementById("view-table").addEventListener("click", function () { setView("table"); });
  document.getElementById("clear").addEventListener("click", function () {
    state.q = "";
    [state.tasks, state.mods, state.status, state.lic, state.country].forEach(function (s) { s.clear(); });
    document.getElementById("search").value = "";
    document.querySelectorAll(".chip[aria-pressed='true']").forEach(function (b) {
      b.setAttribute("aria-pressed", "false");
    });
    render();
  });

  setStats();
  setExoStats();
  buildFilters();
  setView(view);
  render();
  focusHash();
})();
