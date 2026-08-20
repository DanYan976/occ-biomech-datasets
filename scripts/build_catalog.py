#!/usr/bin/env python3
"""
Build the dataset catalog and the static pages derived from it.

Reads every datasets/*.yaml (ignoring files that start with "_"), validates each
against schema/dataset.schema.json, then:
  - writes site/catalog.json
  - injects the JSON into site/index.html, site/datasets.html and
    site/exoskeletons.html (CATALOG markers)
  - injects schema.org JSON-LD into site/datasets.html (JSONLD markers): a
    DataCatalog node referencing every released dataset's detail page
  - generates one detail page per dataset under site/datasets/<id>.html, each
    carrying its own schema.org Dataset node and a BibTeX citation
  - injects the controlled vocabularies into site/docs.html (VOCAB markers)
  - writes site/sitemap.xml

Also builds the model library: reads models/*.yaml, validates each against
schema/model.schema.json, writes site/models.json, and injects rendered cards
plus schema.org JSON-LD into site/models.html (MODELS / MODELS_JSONLD markers).

Run from the repo root:  python scripts/build_catalog.py
Requires: pyyaml, jsonschema  (pip install -r scripts/requirements.txt)

Set SITE_URL to the canonical origin when building for a different host, e.g.
  SITE_URL=https://occbiomechanics.netlify.app python scripts/build_catalog.py
"""
from __future__ import annotations
import datetime as _dt
import html
import json
import os
import re
import sys
from pathlib import Path


def _coerce_dates(obj):
    """YAML parses bare YYYY-MM-DD into date objects; the schema (and JSON) want
    strings. Convert recursively so contributors don't have to quote dates."""
    if isinstance(obj, dict):
        return {k: _coerce_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_dates(v) for v in obj]
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pyyaml. Run: pip install -r scripts/requirements.txt")

ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = ROOT / "datasets"
MODELS_DIR = ROOT / "models"
TOOLS_DIR = ROOT / "tools"
SCHEMA_PATH = ROOT / "schema" / "dataset.schema.json"
MODEL_SCHEMA_PATH = ROOT / "schema" / "model.schema.json"
TOOL_SCHEMA_PATH = ROOT / "schema" / "tool.schema.json"
SITE_DIR = ROOT / "site"
INDEX_HTML = SITE_DIR / "index.html"
DATASETS_HTML = SITE_DIR / "datasets.html"
EXOS_HTML = SITE_DIR / "exoskeletons.html"
MODELS_HTML = SITE_DIR / "models.html"
TOOLS_HTML = SITE_DIR / "tools.html"
DOCS_HTML = SITE_DIR / "docs.html"
CATALOG_JSON = SITE_DIR / "catalog.json"
MODELS_JSON = SITE_DIR / "models.json"
TOOLS_JSON = SITE_DIR / "tools.json"
DETAIL_DIR = SITE_DIR / "datasets"
SITEMAP_XML = SITE_DIR / "sitemap.xml"

MARK_START = "<!-- CATALOG:START -->"
MARK_END = "<!-- CATALOG:END -->"
JSONLD_START = "<!-- JSONLD:START -->"
JSONLD_END = "<!-- JSONLD:END -->"
VOCAB_START = "<!-- VOCAB:START -->"
VOCAB_END = "<!-- VOCAB:END -->"
MODELS_START = "<!-- MODELS:START -->"
MODELS_END = "<!-- MODELS:END -->"
MODELS_JSONLD_START = "<!-- MODELS_JSONLD:START -->"
MODELS_JSONLD_END = "<!-- MODELS_JSONLD:END -->"
TOOLS_START = "<!-- TOOLS:START -->"
TOOLS_END = "<!-- TOOLS:END -->"
TOOLS_JSONLD_START = "<!-- TOOLS_JSONLD:START -->"
TOOLS_JSONLD_END = "<!-- TOOLS_JSONLD:END -->"

# Canonical origin, used to mint stable @id values in the JSON-LD.
SITE_URL = os.environ.get("SITE_URL", "https://occbiomechanics.org").rstrip("/")

# open first, restricted next, coming_soon last
STATUS_ORDER = {"open": 0, "restricted": 1, "coming_soon": 2}
STATUS_LABEL = {"open": "Open", "restricted": "Restricted", "coming_soon": "Coming soon"}

