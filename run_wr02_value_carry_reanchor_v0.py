#!/usr/bin/env python3
"""WR-02 Value Carry re-anchor v0.

Reuses the existing Day20 cohort accounting probe unchanged, but swaps the
observed self policy from Strong Origin v2 Body-only to the current active
Baseline + WR-02 body.

No agent logic is modified. Observation only.
"""
import json
from pathlib import Path

import run_production_downstream_boundary_surface_v0 as probe
import wr02_same_tile_plant_deconfliction_v0 as wr02

probe.body_only = wr02
probe.OUT = Path(
    f"wr02_production_downstream_boundary_surface_v0_{probe.SEED}_seat{probe.SEAT}.json"
)

probe.main()

payload = json.loads(probe.OUT.read_text(encoding="utf-8"))
payload["schema"] = "kaggriculture.strong-origin-v2.wr02-production-downstream-boundary-surface.v0"
payload["active_model"] = "Baseline+WR-02"
payload["comparison_basis"] = {
    "fixed_seeds": [7351, 7352, 7353, 7354, 7355],
    "anchor": "Day20 h0 pre-market",
    "valuation": "same Day20 displayed-price committed-production basis",
}
payload["boundary"].extend([
    "This rerun changes only the observed self policy from Body-only to WR-02.",
    "WR-02 itself is unchanged; no new Candidate or control rule is introduced.",
    "The same anchor-cohort accounting and public environment instrumentation are reused."
])
probe.OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("WR02_VALUE_CARRY_REANCHOR " + json.dumps({
    "seed": payload["seed"],
    "seat": payload["seat"],
    "terminal": payload["terminal"],
    "self": {k:v for k,v in payload["by_player"][str(payload["seat"])].items() if k!="assets"},
    "opponent": {k:v for k,v in payload["by_player"][str(1-int(payload["seat"]))].items() if k!="assets"},
}, ensure_ascii=False, separators=(",",":")))
