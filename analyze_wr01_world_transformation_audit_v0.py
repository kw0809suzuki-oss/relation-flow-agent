#!/usr/bin/env python3
import glob,json
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
CHECKS=("d14h0","d16h0","d20h0","d24h0")
CROPS=("WHEAT","STRAWBERRY","MELON")

def main():
    ps=sorted(Path(p) for p in glob.glob("wr01-transform-artifacts/**/wr01_world_transformation_audit_v0_*.json",recursive=True))
    if len(ps)!=5: raise SystemExit(f"Expected 5 artifacts, found {len(ps)}")
    rs=[json.loads(p.read_text()) for p in ps]
    cps={}
    for cp in CHECKS:
        rows=[]
        for r in rs:
            b=r["baseline"]["views"][cp];c=r["wr01"]["views"][cp]
            rows.append({
                "seed":r["seed"],
                "committed_mark_delta":c["committed_mark"]-b["committed_mark"],
                "crop_mark_delta":c["crop_mark"]-b["crop_mark"],
                "animal_mark_delta":c["animal_mark"]-b["animal_mark"],
                "empty_tile_delta":c["empty_unlocked_tiles"]-b["empty_unlocked_tiles"],
                "seed_delta":{k:c["seed_inventory"].get(k,0)-b["seed_inventory"].get(k,0) for k in CROPS},
                "crop_count_delta":{k:c["crop_count"].get(k,0)-b["crop_count"].get(k,0) for k in CROPS},
            })
        cps[cp]={
            "committed_mark_delta_mean":mean([x["committed_mark_delta"] for x in rows]),
            "crop_mark_delta_mean":mean([x["crop_mark_delta"] for x in rows]),
            "animal_mark_delta_mean":mean([x["animal_mark_delta"] for x in rows]),
            "empty_tile_delta_mean":mean([x["empty_tile_delta"] for x in rows]),
            "seed_delta_mean":{k:mean([x["seed_delta"][k] for x in rows]) for k in CROPS},
            "crop_count_delta_mean":{k:mean([x["crop_count_delta"][k] for x in rows]) for k in CROPS},
            "rows":rows,
        }
    payload={
        "schema":"kaggriculture.strong-origin-v2.wr01-world-transformation-audit.result.v0",
        "battle_count":5,
        "reopened_orders_mean":mean([r["wr01_reopened_orders"] for r in rs]),
        "terminal_self_delta_mean":mean([r["delta_terminal_self"] for r in rs]),
        "checkpoints":cps,
        "boundary":[
            "Checkpoint deltas compare WR-01 World State against baseline on matched fixed-five Battles.",
            "Additional seed inventory is not equated with productive transformation.",
            "Additional committed-production mark/crop count is observed World transformation, not proof of value realization to terminal Cash.",
            "No next Candidate is selected by this result alone."
        ]
    }
    Path("wr01_world_transformation_audit_v0_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    print("WR01_WORLD_TRANSFORMATION_AUDIT_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