TASK_LABEL = {
    "lifting": "Lifting", "lowering": "Lowering", "carrying": "Carrying",
    "pushing": "Pushing", "pulling": "Pulling", "holding": "Holding",
    "reaching": "Reaching", "squatting": "Squatting", "walking": "Walking",
    "assembly": "Assembly", "mmh": "MMH",
}
MOD_LABEL = {
    "mocap": "Mocap", "imu": "IMU", "emg": "EMG", "force_plate": "Force plate",
    "grf": "GRF", "video": "Video", "egocentric_video": "Egocentric video",
    "pose_estimation": "Pose est.", "pressure_insole": "Insole", "physiological": "Physio",
    "survey": "Survey",
}
EXO_ROLE_LABEL = {"evaluation": "Device evaluation", "control_input": "Exoskeleton-control data"}
EXO_REGION_LABEL = {
    "back": "Back", "shoulder": "Shoulder", "knee": "Knee", "hip": "Hip",
    "ankle": "Ankle", "neck": "Neck", "wrist": "Wrist", "full_body": "Full body",
}
EXO_ACTUATION_LABEL = {"passive": "Passive", "active": "Active", "quasi_passive": "Quasi-passive"}
EXO_OUTCOME_LABEL = {
    "muscle_activity": "Muscle activity (EMG)", "kinematics": "Kinematics",
    "kinetics": "Kinetics / assistive forces", "metabolic": "Metabolic cost",
    "cardiovascular": "Cardiovascular", "task_performance": "Task performance",
    "subjective": "Subjective ratings", "discomfort": "Discomfort / usability",
}

# Only SPDX-style ids we can resolve to a canonical deed. Anything else (free
# text like "cite Li et al. 2020") is emitted verbatim, which schema.org allows.
LICENSE_URLS = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-NC-4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC-BY-NC-SA-4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC-BY-ND-4.0": "https://creativecommons.org/licenses/by-nd/4.0/",
    "MIT": "https://opensource.org/license/mit",
}

# Trailing initials ("P.", "G.S.", "G.-J.") are what distinguishes a person in
# the author strings from a lab or university name.
_INITIALS = re.compile(r"\b[A-Z]\.(\s*-?\s*[A-Z]\.)*$")


def load_entries(directory: Path = DATASETS_DIR) -> list[dict]:
    entries = []
    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with path.open(encoding="utf-8") as fh:
            data = _coerce_dates(yaml.safe_load(fh))
        if not isinstance(data, dict):
            sys.exit(f"ERROR: {path.name} did not parse to a mapping.")
        data["_file"] = path.name
        entries.append(data)
    return entries


def validate(entries: list[dict], schema_path: Path = SCHEMA_PATH) -> None:
    try:
        import jsonschema
    except ImportError:
        print("WARNING: jsonschema not installed, skipping validation.")
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = 0
    for entry in entries:
        payload = {k: v for k, v in entry.items() if not k.startswith("_")}
        for err in validator.iter_errors(payload):
            loc = ".".join(str(p) for p in err.path) or "(root)"
            print(f"INVALID {entry.get('_file', '?')} :: {loc} :: {err.message}")
            errors += 1
    if errors:
        sys.exit(f"\n{errors} validation error(s). Fix the entries above and rebuild.")
    print(f"Validated {len(entries)} entries, no errors.")


def build_catalog(entries: list[dict]) -> dict:
    clean = []
    for e in sorted(entries, key=lambda x: (STATUS_ORDER.get(x.get("status"), 9), str(x.get("added", "")))):
        clean.append({k: v for k, v in e.items() if not k.startswith("_")})
    return {"generated_from": "datasets/*.yaml", "count": len(clean), "datasets": clean}


def detail_url(entry: dict) -> str:
    return f"{SITE_URL}/datasets/{entry['id']}.html"


# ---------------------------------------------------------------- JSON-LD ----

def _creators(authors: str) -> list[dict]:
    """Split an author string into schema.org agents. Every comma-separated part
    must look like a personal name before we claim they are people; a lab or
    university name falls back to a single Organization, which is never wrong."""
    parts = [p.strip() for p in authors.split(",") if p.strip()]
    if parts and all(_INITIALS.search(p) for p in parts):
        return [{"@type": "Person", "name": p} for p in parts]
    return [{"@type": "Organization", "name": authors.strip()}]


def _jsonld_entry(entry: dict, catalog_id: str) -> dict:
    access = entry.get("access") or {}
    source = entry.get("source") or {}
    node = {
        "@type": "Dataset",
        "@id": detail_url(entry),
        "name": entry["title"],
        "url": detail_url(entry),
        "includedInDataCatalog": {"@id": catalog_id},
        "creator": _creators(source["authors"]),
        "isAccessibleForFree": entry["status"] == "open",
    }
    if entry.get("description"):
        node["description"] = " ".join(entry["description"].split())
    if source.get("institution"):
        node["publisher"] = {"@type": "Organization", "name": source["institution"]}
    if source.get("year"):
        node["datePublished"] = str(source["year"])
    if access.get("doi"):
        node["identifier"] = f"https://doi.org/{access['doi']}"
    if access.get("url"):
        node["sameAs"] = access["url"]
    if access.get("license"):
        node["license"] = LICENSE_URLS.get(access["license"], access["license"])
    keywords = list(entry.get("tasks", [])) + list(entry.get("modalities", [])) + list(entry.get("tags", []))
    exo = entry.get("exoskeleton")
    if exo:
        keywords += ["exoskeleton"] + list(exo.get("devices", []))
    if keywords:
        node["keywords"] = sorted(set(keywords))
    if entry.get("modalities"):
        node["measurementTechnique"] = entry["modalities"]
    if entry.get("formats"):
        node["encodingFormat"] = entry["formats"]
    cites = []
    for p in entry.get("publications", []):
        cite = {"@type": "ScholarlyArticle", "name": p["citation"]}
        if p.get("doi"):
            cite["@id"] = f"https://doi.org/{p['doi']}"
        elif p.get("url"):
            cite["@id"] = p["url"]
        cites.append(cite)
    if cites:
        node["citation"] = cites
    return node


