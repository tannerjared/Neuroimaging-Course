# One shared container for HiPerGator

Use one `3dprintprep-direct-1.0.0.sif` file for the class. Python, the exporter, and its mesh libraries are inside it. Students do not need a Python environment, FreeSurfer module, FreeSurfer license, FSQC, or BrainPrint to create their STL files. FSQC remains part of the separate QA exercise.

## 1. Build once on a computer with Docker

Download the course repository and open a terminal in `tools/freesurfer-to-stl`. If you already have the prebuilt `freesurfer-to-stl-1.0.0-linux-amd64.tar.gz` archive and its checksum, skip this build and use those files in step 2.

```bash
docker build --platform linux/amd64 -t freesurfer-to-stl:1.0.0 .
```

The build runs eight synthetic subject/mesh tests. It stops if dependencies or tests fail. The explicit platform also creates the correct image on an Apple Silicon Mac; Docker Desktop must support Intel/AMD emulation. No participant data are copied into the image.

Save the image and checksum from this same folder:

```bash
bash <<'BASH'
set -euo pipefail
archive=freesurfer-to-stl-1.0.0-linux-amd64.tar.gz
[[ ! -e "$archive" ]] || { echo "Archive already exists; inspect it first."; exit 1; }
docker image save freesurfer-to-stl:1.0.0 | gzip > "$archive"
shasum -a 256 "$archive" > "${archive}.sha256"
BASH
```

Keep the archive and checksum together. The source uses pinned Python dependencies and a pinned base image; Debian library updates can still change later rebuilds. Retain the built image/archive and its checksum when exact reproducibility matters.

## 2. Convert the archive to SIF on HiPerGator

Upload these three files into one instructor-owned staging folder:

- `freesurfer-to-stl-1.0.0-linux-amd64.tar.gz`
- `freesurfer-to-stl-1.0.0-linux-amd64.tar.gz.sha256`
- `build-sif.sbatch`

In a terminal, enter that folder. Check the account/QoS in the script, then submit:

```bash
sbatch build-sif.sbatch
squeue -u "$USER"
```

The job requires an x86_64 compute node. If your allocation includes ARM nodes, select the current x86 node feature with RC's guidance. Apptainer must be available in the batch environment; if it is not, use the site's documented module setup in both batch scripts.

The job verifies the archive checksum, converts it to SIF without installing Python on the host, and reruns the eight tests inside the SIF. It writes `3dprintprep-direct-1.0.0.sif` and its checksum in the staging folder. This is a CPU-only workflow; no GPU is needed.

After it finishes, replace `JOBID` below with the submitted job number:

```bash
sacct -j JOBID --format=JobID,State,ExitCode,Elapsed,MaxRSS
cat build-stl-container_JOBID.log
```

Require `COMPLETED`, exit `0:0`, eight passed tests, and the final `Container build and eight tests passed` message. If the job fails, inspect the log before resubmitting. The script refuses to overwrite an existing SIF.

Conversion follows [Apptainer's Docker-archive workflow](https://apptainer.org/docs/user/main/build_a_container.html#reusing-existing-containers-from-docker-or-podman); see also [UF's Apptainer usage guide](https://docs.rc.ufl.edu/software/apps/apptainer/usage/).

## 3. Install the shared SIF and test one class subject

Copy the verified SIF once to:

```text
/blue/psb4353c/share/data/neurotools/3dprintprep-direct-1.0.0.sif
```

Keep it instructor-controlled and readable by the class. Do not overwrite an active image or recursively change allocation permissions. Check the copied image against the staging checksum. No `environment.sh`, `.venv`, or separate Python scripts are needed beside the SIF.

Edit `3dprintprep-student.sbatch` for one completed class subject and a new private output folder. Check the shared `IMAGE` path and submit:

```bash
bash -n 3dprintprep-student.sbatch
sbatch 3dprintprep-student.sbatch
```

Verify the job's exit status/log, the STL's appearance and dimensions, the source manifest, and measured memory/runtime. The example requests 2 CPUs, 8 GB, and 40 minutes; adjust based on that run. Check that a student account can read the SIF and its own subject and write its own output folder. The wrapper mounts input read-only and output read/write; symbolic links must resolve within the mounted subjects directory.

Distribute only the small student script after this check. All students reuse the same SIF. Existing FSQC output is not used by this exporter.

Local Docker validation is not HiPerGator validation. SIF conversion and the class-subject run must pass on the cluster before class use.
