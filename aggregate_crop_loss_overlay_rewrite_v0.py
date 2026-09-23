#!/usr/bin/env python3
import glob,json
from pathlib import Path
rows=[json.loads(Path(p).read_text(encoding="utf-8"))
      for p in glob.glob("artifacts/**/crop_loss_overlay_rewrite_v0_*.json",recursive=True)]
payload={
 "schema":"kaggriculture.crop-loss-overlay-rewrite.aggregate.v0",
 "cases":len(rows),
 "cases_with_crop_loss":sum(bool(r.get("crop_loss_days")) for r in rows),
 "crop_loss_events":sum(len(r.get("crop_loss_days",[])) for r in rows),
 "overlay_overrides_in_windows":sum(r.get("summary",{}).get("all_overrides",0) for r in rows),
 "crop_direct_to_livestock_direct":sum(r.get("summary",{}).get("crop_direct_to_livestock_direct",0) for r in rows),
 "per_seed":[
   {"seed":r["seed"],
    "loss_days":r.get("crop_loss_days",[]),
    "overrides":r.get("summary",{}).get("all_overrides",0),
    "crop_to_livestock":r.get("summary",{}).get("crop_direct_to_livestock_direct",0)}
   for r in sorted(rows,key=lambda x:x["seed"])
 ],
 "boundary":"No causal attribution."
}
Path("crop_loss_overlay_rewrite_v0_aggregate.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