def released(entry: dict) -> bool:
    """Placeholder entries carry fake DOIs and coming_soon entries have no
    landing page or license yet; advertising either one in Dataset Search
    would point researchers at something they cannot obtain."""
    return not entry.get("sample") and entry["status"] != "coming_soon"


def catalog_jsonld(catalog: dict) -> dict:
    """DataCatalog node for datasets.html. Full Dataset nodes live on the
    detail pages, where Google prefers to find them."""
    catalog_id = f"{SITE_URL}/datasets.html#catalog"
    refs = [{"@id": detail_url(e)} for e in catalog["datasets"] if released(e)]
    return {
        "@context": "https://schema.org",
        "@type": "DataCatalog",
        "@id": catalog_id,
        "name": "OccBiomechanics",
        "url": f"{SITE_URL}/datasets.html",
        "description": (
            "A discovery catalog of motion capture, video, and wearable-sensor "
            "datasets of occupational tasks. Indexes metadata and links to each "
            "source; does not rehost data files."
        ),
        "publisher": {"@type": "Organization", "name": "AnyMotion Lab, New Jersey Institute of Technology"},
        "dataset": refs,
    }


# ------------------------------------------------------------ injections ----

def _inject(path: Path, start: str, end: str, block: str) -> None:
    if not path.exists():
        sys.exit(f"ERROR: {path} not found.")
    text = path.read_text(encoding="utf-8")
    if start not in text or end not in text:
        sys.exit(f"ERROR: {start} markers not found in {path.name}.")
    pre = text.split(start)[0]
    post = text.split(end)[1]
    path.write_text(pre + start + "\n" + block + "\n" + end + post, encoding="utf-8")


def inject_catalog(catalog: dict) -> None:
    payload = json.dumps(catalog, ensure_ascii=False, indent=2)
    block = f'<script id="catalog-data" type="application/json">\n{payload}\n</script>'
    for page in (INDEX_HTML, DATASETS_HTML, EXOS_HTML):
        _inject(page, MARK_START, MARK_END, block)


def inject_jsonld(catalog: dict) -> None:
    payload = json.dumps(catalog_jsonld(catalog), ensure_ascii=False, indent=2)
    block = f'<script type="application/ld+json">\n{payload}\n</script>'
    _inject(DATASETS_HTML, JSONLD_START, JSONLD_END, block)


def inject_vocab() -> None:
    """Render the controlled vocabularies from the schema into docs.html so the
    documentation can never drift from what validation actually accepts."""
    if not DOCS_HTML.exists():
        return
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    props = schema["properties"]
    tasks = props["tasks"]["items"]["enum"]
    mods = props["modalities"]["items"]["enum"]
    formats = props["formats"]["items"]["enum"]
    statuses = props["status"]["enum"]
    exo = props["exoskeleton"]["properties"]

    def codes(values):
        return " ".join(f'<code>{v}</code>' for v in values)

    block = (
        f'<dl class="detail-table">\n'
        f'  <dt>status</dt><dd>{codes(statuses)}</dd>\n'
        f'  <dt>tasks</dt><dd>{codes(tasks)}</dd>\n'
        f'  <dt>modalities</dt><dd>{codes(mods)}</dd>\n'
        f'  <dt>formats</dt><dd>{codes(formats)}</dd>\n'
        f'  <dt>exoskeleton.role</dt><dd>{codes(exo["role"]["enum"])}</dd>\n'
        f'  <dt>exoskeleton.body_region</dt><dd>{codes(exo["body_region"]["items"]["enum"])}</dd>\n'
        f'  <dt>exoskeleton.actuation</dt><dd>{codes(exo["actuation"]["items"]["enum"])}</dd>\n'
        f'  <dt>exoskeleton.outcomes</dt><dd>{codes(exo["outcomes"]["items"]["enum"])}</dd>\n'
        f'</dl>'
    )
    _inject(DOCS_HTML, VOCAB_START, VOCAB_END, block)


# ----------------------------------------------------------- detail pages ----

