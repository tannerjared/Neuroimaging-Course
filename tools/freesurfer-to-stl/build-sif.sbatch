#!/bin/bash
#SBATCH --job-name=build-stl-container
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8gb
#SBATCH --time=00:30:00
#SBATCH --account=psb4353c
#SBATCH --qos=psb4353c
#SBATCH --output=build-stl-container_%j.log
set -euo pipefail

# Submit from the folder containing the archive, checksum, and this script:
# sbatch build-sif.sbatch
ARCHIVE="$(pwd)/freesurfer-to-stl-1.0.0-linux-amd64.tar.gz"
IMAGE="$(pwd)/3dprintprep-direct-1.0.0.sif"
[[ "$(uname -m)" == x86_64 ]] || { echo "STOP: Request an x86_64 compute node."; exit 1; }
command -v apptainer >/dev/null || { echo "STOP: Apptainer is not available."; exit 1; }
[[ ! -e "$IMAGE" && ! -L "$IMAGE" ]] || { echo "STOP: $IMAGE already exists."; exit 1; }
sha256sum -c "${ARCHIVE}.sha256"
BUILD_WORK=$(mktemp -d "${SLURM_TMPDIR:-${TMPDIR:-/tmp}}/stl-build.XXXXXXXX")
trap 'rm -rf -- "$BUILD_WORK"' EXIT
export APPTAINER_TMPDIR="$BUILD_WORK/tmp"
export APPTAINER_CACHEDIR="$BUILD_WORK/cache"
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"
apptainer build "$BUILD_WORK/exporter.sif" "docker-archive:$ARCHIVE"
apptainer exec --cleanenv --containall --pwd /tmp "$BUILD_WORK/exporter.sif" \
    python -m pytest -q /opt/freesurfer-to-stl/tests --rootdir=/tmp -W error::RuntimeWarning -p no:cacheprovider
apptainer run --cleanenv --containall "$BUILD_WORK/exporter.sif" --help
# Publish without replacing a SIF that appeared while this job was running.
( set -o noclobber; cat "$BUILD_WORK/exporter.sif" > "$IMAGE" )
sha256sum "$IMAGE" > "${IMAGE}.sha256"
echo "Container build and eight tests passed: $IMAGE"
