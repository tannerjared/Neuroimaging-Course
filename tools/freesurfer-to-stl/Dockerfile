FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    QT_QPA_PLATFORM=offscreen \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    MPLCONFIGDIR=/tmp/matplotlib

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libopengl0 libglib2.0-0 libharfbuzz0b libxrender1 libxtst6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/freesurfer-to-stl
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt \
    && python -m pip check
COPY 3Dprintprep.py subject_input.py ./
COPY tests/ ./tests/
RUN python -m pytest -q tests -W error::RuntimeWarning -p no:cacheprovider

LABEL org.opencontainers.image.title="FreeSurfer-to-STL" \
      org.opencontainers.image.description="Direct STL export from completed FreeSurfer subjects; no FSQC or FreeSurfer installation required"
ENTRYPOINT ["python", "/opt/freesurfer-to-stl/3Dprintprep.py"]
CMD ["--help"]