def _bibtex(entry: dict) -> str:
    source = entry.get("source") or {}
    access = entry.get("access") or {}

    def esc(s: str) -> str:
        return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")

    authors = source.get("authors", "")
    parts = [p.strip() for p in authors.split(",") if p.strip()]
    if parts and all(_INITIALS.search(p) for p in parts):
        names = []
        for p in parts:
            m = _INITIALS.search(p)
            names.append(f"{p[:m.start()].strip()}, {m.group(0)}")
        bib_authors = " and ".join(names)
    else:
        bib_authors = "{" + authors + "}"

    lines = [f"@misc{{{entry['id']},"]
    lines.append(f"  author = {{{esc(bib_authors)}}},")
    lines.append(f"  title  = {{{{{esc(entry['title'])}}}}},")
    if source.get("year"):
        lines.append(f"  year   = {{{source['year']}}},")
    if access.get("doi"):
        lines.append(f"  doi    = {{{access['doi']}}},")
    if access.get("url"):
        lines.append(f"  url    = {{{access['url']}}},")
    lines.append("}")
    return "\n".join(lines)


def _detail_page(entry: dict) -> str:
    e = html.escape
    source = entry.get("source") or {}
    access = entry.get("access") or {}
    subj = entry.get("subjects") or {}
    status = entry["status"]
    desc = " ".join((entry.get("description") or "").split())
    url = detail_url(entry)

    jsonld = ""
    if released(entry):
        node = _jsonld_entry(entry, f"{SITE_URL}/datasets.html#catalog")
        node["@context"] = "https://schema.org"
        jsonld = ('<script type="application/ld+json">\n'
                  + json.dumps(node, ensure_ascii=False, indent=2)
                  + "\n</script>\n")

    tags_html = "".join(
        f'<span class="tag mod">{e(MOD_LABEL.get(m, m))}</span>' for m in entry.get("modalities", [])
    ) + "".join(
        f'<span class="tag">{e(TASK_LABEL.get(t, t))}</span>' for t in entry.get("tasks", [])
    )

    if status != "coming_soon" and access.get("url"):
        action = f'<a class="btn primary" href="{e(access["url"])}" target="_blank" rel="noopener">View source ↗</a>'
    else:
        action = '<span class="pending">Release pending</span>'
    doi_html = ""
    if access.get("doi"):
        doi_html = (f'<span class="lic">DOI: <a href="https://doi.org/{e(access["doi"])}" target="_blank" '
                    f'rel="noopener">{e(access["doi"])}</a></span>')

    subj_bits = []
    if subj.get("n"):
        subj_bits.append(f"n = {subj['n']}")
    if subj.get("sex"):
        subj_bits.append(e(subj["sex"]))
    if subj.get("age_range"):
        subj_bits.append(e(subj["age_range"]))

    rows = []

    def row(label, value_html):
        if value_html:
            rows.append(f"  <dt>{label}</dt><dd>{value_html}</dd>")

    # Exoskeleton block: its own section, so evaluations can be read device-first.
    exo = entry.get("exoskeleton") or {}
    exo_rows = []

    def exo_row(label, value_html):
        if value_html:
            exo_rows.append(f"  <dt>{label}</dt><dd>{value_html}</dd>")

    exo_row("Record type", e(EXO_ROLE_LABEL.get(exo.get("role"), exo.get("role", ""))))
    exo_row("Device(s)", ", ".join(e(d) for d in exo.get("devices", [])))
    exo_row("Body region", ", ".join(e(EXO_REGION_LABEL.get(r, r)) for r in exo.get("body_region", [])))
    exo_row("Actuation", ", ".join(e(EXO_ACTUATION_LABEL.get(a, a)) for a in exo.get("actuation", [])))
    exo_row("Study design", e(exo.get("comparison", "")))
    exo_row("Outcomes", ", ".join(e(EXO_OUTCOME_LABEL.get(o, o)) for o in exo.get("outcomes", [])))

    exo_section = ""
    exo_badge = ""
    if exo_rows:
        exo_section = ('<h2>Exoskeleton</h2>\n  <dl class="detail-table">\n'
                       + "\n".join(exo_rows)
                       + '\n  </dl>\n  <p class="gov">This record is part of the '
                         '<a href="/exoskeletons.html">exoskeleton collection</a>.</p>\n\n  ')
        label = "Exo evaluation" if exo.get("role") == "evaluation" else "Exo-control data"
        exo_badge = f' <span class="badge exo">{label}</span>'

    row("Subjects", " · ".join(subj_bits))
    row("Protocol / load", e(entry.get("load", "")))
    row("Equipment", e(entry.get("equipment", "")))
    if entry.get("sampling"):
        row("Sampling", " · ".join(f"{e(k)} {v}&nbsp;Hz" for k, v in entry["sampling"].items()))
    row("Formats", ", ".join(f"<code>{e(f)}</code>" for f in entry.get("formats", [])))
    row("License", e(access.get("license", "")) or ("TBD" if status == "coming_soon" else ""))
    row("Keywords", ", ".join(e(t) for t in entry.get("tags", [])))
    row("Added to catalog", e(str(entry.get("added", ""))))
    details = "\n".join(rows)

    pubs_section = ""
    pubs = entry.get("publications") or []
    if pubs:
        items = []
        for p in pubs:
            link = p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")
            cite = e(p["citation"])
            if link:
                cite = f'<a href="{e(link)}" target="_blank" rel="noopener">{cite}</a>'
            note = f'<span class="pub-note">{e(p["note"])}</span>' if p.get("note") else ""
            items.append(f"    <li>{cite}{note}</li>")
        pubs_section = ('<h2>Publications</h2>\n  <ul class="pub-list">\n'
                        + "\n".join(items)
                        + '\n  </ul>\n\n  ')

    authors_line = f'<p class="src">{e(source.get("authors", ""))}</p>' if source.get("authors") else ""
    inst_line = " · ".join(str(x) for x in [source.get("institution"), source.get("year")] if x)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{e(entry['title'])} — OccBiomechanics</title>
