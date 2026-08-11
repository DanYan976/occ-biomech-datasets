# Contributing a dataset

Thanks for helping build the catalog. Each dataset is one YAML file in
`datasets/`. Adding or editing one is a pull request.

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

## Controlled vocabularies

**status**: `open` (publicly downloadable), `restricted` (data-use agreement),
`coming_soon` (planned, not yet released).

**tasks**: lifting, lowering, carrying, pushing, pulling, holding, reaching,
squatting, walking, assembly, mmh.

**modalities**: mocap, imu, emg, force_plate, grf, video, egocentric_video,
pose_estimation, pressure_insole, physiological.

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
