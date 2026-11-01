# Direct FreeSurfer-to-STL export

These are the scripts used by the [Module 4 print-preparation tutorial](https://github.com/tannerjared/Neuroimaging-Course/wiki/Module-4-MRI-QA-and-3D-Print-Prep#preparing-for-3d-printing).

Read a completed FreeSurfer subject directly. FSQC, BrainPrint, FreeSurfer executables, and a FreeSurfer license are not needed for export. Keep `3Dprintprep.py` and `subject_input.py` together. No participant data are included.

## Container use

For HiPerGator, use the shared `3dprintprep-direct-1.0.0.sif` and [student script](3dprintprep-student.sbatch). The instructor builds/converts it once using [INSTRUCTOR-SETUP.md](INSTRUCTOR-SETUP.md). Students need no Python setup.

For Docker on your own computer, build from this folder:

```sh
docker build --platform linux/amd64 -t freesurfer-to-stl:1.0.0 .
mkdir -p /path/to/exports
docker run --rm --platform linux/amd64 \
  --mount type=bind,src=/path/to/subject01,dst=/in,readonly \
  --mount type=bind,src=/path/to/exports,dst=/out \
  freesurfer-to-stl:1.0.0 /in /out/subject01.stl
```

Replace the host paths. Keep symlink targets within the mounted input. On native Linux, add `--user "$(id -u):$(id -g)"` to keep outputs owned by your account. No MRI data or license are included in the container. VTK and PyMeshLab account for much of its size.

## Optional local Python setup

Use Python 3.12. Run these commands from this folder:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python 3Dprintprep.py "/path/to/subject01" "/path/to/exports/subject01.stl"
```

On Windows, create the environment with `py -3.12 -m venv .venv` and replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`.

Required subject files are `mri/orig.mgz`, `mri/aseg.mgz`, `surf/lh.pial`, and `surf/rh.pial`. The `.pial.T1` alternatives are accepted. When copying symlinks, include their target files. A full native FastSurfer subject is also supported; segmentation-only processing is insufficient.

```sh
.venv/bin/python 3Dprintprep.py "/path/to/subject01" --check-input
.venv/bin/python 3Dprintprep.py "/path/to/subjects" "/path/to/exports/subject01.stl" --subject subject01
```

Keep output outside the source subject. The exporter creates the output directory. Direct invocation replaces generated files when reusing a destination; the student Slurm wrapper stops if outputs already exist.

## What is exported

The combined model contains cortex, cerebellum, brainstem, and selected non-cortical structures. Generic CSF and ventricles are excluded. Missing labels are reported. All meshes share the subject's surface/tkregister RAS coordinates in millimetres. No independent centering, resizing, or mesh decimation is performed.

The sibling `<output-name>_surfaces` folder contains original hemisphere STLs, grouped non-cortex STLs, smoothed/unsmoothed combined components, and `source_manifest.json`. `cortex.stl` preserves the original pial geometry before print smoothing.

Defaults match the tested exporter: 100 scale-dependent Laplacian cortex steps, delta 0.1%; 30 VTK windowed-sinc non-cortex iterations, passband 0.2. The combined non-cortex is extracted from the union of its selected labels to avoid shared internal seams. The overall STL contains anatomical shells, not a whole-brain boolean union. Inspect it in the slicer before printing.

## Validation and reproducibility

Dependencies are pinned in `requirements.txt`. The exporter passed eight tests and reproduced the reference FreeSurfer 8.2 STL byte-for-byte on Apple Silicon macOS with Python 3.12.9. Both source Python files are unchanged from that tested export. Cross-platform bit-for-bit identity is not promised.

The Linux AMD64 container passed the same eight tests, including a non-root run with a read-only image and no network. A real FreeSurfer subject export produced 21 valid meshes, with the same final triangle count and bounds as the native macOS export (binary STL files are not byte-identical across platforms). The saved Docker archive is 493 MB compressed; the unpacked image is about 1.62 GB. The student wrapper is checked locally with mocked Apptainer calls. SIF conversion, HiPerGator execution, and student permissions still require cluster validation. Native Windows execution has not been tested.

```sh
.venv/bin/python -m pytest -q tests -W error::RuntimeWarning
```

The exporter checks saved smoothed/final meshes for finite coordinates, closure, positive volume, and consistent winding. These checks do not replace anatomical QA, self-intersection checks, slicer inspection, or a physical print test.