<meta name="description" content="{e(desc)}" />
<link rel="canonical" href="{e(url)}" />
<link rel="icon" type="image/svg+xml" href="/favicon.svg?v=20260812" />
<meta name="theme-color" content="#0F766E" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="OccBiomechanics" />
<meta property="og:title" content="{e(entry['title'])}" />
<meta property="og:description" content="{e(desc)}" />
<meta property="og:url" content="{e(url)}" />
<meta property="og:image" content="{SITE_URL}/og-image.png" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{e(entry['title'])}" />
<meta name="twitter:description" content="{e(desc)}" />
<meta name="twitter:image" content="{SITE_URL}/og-image.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/style.css?v=20260819" />
<script src="/nav.js" defer></script>
{jsonld}</head>
<body>

<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/">
      <img class="mark" src="/assets/logo.svg" alt="" />
      <span class="name">OccBiomechanics</span>
    </a>
    <nav class="nav">
      <a href="/index.html">Home</a>
      <div class="dropdown">
        <button type="button" class="dropdown-toggle active" aria-haspopup="true" aria-expanded="false">Libraries</button>
        <div class="dropdown-menu">
          <a href="/datasets.html" class="active">All Datasets</a>
          <a href="/exoskeletons.html">Exoskeleton Studies</a>
          <a href="/models.html">Models</a>
          <a href="/tools.html">Tools</a>
        </div>
      </div>
      <a href="/docs.html">Docs</a>
      <a href="/contribute.html">Contribute</a>
      <a href="/community.html">Community</a>
      <a href="#about">About</a>
    </nav>
  </div>
</header>

<main class="wrap detail">
  <p class="crumb"><a href="/datasets.html">← All datasets</a></p>

  <div class="detail-head">
    <div class="dmeta"><span class="cid">{e(entry['id'])}</span> <span class="badge {e(status)}">{e(STATUS_LABEL.get(status, status))}</span>{exo_badge}</div>
    <h1>{e(entry['title'])}</h1>
    {authors_line}
    <p class="src">{e(inst_line)}</p>
  </div>

  <p class="desc">{e(desc)}</p>
  <div class="tags">{tags_html}</div>
  <div class="cta-row">{action}{doi_html}</div>

  <h2>Details</h2>
  <dl class="detail-table">
{details}
  </dl>

  {pubs_section}{exo_section}<h2>Cite</h2>
  <p class="gov">Cite the dataset as its authors request (check the source page for an official citation); this BibTeX is a convenience starting point.</p>
  <div class="citebox">
    <pre id="bibtex">{e(_bibtex(entry))}</pre>
    <button class="btn" id="copybib" type="button">Copy BibTeX</button>
  </div>
</main>

<footer class="site-footer" id="about">
  <div class="wrap">
    <div class="eyebrow">About this catalog</div>
    <p class="gov">This is a discovery index for the occupational biomechanics community — human-motion datasets today, with models and open-source analysis tools being added. Each entry describes a resource and links to its original source; listing is descriptive and is not an endorsement. Datasets keep their own licenses, and access terms are set by their authors. The catalog is maintained by the <a href="https://sites.google.com/view/weiyin-njit">AnyMotion Lab</a>.</p>
    <p>Know a dataset, model, or tool we should list — or want to work together? See <a href="/contribute.html">how to contribute</a>, or email the link and a short description and we will add it.</p>
    <p>Machine-readable: <a href="/catalog.json">catalog.json</a> · <a href="/docs.html">schema &amp; API docs</a></p>
    <p>A project of <a href="https://sites.google.com/view/weiyin-njit"><strong>AnyMotion Lab</strong></a> · New Jersey Institute of Technology</p>
    <p>Site code: MIT · Catalog metadata: CC0 · contact: <a href="mailto:dy266@njit.edu">dy266@njit.edu</a></p>
  </div>
