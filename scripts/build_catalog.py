#!/usr/bin/env python3
"""
Build the dataset catalog and the static pages derived from it.

Reads every datasets/*.yaml (ignoring files that start with "_"), validates each
against schema/dataset.schema.json, then:
  - writes site/catalog.json
  - injects the JSON into site/index.html and site/datasets.html (CATALOG markers)
  - injects schema.org JSON-LD into site/datasets.html (JSONLD markers): a
    DataCatalog node referencing every released dataset's detail page
  - generates one detail page per dataset under site/datasets/<id>.html, each
    carrying its own schema.org Dataset node and a BibTeX citation
  - injects the controlled vocabularies into site/docs.html (VOCAB markers)
  - writes site/sitemap.xml

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
SCHEMA_PATH = ROOT / "schema" / "dataset.schema.json"
SITE_DIR = ROOT / "site"
INDEX_HTML = SITE_DIR / "index.html"
DATASETS_HTML = SITE_DIR / "datasets.html"
DOCS_HTML = SITE_DIR / "docs.html"
CATALOG_JSON = SITE_DIR / "catalog.json"
DETAIL_DIR = SITE_DIR / "datasets"
SITEMAP_XML = SITE_DIR / "sitemap.xml"

MARK_START = "<!-- CATALOG:START -->"
MARK_END = "<!-- CATALOG:END -->"
JSONLD_START = "<!-- JSONLD:START -->"
JSONLD_END = "<!-- JSONLD:END -->"
VOCAB_START = "<!-- VOCAB:START -->"
VOCAB_END = "<!-- VOCAB:END -->"

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


def load_entries() -> list[dict]:
    entries = []
    for path in sorted(DATASETS_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with path.open(encoding="utf-8") as fh:
            data = _coerce_dates(yaml.safe_load(fh))
        if not isinstance(data, dict):
            sys.exit(f"ERROR: {path.name} did not parse to a mapping.")
        data["_file"] = path.name
        entries.append(data)
    return entries


def validate(entries: list[dict]) -> None:
    try:
        import jsonschema
    except ImportError:
        print("WARNING: jsonschema not installed, skipping validation.")
        return
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
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
    if keywords:
        node["keywords"] = sorted(set(keywords))
    if entry.get("modalities"):
        node["measurementTechnique"] = entry["modalities"]
    if entry.get("formats"):
        node["encodingFormat"] = entry["formats"]
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
        "name": "ErgoBiomech",
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
    for page in (INDEX_HTML, DATASETS_HTML):
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

    def codes(values):
        return " ".join(f'<code>{v}</code>' for v in values)

    block = (
        f'<dl class="detail-table">\n'
        f'  <dt>status</dt><dd>{codes(statuses)}</dd>\n'
        f'  <dt>tasks</dt><dd>{codes(tasks)}</dd>\n'
        f'  <dt>modalities</dt><dd>{codes(mods)}</dd>\n'
        f'  <dt>formats</dt><dd>{codes(formats)}</dd>\n'
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

    authors_line = f'<p class="src">{e(source.get("authors", ""))}</p>' if source.get("authors") else ""
    inst_line = " · ".join(str(x) for x in [source.get("institution"), source.get("year")] if x)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{e(entry['title'])} — ErgoBiomech</title>
<meta name="description" content="{e(desc)}" />
<link rel="canonical" href="{e(url)}" />
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<meta name="theme-color" content="#0F766E" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="ErgoBiomech" />
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
<link rel="stylesheet" href="/style.css" />
{jsonld}</head>
<body>

<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/">
      <span class="mark">EB</span>
      <span class="name">ErgoBiomech</span>
    </a>
    <nav class="nav">
      <a href="/datasets.html" class="active">Datasets</a>
      <a href="/docs.html">Docs</a>
      <a href="#about">About</a>
    </nav>
  </div>
</header>

<main class="wrap detail">
  <p class="crumb"><a href="/datasets.html">← All datasets</a></p>

  <div class="detail-head">
    <div class="dmeta"><span class="cid">{e(entry['id'])}</span> <span class="badge {e(status)}">{e(STATUS_LABEL.get(status, status))}</span></div>
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

  <h2>Cite</h2>
  <p class="gov">Cite the dataset as its authors request (check the source page for an official citation); this BibTeX is a convenience starting point.</p>
  <div class="citebox">
    <pre id="bibtex">{e(_bibtex(entry))}</pre>
    <button class="btn" id="copybib" type="button">Copy BibTeX</button>
  </div>
</main>

<footer class="site-footer" id="about">
  <div class="wrap">
    <div class="eyebrow">About this catalog</div>
    <p class="gov">This is a discovery index for the occupational biomechanics community. Each entry describes a dataset and links to its original source; listing is descriptive and is not an endorsement. Datasets keep their own licenses, and access terms are set by their authors. The catalog is maintained by the AnyMotion Lab.</p>
    <p>Know a public dataset we should list? Email us the link and a short description, and we will add it.</p>
    <p>Machine-readable: <a href="/catalog.json">catalog.json</a> · <a href="/docs.html">schema &amp; API docs</a></p>
    <p>A project of <strong>AnyMotion Lab</strong> · New Jersey Institute of Technology</p>
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


# ---------------------------------------------------------------- sitemap ----

def build_sitemap(catalog: dict) -> None:
    urls = [(f"{SITE_URL}/", None), (f"{SITE_URL}/datasets.html", None), (f"{SITE_URL}/docs.html", None)]
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
    n = catalog["count"]
    by_status = {}
    for d in catalog["datasets"]:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
    skipped = [d["id"] for d in catalog["datasets"] if not released(d)]
    print(f"Built catalog: {n} datasets {dict(by_status)}")
    print(f"  -> {CATALOG_JSON.relative_to(ROOT)}")
    print(f"  -> catalog JSON injected into index.html + datasets.html")
    if skipped:
        print(f"  -> JSON-LD skipped {len(skipped)} unreleased/placeholder: {', '.join(skipped)}")
    print(f"  -> JSON-LD DataCatalog on datasets.html; Dataset nodes on detail pages ({SITE_URL})")


if __name__ == "__main__":
    main()
