# Instructor setup for HiPerGator

Stage one shared installation before students run the new Module 4 job. This replaces the FSQC/BrainPrint step for printing only; FSQC remains part of the QA exercise.

1. In an allocated HiPerGator compute session, select an available Python 3.12 environment. Use `module spider python` and the [UF Python documentation](https://docs.rc.ufl.edu/software/apps/python/) or consult RC. Do not assume a particular versioned module name exists. Record the exact module-load commands needed by this environment.
2. Download this repository once and place the contents of `tools/freesurfer-to-stl` at `/blue/psb4353c/share/data/neurotools/freesurfer-to-stl`. Keep the folder name stable for the semester. If it already exists, inspect it rather than creating parallel copies or overwriting an active installation.
3. Create `environment.sh` in that shared folder. Put the tested module-load commands from step 1 in it. If the Python installation requires no modules, the file may contain only a comment. This file is sourced by student batch jobs; keep it instructor-controlled along with the code and environment.
4. From that shared directory, after loading the chosen Python environment, install once:

   ```bash
   # Confirm that this Python is 3.12 before continuing.
   python -c 'import sys; assert sys.version_info[:2] == (3, 12), sys.version'
   python -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -c 'import pymeshlab, vtk, nibabel, skimage, trimesh; print("Imports passed")'
   .venv/bin/python -m pytest -q tests -W error::RuntimeWarning
   ```

   Stop and resolve import failures before distributing the student script. PyMeshLab and VTK may require Linux graphics libraries even without opening a window. Use RC support for missing system libraries; do not have students create separate installations to work around a broken shared setup.

5. Test `3dprintprep-student.sbatch` on one completed class subject, using a private output folder and the same account/QoS students will use. Check the Slurm exit status and log, STL dimensions and appearance, source manifest, peak memory, and runtime. The example requests 2 CPUs, 8 GB and 40 minutes; adjust based on that measured run.
6. Verify read/traverse access to code, `environment.sh`, and `.venv` from a student account; keep them protected from student writes. Verify students can write only their own export folders. Do not apply broad recursive permission changes to the allocation.
7. Copy the small updated student batch script into the shared Module4 handout location if you distribute scripts there, or have students download it from GitHub. Confirm the shared `TOOL_DIR` is correct before announcing it is ready.

This repository does not install software on HiPerGator. A successful local macOS export or a shell syntax check is not cluster validation. Retain the source revision, Python version, and pinned requirements used for the class.
