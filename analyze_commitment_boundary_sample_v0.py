#!/usr/bin/env python3
import glob,json,sys
from collections import Counter,defaultdict
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
files=sorted(root.glob("**/commitment_boundary_sample_v0_*.json"))
if not files:
    files=[Path(p) for p in glob.glob(str(root/"**"/"commitment_boundary_sample_v0_*.json"),recursive=True)]
rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
if not rows: raise SystemExit("No samples")

def aggregate(side):
    samples=[x for r in rows for x in r[side]["samples"]]
    by_crop=defaultdict(list)
    for x in samples: by_crop[x["crop"]].append(x)
    out={}
    for crop,xs in by_crop.items():
        op_counts=Counter(op for x in xs for op in x.get("unit_ops",[]))
        out[crop]={
            "sample_count":len(xs),
            "mean_workers":sum(x["workers"] for x in xs)/len(xs),
            "mean_empty_tiles":sum(x["empty_tiles"] for x in xs)/len(xs),
            "mean_queue_after":sum(x["queue_after"] for x in xs)/len(xs),
            "plant_order_present_cases":sum(x["plant_orders_for_crop"]>0 for x in xs),
            "unit_ops":dict(op_counts),
            "examples":xs[:3],
        }
    return {
        "mean_stall_count":sum(r[side]["stall_count"] for r in rows)/len(rows),
        "by_crop":dict(out),
    }

out={
  "schema":"kaggriculture.strong-origin-v2.commitment-boundary-sample.aggregate.v0",
  "battle_count":len(rows),
  "self":aggregate("self"),
  "opponent":aggregate("opponent"),
  "boundary":[
    "Representative samples only; not a full classification of all queue-positive turns.",
    "No causal label is assigned from action frequencies alone."
  ]
}
Path("commitment_boundary_sample_v0_aggregate.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("COMMITMENT_BOUNDARY_SAMPLE_AGG "+json.dumps(out,ensure_ascii=False,separators=(",",":")))
