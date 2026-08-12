# OccBiomechanics

**Human-motion datasets, models, and analysis tools for occupational tasks,
indexed in one place** — by the
[AnyMotion Lab](https://sites.google.com/view/weiyin-njit) at NJIT. Published at
[occbiomechanics.org](https://occbiomechanics.org).

A discovery catalog for **occupational biomechanics**: lab-based motion capture,
video, and wearable-sensor recordings of work tasks such as lifting, carrying,
and manual materials handling (MMH), with a dedicated collection for
**occupational exoskeleton** studies.

The catalog **indexes metadata and links out to each dataset's source**. It does
not rehost data files. Listing is descriptive, not an endorsement, and every
dataset keeps its own license and access terms.

### Where this is going

1. **Now** — gather what exists: datasets, models, and analysis tools under one
   schema, so they can be found and compared.
2. **Next** — develop and publish our own open-source analysis tools, with the
   datasets they were validated on.
3. **Long term** — a community resource supporting exoskeleton evaluation
   standards and reproducible occupational biomechanics analysis.

Contributions are welcome: dataset submissions, models and tools, fixes to
existing records, exoskeleton evaluation partners, and joint research. See
[Contribute](https://occbiomechanics.org/contribute.html) (or `CONTRIBUTING.md`
in this repo), meet the core team on the
[Community page](https://occbiomechanics.org/community.html), or email
<dy266@njit.edu>.

---

## How it works

```
datasets/*.yaml   →   scripts/build_catalog.py   →   site/ (static, filterable)
   (source of         (validates against              (deploys to GitHub Pages)
    truth, one          schema, compiles JSON
    file per            into the catalog pages +
    dataset)            one detail page each)
```

Data lives as one YAML file per dataset, so every change is a reviewable pull
request. The build validates each entry against `schema/dataset.schema.json`,
then injects the compiled catalog into the page. The site filters entirely on
the client, so no server or database is needed.

## Repo layout

```
occ-biomech-datasets/
├── datasets/                 # one YAML per dataset (source of truth)
│   ├── _template.yaml        # copy this to add a dataset (files starting "_" are ignored)
│   └── *.yaml
├── schema/
│   └── dataset.schema.json   # field definitions + controlled vocabularies
├── scripts/
│   ├── build_catalog.py      # validate + compile
│   └── requirements.txt
├── site/                     # the published site
│   ├── index.html            # landing page: stats, roadmap, contribute teaser
│   ├── datasets.html         # full catalog with filters and table view
│   ├── exoskeletons.html     # exoskeleton collection, grouped by body region
│   ├── docs.html             # schema, vocabularies, JSON API
│   ├── contribute.html       # how to propose, fix, and review records
│   ├── community.html        # core team and contributors
│   ├── datasets/<id>.html    # generated, one page per dataset
│   ├── assets/team/          # core-team headshots
│   ├── style.css
│   ├── nav.js                # header nav dropdown behavior
│   ├── app.js                # search + filter logic (all three views)
│   └── catalog.json          # generated
└── .github/workflows/deploy.yml  # build + deploy to GitHub Pages
```

## Add a dataset

1. Copy `datasets/_template.yaml` to `datasets/<your-id>.yaml`.
2. Fill in the fields (see `schema/dataset.schema.json` for allowed values).
3. Rebuild and open a pull request. See `CONTRIBUTING.md`.

## Build and preview locally

New to this? See `QUICKSTART.md` for a step-by-step walkthrough with a venv and
troubleshooting. The short version:

```bash
pip install -r scripts/requirements.txt
python scripts/build_catalog.py            # validate + compile
python -m http.server -d site 8000         # then open http://localhost:8000
```

You can also just open `site/index.html` directly; the catalog data is embedded
in the page, so it renders without a server.

## Deploy (GitHub Pages)

The site is live at [occbiomechanics.org](https://occbiomechanics.org). Every
push to `main` triggers `.github/workflows/deploy.yml`, which runs the build and
publishes `site/` via GitHub Pages — so a merged pull request is deployed
automatically, with no separate release step.

Note for maintainers: the header/footer of the generated dataset detail pages
comes from the HTML template inside `scripts/build_catalog.py`. Site-wide chrome
changes (nav, footer) must be made both in the hand-written pages under `site/`
and in that template, then rebuilt.

## Metadata standards

The schema is deliberately close to
[schema.org/Dataset](https://schema.org/Dataset), and the build emits JSON-LD
into the page so entries are discoverable through Google Dataset Search. Only
released, real datasets are described: placeholder entries carry fake DOIs and
`coming_soon` entries have no landing page yet, so advertising either would send
researchers after something they cannot obtain. The markup points `url` at each
dataset's own home and marks the page as a `DataCatalog`, matching what the
catalog actually is — an index, not a host. It also maps
cleanly onto [Croissant](https://mlcommons.org/croissant/) (MLCommons) if you
later want ML-ready, framework-loadable descriptions. Domain fields (tasks,
modalities, load, sampling) extend that base for occupational biomechanics.

## Exoskeleton records

Records that involve an occupational exoskeleton carry an extra `exoskeleton`
object, which drives the exoskeleton filters on `datasets.html` and the grouping
on `exoskeletons.html`:

```yaml
exoskeleton:
  role: evaluation            # evaluation | control_input
  devices: ["Laevo V2.5"]
  body_region: [back]         # back | shoulder | knee | hip | ankle | neck | wrist | full_body
  actuation: [passive]        # passive | active | quasi_passive
  comparison: "With vs. without the exoskeleton, within-subject"
  outcomes: [muscle_activity, kinematics, cardiovascular]
```

`role: evaluation` means a device was worn and its effect measured;
`role: control_input` means the data were collected to develop or control an
exoskeleton, with no device worn during capture. Datasets with no exoskeleton
connection omit the object entirely. `outcomes` is the field that makes
evaluations comparable — and makes the gaps between them visible.

## About the entries

`njit-*` entries are the lab's own planned datasets, marked `coming_soon` until
release. Everything else is a published dataset indexed from its original source;
check each record's `access.license` before use, since terms vary from CC0 to
non-commercial to data-on-request.

## Core team

- [Wei Yin](https://people.njit.edu/profile/wy37) — NJIT; directs the
  [AnyMotion Lab](https://sites.google.com/view/weiyin-njit), which maintains
  this catalog
- [Yangming Shi](https://cee.mines.edu/project/shi-yangming/) — Colorado School
  of Mines
- [Xianlian Zhou](https://people.njit.edu/profile/alexzhou) — NJIT
- [Xudong Zhang](https://engineering.tamu.edu/industrial/profiles/zhang-xudong.html)
  — Texas A&M University

More on the [Community page](https://occbiomechanics.org/community.html).

## Licensing

- **Site code:** MIT (see `LICENSE`).
- **Catalog metadata** (the YAML you write): CC0 recommended.
- **Datasets themselves:** keep their own licenses; the catalog only points to them.

Because the catalog links out rather than rehosting, indexing a dataset carries
no redistribution risk. But **using** the underlying data means honoring each
dataset's own terms: give attribution where required, respect **non-commercial
(NC)** restrictions, and for datasets with **no explicit license**, cite the
source paper and contact the authors before rehosting or redistributing.

## Data ethics reminder

Occupational biomechanics data often involves human subjects and identifiable
**video**. Before moving one of your own datasets from `coming_soon` to `open`,
confirm that IRB approval and participant consent cover public sharing and
secondary use, and de-identify or gate video appropriately (restricted access +
data-use agreement). Plan the access tier per dataset via the `status` field.
