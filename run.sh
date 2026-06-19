#!/bin/bash
#
# GPUPulse quick launcher from source tree (for development / testing)
# For normal use: bash install.sh  (or double-click Install-GPUPulse.desktop)
#

cd "$(dirname "$0")"
echo "Running GPUPulse from source (PYTHONPATH=.) ..."
PYTHONPATH=. exec python3 main.py
