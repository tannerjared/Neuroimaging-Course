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
TOOL_DIR="/blue/psb4353c/share/data/neurotools/freesurfer-to-stl"

if [[ "$USERNAME" == "your_username" ]]; then
    echo "STOP: Edit USERNAME, SUBJECTS, BASE_DIR, and the email before submitting."
    exit 1
fi
if [[ ! -r "$TOOL_DIR/environment.sh" ]]; then
    echo "STOP: Shared exporter setup is missing. Ask the instructor; do not use the old print container."
    exit 1
fi
# The instructor records the module(s) needed by the shared Python environment here.
# Source before enabling nounset again because some module setup scripts use unset variables.
set +u
source "$TOOL_DIR/environment.sh"
set -u
PYTHON="$TOOL_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" || ! -r "$TOOL_DIR/3Dprintprep.py" || ! -r "$TOOL_DIR/subject_input.py" ]]; then
    echo "STOP: Shared exporter is incomplete. Ask the instructor to finish setup."
    exit 1
fi
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"

# Check every input before starting any exports.
for SUBJ in "${SUBJECTS[@]}"; do
    [[ "$SUBJ" != */* && "$SUBJ" != "." && "$SUBJ" != ".." && -n "$SUBJ" ]] || {
        echo "STOP: Invalid subject ID: $SUBJ"; exit 1;
    }
    "$PYTHON" "$TOOL_DIR/3Dprintprep.py" "$BASE_DIR" --subject "$SUBJ" --check-input
    if [[ -e "$OUT_DIR/$SUBJ.stl" || -e "$OUT_DIR/${SUBJ}_surfaces" ]]; then
        echo "STOP: Output for $SUBJ already exists. Review it before choosing a new OUT_DIR."
        exit 1
    fi
done

mkdir -p "$OUT_DIR"
date
for SUBJ in "${SUBJECTS[@]}"; do
    echo "Exporting $SUBJ directly from FreeSurfer..."
    "$PYTHON" -u "$TOOL_DIR/3Dprintprep.py" \
        "$BASE_DIR" "$OUT_DIR/$SUBJ.stl" --subject "$SUBJ"
done
echo "Finished. Check $OUT_DIR for your STL files and source manifests."
date
