#!/bin/bash
set -euo pipefail

# Preprocess the region extract that osrm-download has already placed in the
# shared volume at /data/region.osm.pbf. Produces the .osrm* files that
# osrm-routed serves. Skipped automatically if a previous run already
# preprocessed into this named volume.

DATA_DIR="/data"
PBF_PATH="$DATA_DIR/region.osm.pbf"
OSRM_PATH="$DATA_DIR/region.osrm"

if [ -f "$OSRM_PATH.mldgr" ] || [ -f "$OSRM_PATH.partition" ]; then
    echo "OSRM data already preprocessed in volume, skipping."
    exit 0
fi

if [ ! -f "$PBF_PATH" ]; then
    echo "ERROR: expected region extract at $PBF_PATH (osrm-download should have created it)." >&2
    exit 1
fi

echo "Running osrm-extract ..."
osrm-extract -p /opt/car.lua "$PBF_PATH"

echo "Running osrm-partition ..."
osrm-partition "$OSRM_PATH"

echo "Running osrm-customize ..."
osrm-customize "$OSRM_PATH"

echo "OSRM preprocessing complete."
