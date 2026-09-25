#!/usr/bin/env python3
"""Aggregate WR-01 purchase->plant conversion fixed5."""
import glob,json
from pathlib import Path

CROPS=("WHEAT","STRAWBERRY","MELON")
def mean(xs): return sum(xs)/len(xs) if xs else None

def main():
    ps=sorted(Path(p) for p in glob.glob(
        "wr01-purchase-plant-artifacts/**/wr01_purchase_plant_conversion_audit_v0_*.json",
        recursive=True
    ))
    if len(ps)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(ps)}")
    rs=[json.loads(p.read_text(encoding="utf-8")) for p in ps]

    by_crop={}
    for c in CROPS:
        buy=[r["delta"]["executed_buy_seed_units"][c] for r in rs]
        cmd=[r["delta"]["plant_command_units"][c] for r in rs]
        suc=[r["delta"]["successful_plant_units"][c] for r in rs]
        stock=[r["delta"]["seed_inventory_day24"][c] for r in rs]
        by_crop[c]={
            "extra_executed_buy_units_mean":mean(buy),
            "extra_plant_commands_mean":mean(cmd),
            "extra_successful_plants_mean":mean(suc),
            "day24_extra_seed_inventory_mean":mean(stock),
            "buy_to_command_drop_mean":mean([b-cm for b,cm in zip(buy,cmd)]),
            "command_to_success_drop_mean":mean([cm-s for cm,s in zip(cmd,suc)]),
            "by_seed":{
                str(r["seed"]):{
                    "buy":b,"command":cm,"success":s,"day24_seed":st
                }
                for r,b,cm,s,st in zip(rs,buy,cmd,suc,stock)
            },
        }

    totals={}
    for key in ("executed_buy_seed_units","plant_command_units","successful_plant_units","seed_inventory_day24"):
        vals=[sum(r["delta"][key][c] for c in CROPS) for r in rs]
        totals[key]={"mean":mean(vals),"by_seed":{str(r["seed"]):v for r,v in zip(rs,vals)}}

    buy=[totals["executed_buy_seed_units"]["by_seed"][str(r["seed"])] for r in rs]
    cmd=[totals["plant_command_units"]["by_seed"][str(r["seed"])] for r in rs]
    suc=[totals["successful_plant_units"]["by_seed"][str(r["seed"])] for r in rs]

    dup=[int(r["delta"].get("duplicate_plant_commands",0)) for r in rs]
    payload={
        "schema":"kaggriculture.strong-origin-v2.wr01-purchase-plant-conversion-audit.result.v0",
        "battle_count":5,
        "terminal_self_delta_mean":mean([r["delta"]["terminal_self"] for r in rs]),
        "by_crop":by_crop,
        "totals":totals,
        "connection_drop":{
            "purchase_to_plant_command_mean":mean([b-c for b,c in zip(buy,cmd)]),
            "plant_command_to_success_mean":mean([c-s for c,s in zip(cmd,suc)]),
            "same_tile_duplicate_plant_delta_mean":mean(dup),
            "same_tile_duplicate_share_of_command_success_drop":(
                mean(dup)/mean([c-s for c,s in zip(cmd,suc)])
                if mean([c-s for c,s in zip(cmd,suc)]) else None
            ),
            "cases_purchase_gt_command":sum(b>c for b,c in zip(buy,cmd)),
            "cases_command_gt_success":sum(c>s for c,s in zip(cmd,suc)),
            "cases_with_positive_duplicate_delta":sum(x>0 for x in dup),
        },
        "cases":[{
            "seed":r["seed"],
            "seat":r["seat"],
            "terminal_delta":r["delta"]["terminal_self"],
            "delta":{k:v for k,v in r["delta"].items() if k!="terminal_self"},
        } for r in rs],
        "boundary":[
            "Incremental flow is WR-01 minus matched baseline from Day14 onward.",
            "The first connection drop is descriptive; negative deltas can occur because WR-01 changes later World state and model actions.",
            "A PLANT command is not counted as successful unless World state confirms seed consumption and matching crop-tile creation.",
            "No WR-02 is created by this aggregation."
        ]
    }
    Path("wr01_purchase_plant_conversion_audit_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("WR01_PURCHASE_PLANT_CONVERSION_AUDIT_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
