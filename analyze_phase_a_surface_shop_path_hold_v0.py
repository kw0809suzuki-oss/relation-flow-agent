#!/usr/bin/env python3
import glob,json
from pathlib import Path

rows=[json.loads(Path(p).read_text(encoding="utf-8")) for p in glob.glob("phase-a-surface-shop-path-hold-artifacts/**/phase_a_surface_shop_path_hold_v0_*.json",recursive=True)]
rows=sorted(rows,key=lambda r:r["seed"])
if [r["seed"] for r in rows] != [8801,8806]:
    raise SystemExit(f"Expected 8801/8806, got {[r['seed'] for r in rows]}")

cases=[]
for r in rows:
    od=float(r["delta_vs_active"]["surface_original"])
    hd=float(r["delta_vs_active"]["surface_active_shop_path"])
    cases.append({
      "seed":r["seed"],
      "terminal_self":r["terminal_self"],
      "delta_vs_active":{
        "surface_original":od,
        "surface_active_shop_path":hd,
      },
      "shop_path_hold_effect_on_surface":hd-od,
      "original_sign":"positive" if od>0 else "negative" if od<0 else "zero",
      "held_sign":"positive" if hd>0 else "negative" if hd<0 else "zero",
      "sign_changed":(od>0)!=(hd>0) if od!=0 and hd!=0 else od!=hd,
      "held_path_matches_active":r["shop_paths"]["surface_active_shop_path"]==r["shop_paths"]["active"],
      "changed_turns":r["changed_turns"],
    })

payload={
  "schema":"kaggriculture.phase-a-surface-shop-path-hold.result.v0",
  "cases":cases,
  "mechanical_summary":{
    "both_held_paths_match_active":all(c["held_path_matches_active"] for c in cases),
    "any_terminal_sign_changed":any(c["sign_changed"] for c in cases)
  },
  "boundary":[
    "A sign change after holding the Active shop path is evidence that the candidate-induced shop-path channel materially participates in the terminal Surface effect for that seed.",
    "No sign change does not prove the channel is irrelevant; magnitude changes remain informative.",
    "This probe does not remove every downstream effect of altered RNG consumption."
  ]
}
Path("phase_a_surface_shop_path_hold_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload["mechanical_summary"],ensure_ascii=False))