</footer>

<script>
document.getElementById("copybib").addEventListener("click", function () {{
  var btn = this;
  navigator.clipboard.writeText(document.getElementById("bibtex").textContent).then(function () {{
    btn.textContent = "Copied ✓";
    setTimeout(function () {{ btn.textContent = "Copy BibTeX"; }}, 1600);
  }});
}});
</script>
</body>
</html>
"""


def build_detail_pages(catalog: dict) -> None:
    DETAIL_DIR.mkdir(exist_ok=True)
    wanted = set()
    for entry in catalog["datasets"]:
        name = f"{entry['id']}.html"
        wanted.add(name)
        (DETAIL_DIR / name).write_text(_detail_page(entry), encoding="utf-8")
    for stale in DETAIL_DIR.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
            print(f"  -> removed stale detail page {stale.name}")
    print(f"  -> {len(wanted)} detail pages in site/datasets/")


# ------------------------------------------------------------ model library ----

def _model_link_row(links: dict) -> str:
    """Outbound links for a model card, primary source first."""
    e = html.escape
    parts = []
    if links.get("paper"):
        parts.append(f'<a class="out" href="{e(links["paper"])}" target="_blank" rel="noopener">Paper ↗</a>')
    if links.get("code"):
        parts.append(f'<a class="out" href="{e(links["code"])}" target="_blank" rel="noopener">Code ↗</a>')
    if links.get("preprint"):
        parts.append(f'<a class="out" href="{e(links["preprint"])}" target="_blank" rel="noopener">Preprint ↗</a>')
    if links.get("record"):
        parts.append(f'<a class="out" href="{e(links["record"])}" target="_blank" rel="noopener">Record ↗</a>')
    return '<span style="display:flex;gap:14px;flex-wrap:wrap">' + "".join(parts) + "</span>"


def _model_card(m: dict) -> str:
    e = html.escape
    source = m.get("source") or {}
    links = m.get("links") or {}
    has_code = bool(links.get("code"))
    badge = ('<span class="badge open">Code</span>' if has_code
             else '<span class="badge restricted">Paper only</span>')
    primary = links.get("code") or links.get("paper") or links.get("record") or ""
    src_line = " · ".join(str(x) for x in [source.get("institution"), source.get("year")] if x)
    desc = " ".join((m.get("description") or "").split())

    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in m.get("tags", []))

    metrics = []
    for label, value in (("Input", m.get("inputs")), ("Output", m.get("outputs")), ("Domain", m.get("domain"))):
        if value:
            metrics.append(f'<div class="metric"><span class="k">{label}</span>'
                           f'<span class="v" title="{e(value)}">{e(value)}</span></div>')

    lic = m.get("code_license") or ("—" if has_code else "No code released")

    return f"""<article class="card" id="model-{e(m['id'])}">
  <div class="card-top">
    <div><span class="cid">{e(m['id'])}</span></div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">{badge}</div>
  </div>
  <h3><a class="title-link" href="{e(primary)}" target="_blank" rel="noopener">{e(m['title'])}</a></h3>
  <div class="src">{e(src_line)}</div>
  <p class="desc">{e(desc)}</p>
  <div class="tags">{tags}</div>
  <div class="metrics">{''.join(metrics)}</div>
  <div class="card-foot">
    <span class="lic">{e(lic)}</span>
    {_model_link_row(links)}
  </div>
