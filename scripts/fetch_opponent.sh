#!/usr/bin/env bash
set -euo pipefail
mkdir -p opponents
curl -fL --retry 3 \
  -o opponents/seyamalam_v21.py \
  https://raw.githubusercontent.com/Seyamalam/Kaggriculture/8b8c421eb10634c756583ce10c75189f50c83a72/main.py
