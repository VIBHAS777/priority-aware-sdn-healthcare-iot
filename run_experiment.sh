#!/usr/bin/env bash
set -euo pipefail

python3 -m src.sdn_health_iot --scenario baseline --policy priority
python3 -m src.sdn_health_iot --scenario baseline --policy fifo --tag fifo

echo "Experiment complete."
echo "Open dashboard with: node dashboard/server.js"