</article>"""


def models_jsonld(models: list[dict]) -> dict:
    """One node per model: SoftwareSourceCode when code is released, otherwise
    ScholarlyArticle — so Google indexes each for what it actually is."""
    nodes = []
    for m in models:
        if m.get("sample"):
            continue
        source = m.get("source") or {}
        links = m.get("links") or {}
        has_code = bool(links.get("code"))
        node = {
            "@type": "SoftwareSourceCode" if has_code else "ScholarlyArticle",
            "@id": f"{SITE_URL}/models.html#model-{m['id']}",
            "name": m["title"],
            "url": links.get("code") or links.get("paper"),
            "creator": _creators(source.get("authors", "")),
        }
        if m.get("description"):
            node["description"] = " ".join(m["description"].split())
        if source.get("year"):
            node["datePublished"] = str(source["year"])
        if links.get("doi"):
            node["identifier"] = f"https://doi.org/{links['doi']}"
        if has_code:
            node["codeRepository"] = links["code"]
            if m.get("code_license"):
                node["license"] = LICENSE_URLS.get(m["code_license"], m["code_license"])
            if links.get("paper"):
                node["citation"] = {"@type": "ScholarlyArticle", "@id": f"https://doi.org/{links['doi']}" if links.get("doi") else links["paper"]}
        elif links.get("record"):
            node["sameAs"] = links["record"]
        if m.get("tags"):
            node["keywords"] = sorted(set(m["tags"]))
        nodes.append(node)
    return {"@context": "https://schema.org", "@graph": nodes}


def build_models(models: list[dict]) -> None:
    models = sorted(models, key=lambda m: (str(m.get("added", "")), m["id"]), reverse=True)
    clean = [{k: v for k, v in m.items() if not k.startswith("_")} for m in models]
    MODELS_JSON.write_text(
        json.dumps({"generated_from": "models/*.yaml", "count": len(clean), "models": clean},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")

    n = len(models)
    cards = "\n".join(_model_card(m) for m in models)
    block = (f'<section class="exo-group">\n'
             f'  <div class="section-head"><h2>All models</h2>'
             f'<span class="count-note">{n} {"model" if n == 1 else "models"}</span></div>\n'
             f'  <div class="grid">\n{cards}\n  </div>\n'
             f'</section>')
    _inject(MODELS_HTML, MODELS_START, MODELS_END, block)

    jsonld = json.dumps(models_jsonld(models), ensure_ascii=False, indent=2)
    _inject(MODELS_HTML, MODELS_JSONLD_START, MODELS_JSONLD_END,
            f'<script type="application/ld+json">\n{jsonld}\n</script>')
    print(f"  -> {MODELS_JSON.relative_to(ROOT)}; {n} model cards + JSON-LD injected into models.html")


# ------------------------------------------------------------- tool library ----

LICENSING_LABEL = {"commercial": "Commercial", "free": "Free", "open_source": "Open source"}


def _tool_link_row(links: dict, patents: list[dict]) -> str:
    """Outbound links for a tool card: vendor page first, then patents."""
    e = html.escape
    parts = []
    if links.get("website"):
        parts.append(f'<a class="out" href="{e(links["website"])}" target="_blank" rel="noopener">Website ↗</a>')
    if links.get("docs"):
        parts.append(f'<a class="out" href="{e(links["docs"])}" target="_blank" rel="noopener">Docs ↗</a>')
    if links.get("paper"):
        parts.append(f'<a class="out" href="{e(links["paper"])}" target="_blank" rel="noopener">Paper ↗</a>')
    if links.get("record"):
        parts.append(f'<a class="out" href="{e(links["record"])}" target="_blank" rel="noopener">Record ↗</a>')
    for p in patents:
        label = e(p["number"])
        if p.get("url"):
            parts.append(f'<a class="out" href="{e(p["url"])}" target="_blank" rel="noopener" title="{e(p.get("title", ""))}">{label} ↗</a>')
        else:
            parts.append(f'<span class="lic" title="{e(p.get("title", ""))}">{label}</span>')
    return '<span style="display:flex;gap:14px;flex-wrap:wrap">' + "".join(parts) + "</span>"


def _tool_card(t: dict) -> str:
    e = html.escape
    source = t.get("source") or {}
    links = t.get("links") or {}
    licensing = t.get("licensing", "")
    badge_cls = "open" if licensing in ("free", "open_source") else "restricted"
    badge = f'<span class="badge {badge_cls}">{e(LICENSING_LABEL.get(licensing, licensing) or "Tool")}</span>'
    primary = links.get("website") or links.get("record") or links.get("paper") or ""
    src_line = " · ".join(str(x) for x in [source.get("institution"), source.get("year")] if x)
    desc = " ".join((t.get("description") or "").split())

    tags = "".join(f'<span class="tag">{e(x)}</span>' for x in t.get("tags", []))

    metrics = []
    for label, value in (("Vendor", t.get("vendor")), ("Input", t.get("inputs")),
                         ("Output", t.get("outputs")), ("Category", t.get("category"))):
        if value:
            metrics.append(f'<div class="metric"><span class="k">{label}</span>'
                           f'<span class="v" title="{e(value)}">{e(value)}</span></div>')

    related = ""
    if t.get("related_models"):
        rel_links = ", ".join(f'<a href="models.html#model-{e(r)}">{e(r)}</a>' for r in t["related_models"])
        related = f'<div class="src">Built on: {rel_links}</div>'

    lic = t.get("pricing_note") or LICENSING_LABEL.get(licensing, "")

    return f"""<article class="card" id="tool-{e(t['id'])}">
  <div class="card-top">
    <div><span class="cid">{e(t['id'])}</span></div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">{badge}</div>
  </div>
  <h3><a class="title-link" href="{e(primary)}" target="_blank" rel="noopener">{e(t['title'])}</a></h3>
  <div class="src">{e(src_line)}</div>
  <p class="desc">{e(desc)}</p>
  <div class="tags">{tags}</div>
  <div class="metrics">{''.join(metrics)}</div>
  {related}
  <div class="card-foot">
    <span class="lic">{e(lic)}</span>
    {_tool_link_row(links, t.get("patents", []))}
  </div>
