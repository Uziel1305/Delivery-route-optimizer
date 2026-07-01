#!/bin/bash
set -euo pipefail

DATA_DIR="/data"
PBF_PATH="$DATA_DIR/region.osm.pbf"
OSRM_PATH="$DATA_DIR/region.osrm"

if [ -f "$OSRM_PATH.hsgr" ] || [ -f "$OSRM_PATH.partition" ]; then
    echo "OSRM data already preprocessed in volume, skipping."
    exit 0
fi

echo "Downloading region extract from $OSRM_REGION_URL ..."
curl -fL "$OSRM_REGION_URL" -o "$PBF_PATH"

echo "Running osrm-extract ..."
osrm-extract -p /opt/car.lua "$PBF_PATH"

echo "Running osrm-partition ..."
osrm-partition "$OSRM_PATH"

echo "Running osrm-customize ..."
osrm-customize "$OSRM_PATH"

echo "OSRM preprocessing complete."
