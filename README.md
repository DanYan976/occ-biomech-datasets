# ErgoBiomech

**A curated catalog of occupational biomechanics datasets** — by AnyMotion Lab at NJIT.

A discovery catalog for **occupational biomechanics** datasets: lab-based motion
capture, video, and wearable-sensor recordings of work tasks such as lifting,
carrying, and manual materials handling (MMH).

The catalog **indexes metadata and links out to each dataset's source**. It does
not rehost data files. Listing is descriptive, not an endorsement, and every
dataset keeps its own license and access terms.

This repo ships as an architecture-first skeleton: a working filterable site
seeded with a few placeholder entries and your lab's planned datasets marked
**Coming soon**. Swap in real records over time.

---

## How it works

```
datasets/*.yaml   →   scripts/build_catalog.py   →   site/ (static, filterable)
   (source of         (validates against              (deploys to GitHub Pages)
    truth, one          schema, compiles to
    file per            JSON injected into
    dataset)            site/index.html)
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
│   ├── index.html            # structure + injected catalog data
│   ├── style.css
│   ├── app.js                # search + filter logic
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

1. Push this repo to GitHub.
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Push to `main`. The workflow in `.github/workflows/deploy.yml` runs the build
   and publishes `site/`.

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

## About the seeded entries

- `njit-*` entries are real planned datasets, marked `coming_soon` until release.
- Real indexed datasets: `andydata-lab-oneperson` (CC-BY-4.0),
  `lara-logistics-har` (CC-BY-**NC**-4.0, non-commercial), and `moped25`
  (freely available, no explicit license — cite Li et al. 2020).

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