</article>"""


def tools_jsonld(tools: list[dict]) -> dict:
    """One SoftwareApplication node per tool — the schema.org type for a
    product you obtain and run, as opposed to a published method."""
    nodes = []
    for t in tools:
        if t.get("sample"):
            continue
        source = t.get("source") or {}
        links = t.get("links") or {}
        node = {
            "@type": "SoftwareApplication",
            "@id": f"{SITE_URL}/tools.html#tool-{t['id']}",
            "name": t["title"],
            "url": links.get("website") or links.get("record") or links.get("paper"),
            "publisher": {"@type": "Organization", "name": t["vendor"]},
            "applicationCategory": t.get("category") or "Ergonomics analysis software",
        }
        if source.get("authors"):
            node["creator"] = _creators(source["authors"])
        if t.get("description"):
            node["description"] = " ".join(t["description"].split())
        if links.get("doi"):
            node["identifier"] = f"https://doi.org/{links['doi']}"
        same_as = [p["url"] for p in t.get("patents", []) if p.get("url")]
        if same_as:
            node["sameAs"] = same_as
        if t.get("tags"):
            node["keywords"] = sorted(set(t["tags"]))
        nodes.append(node)
    return {"@context": "https://schema.org", "@graph": nodes}


def build_tools(tools: list[dict]) -> None:
    tools = sorted(tools, key=lambda t: (str(t.get("added", "")), t["id"]), reverse=True)
    clean = [{k: v for k, v in t.items() if not k.startswith("_")} for t in tools]
    TOOLS_JSON.write_text(
        json.dumps({"generated_from": "tools/*.yaml", "count": len(clean), "tools": clean},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")

    n = len(tools)
    cards = "\n".join(_tool_card(t) for t in tools)
    block = (f'<section class="exo-group">\n'
             f'  <div class="section-head"><h2>All tools</h2>'
             f'<span class="count-note">{n} {"tool" if n == 1 else "tools"}</span></div>\n'
             f'  <div class="grid">\n{cards}\n  </div>\n'
             f'</section>')
    _inject(TOOLS_HTML, TOOLS_START, TOOLS_END, block)

    jsonld = json.dumps(tools_jsonld(tools), ensure_ascii=False, indent=2)
    _inject(TOOLS_HTML, TOOLS_JSONLD_START, TOOLS_JSONLD_END,
            f'<script type="application/ld+json">\n{jsonld}\n</script>')
    print(f"  -> {TOOLS_JSON.relative_to(ROOT)}; {n} tool cards + JSON-LD injected into tools.html")


# ---------------------------------------------------------------- sitemap ----

def build_sitemap(catalog: dict) -> None:
    urls = [(f"{SITE_URL}/", None), (f"{SITE_URL}/datasets.html", None),
            (f"{SITE_URL}/exoskeletons.html", None), (f"{SITE_URL}/models.html", None),
            (f"{SITE_URL}/tools.html", None), (f"{SITE_URL}/docs.html", None),
            (f"{SITE_URL}/contribute.html", None),
            (f"{SITE_URL}/community.html", None)]
    for entry in catalog["datasets"]:
        urls.append((detail_url(entry), str(entry.get("added")) if entry.get("added") else None))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{html.escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    SITEMAP_XML.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  -> sitemap.xml ({len(urls)} URLs)")


# ------------------------------------------------------------------- main ----

def main() -> None:
    entries = load_entries()
    if not entries:
        sys.exit("No dataset entries found in datasets/*.yaml.")
    validate(entries)
    catalog = build_catalog(entries)
    SITE_DIR.mkdir(exist_ok=True)
    CATALOG_JSON.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    inject_catalog(catalog)
    inject_jsonld(catalog)
    inject_vocab()
    build_detail_pages(catalog)
    build_sitemap(catalog)
    models = load_entries(MODELS_DIR) if MODELS_DIR.exists() else []
    if models:
        validate(models, MODEL_SCHEMA_PATH)
        build_models(models)
    tools = load_entries(TOOLS_DIR) if TOOLS_DIR.exists() else []
    if tools:
        validate(tools, TOOL_SCHEMA_PATH)
        build_tools(tools)
    n = catalog["count"]
    by_status = {}
    for d in catalog["datasets"]:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
    skipped = [d["id"] for d in catalog["datasets"] if not released(d)]
    print(f"Built catalog: {n} datasets {dict(by_status)}")
    print(f"  -> {CATALOG_JSON.relative_to(ROOT)}")
    print(f"  -> catalog JSON injected into index.html + datasets.html + exoskeletons.html")
    if skipped:
        print(f"  -> JSON-LD skipped {len(skipped)} unreleased/placeholder: {', '.join(skipped)}")
    print(f"  -> JSON-LD DataCatalog on datasets.html; Dataset nodes on detail pages ({SITE_URL})")


if __name__ == "__main__":
    main()
