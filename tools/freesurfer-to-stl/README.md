# Direct FreeSurfer-to-STL export

These are the scripts used by the [Module 4 print-preparation tutorial](https://github.com/tannerjared/Neuroimaging-Course/wiki/Module-4-MRI-QA-and-3D-Print-Prep#preparing-for-3d-printing).

Read a completed FreeSurfer subject directly. FSQC, BrainPrint, FreeSurfer executables, and a FreeSurfer license are not needed for export. Keep `3Dprintprep.py` and `subject_input.py` together. No participant data are included.

## Local setup and use

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

## HiPerGator course setup

Students use one shared installation and copy only `3dprintprep-student.sbatch` into their own work folder. The instructor must first complete [INSTRUCTOR-SETUP.md](INSTRUCTOR-SETUP.md). No shared installation is created by downloading this repository.

The wrapper runs on a compute node, checks all subject inputs, prevents accidental output replacement, and uses the existing Module 3 subjects. It does not run `fsqc.sif`, BrainPrint `--shape`, or an old `3dprintprep*.sif` image.

## Validation and reproducibility

Dependencies are pinned in `requirements.txt`. The exporter passed eight tests and reproduced the reference FreeSurfer 8.2 STL byte-for-byte on Apple Silicon macOS with Python 3.12.9. Both source Python files are unchanged from that tested export. Cross-platform bit-for-bit identity is not promised.

The Slurm wrapper has been checked locally with input/output guard tests. HiPerGator execution, Linux graphics-library compatibility, and student permissions still require a test on the cluster before class use. Native Windows execution has not been tested.

```sh
.venv/bin/python -m pytest -q tests -W error::RuntimeWarning
```

The exporter checks saved smoothed/final meshes for finite coordinates, closure, positive volume, and consistent winding. These checks do not replace anatomical QA, self-intersection checks, slicer inspection, or a physical print test.
