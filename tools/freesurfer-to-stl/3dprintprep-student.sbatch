#!/bin/bash
#SBATCH --job-name=3dprintprep-student
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=USER@ufl.edu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8gb
#SBATCH --time=00:40:00
#SBATCH --account=psb4353c
#SBATCH --qos=psb4353c
#SBATCH --output=3dprintprep_%j.log

set -euo pipefail

# EDIT: Your username, subject IDs, and paths. Also change the email above.
USERNAME="your_username"
SUBJECTS=("sub-6303")  # One brain is enough for the homework.
BASE_DIR="/blue/psb4353c/share/students/${USERNAME}/Module3/ADNI_bids/derivatives/freesurfer"
OUT_DIR="${BASE_DIR}/3dprint-direct"
IMAGE="/blue/psb4353c/share/data/neurotools/3dprintprep-direct-1.0.0.sif"

if [[ "$USERNAME" == "your_username" ]]; then
    echo "STOP: Edit USERNAME, SUBJECTS, BASE_DIR, and the email before submitting."
    exit 1
fi
command -v apptainer >/dev/null || { echo "STOP: Apptainer is not available. Ask the instructor."; exit 1; }
[[ -r "$IMAGE" ]] || { echo "STOP: Shared container is missing: $IMAGE. Ask the instructor."; exit 1; }
[[ -d "$BASE_DIR" ]] || { echo "STOP: Subject directory does not exist: $BASE_DIR"; exit 1; }
[[ ${#SUBJECTS[@]} -gt 0 ]] || { echo "STOP: List at least one subject."; exit 1; }
# Commas and colons are Apptainer bind delimiters; avoid them in these paths.
for path in "$BASE_DIR" "$OUT_DIR"; do
    [[ "$path" != *:* && "$path" != *,* ]] || { echo "STOP: Bind paths cannot contain commas or colons."; exit 1; }
done
THREADS="${SLURM_CPUS_PER_TASK:-2}"
RUN=(apptainer run --cleanenv --containall --pwd /tmp
    --env "OMP_NUM_THREADS=$THREADS,OPENBLAS_NUM_THREADS=$THREADS,MKL_NUM_THREADS=$THREADS"
    --bind "$BASE_DIR:/in:ro")

# Check every input and destination before starting any exports.
for SUBJ in "${SUBJECTS[@]}"; do
    [[ "$SUBJ" != */* && "$SUBJ" != "." && "$SUBJ" != ".." && -n "$SUBJ" ]] || {
        echo "STOP: Invalid subject ID: $SUBJ"; exit 1;
    }
    "${RUN[@]}" "$IMAGE" /in --subject "$SUBJ" --check-input
    if [[ -e "$OUT_DIR/$SUBJ.stl" || -L "$OUT_DIR/$SUBJ.stl" || -e "$OUT_DIR/${SUBJ}_surfaces" || -L "$OUT_DIR/${SUBJ}_surfaces" ]]; then
        echo "STOP: Output for $SUBJ already exists. Review it before choosing a new OUT_DIR."
        exit 1
    fi
done

mkdir -p "$OUT_DIR"
date
for SUBJ in "${SUBJECTS[@]}"; do
    echo "Exporting $SUBJ directly from FreeSurfer..."
    "${RUN[@]}" --bind "$OUT_DIR:/out:rw" "$IMAGE" \
        /in "/out/$SUBJ.stl" --subject "$SUBJ"
done
echo "Finished. Check $OUT_DIR for your STL files and source manifests."
date
