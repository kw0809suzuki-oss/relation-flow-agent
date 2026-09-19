#!/usr/bin/env bash
set -euo pipefail
mkdir -p opponents

curl -fL --retry 3   -o opponents/seyamalam_v21.py   https://raw.githubusercontent.com/Seyamalam/Kaggriculture/8b8c421eb10634c756583ce10c75189f50c83a72/main.py

curl -fL --retry 3   -o opponents/lonespear_main.py   https://raw.githubusercontent.com/lonespear/kaggriculture/774b26093ccf4246525517d48420349b841b6e50/main.py

curl -fL --retry 3   -o opponents/cok_main.py   https://raw.githubusercontent.com/COK-ZhangZiliang/Kaggriculture/7ef67eac458cd9ecd13786063e2e581fbe7403ec/main.py
