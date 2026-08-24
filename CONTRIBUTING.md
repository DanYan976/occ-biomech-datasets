# Contributing

Thanks for helping build the catalog. Each record is one YAML file — datasets
in `datasets/`, models in `models/`, analysis tools in `tools/`. Adding or
editing one is a pull request. The steps below are written for datasets; the
[Models and tools](#models-and-tools) section covers what differs.

## Steps

1. Copy the template:
   ```bash
   cp datasets/_template.yaml datasets/my-dataset.yaml
   ```
2. Fill in the fields. Required: `id`, `title`, `status`, `source`, `tasks`,
   `modalities`. See `schema/dataset.schema.json` for every field and the
   allowed values.
3. Validate and build:
   ```bash
   pip install -r scripts/requirements.txt
   python scripts/build_catalog.py
   ```
   The build fails with a clear message if a field is missing or uses a value
   outside the controlled vocabulary.
4. Commit the YAML (and the regenerated `site/index.html` / `site/catalog.json`)
   and open a pull request.

## Models

Same workflow, different folder and schema: copy `models/_template.yaml` and
validate against `schema/model.schema.json` (required: `id`, `title`, `source`,
`links`). A **model** is a published method — a pose estimator, an exposure
equation, a biomechanical model — with a paper landing page in `links.paper`
and, when released, code in `links.code` plus its `code_license`. If the method
is available as software (commercial or free), put the vendor or project page in
`links.website`; the card shows it as a "Software" link. Link models to catalog
datasets with `related_datasets` (use the dataset `id`s). A method that is
announced but whose paper is not yet public can be listed with
`status: coming_soon`; that is the only case where `links` may be omitted, and
the card then shows a "Coming soon" badge with no outbound link.
`python scripts/build_catalog.py` validates both libraries at once and
regenerates `site/models.json` and `site/models.html`; commit those with your
YAML.

## Controlled vocabularies

**status**: `open` (publicly downloadable), `restricted` (data-use agreement),
`coming_soon` (planned, not yet released).

**tasks**: lifting, lowering, carrying, pushing, pulling, holding, reaching,
squatting, walking, assembly, mmh.

**modalities** (what was captured — sensors and data streams, not derived
outputs such as pose keypoints or joint angles): mocap (optical), imu,
force_plate (incl. GRF), pressure (insoles or gloves), emg, physiological (HR,
ECG, EDA, VO2…), video, egocentric_video, depth (depth cameras / LiDAR), survey
(questionnaire-only studies).

**exoskeleton.role**: `evaluation` (a device was worn and its effect measured),
`control_input` (collected to develop or control an exoskeleton, no device worn).

**exoskeleton.body_region**: back, shoulder, knee, hip, ankle, neck, wrist,
full_body. **exoskeleton.actuation**: passive, active, quasi_passive.
**exoskeleton.outcomes**: muscle_activity, kinematics, kinetics, metabolic,
cardiovascular, task_performance, subjective, discomfort.

Need a value that isn't listed? Add it to the relevant `enum` in
`schema/dataset.schema.json` in the same pull request, with a one-line note in
the PR description.

## Exoskeleton records

If the record involves an occupational exoskeleton, add the `exoskeleton` block
(see `datasets/_template.yaml`). It is what puts the entry in the exoskeleton
collection at `site/exoskeletons.html` and behind the exoskeleton filters on the
catalog page. Fill `outcomes` from what the source actually reports — an empty
outcome is more useful than a guessed one, because the point of the field is to
show where evaluations differ.

## What we index

Metadata only. The catalog links to the dataset at its original home; it does
not host data files. Listing a dataset is descriptive and is not an endorsement.
Only submit datasets whose authors have made them available, and respect their
license and access terms.

## Human-subjects data

If you are listing your own dataset and it contains identifiable data (notably
video), do not set `status: open` unless consent and IRB approval cover public
release. Use `restricted` with an application URL, or keep it `coming_soon`
until access terms are settled.
