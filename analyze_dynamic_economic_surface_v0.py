#!/usr/bin/env python3
"""Aggregate Dynamic Economic Surface v0 across the fixed five Battles."""
import glob,json
from pathlib import Path

DAYS=tuple(range(12,21))
INTERVALS=tuple(range(12,20))
PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
ASSETS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","GOOSE","COW","SHEEP")

def mean(xs): return sum(xs)/len(xs) if xs else None

def anchor(raw,day):
    for t in raw["surface_turns"]:
        if int(t["day"])==day and int(t["hour"])==0:
            return t
    raise KeyError((raw["seed"],day))

def side_index(raw,label):
    seat=int(raw["seat"])
    return str(seat if label=="self" else 1-seat)

def metric_summary(raws,day,getter):
    sv=[];ov=[]
    for r in raws:
        t=anchor(r,day)
        s=getter(t["before"][side_index(r,"self")])
        o=getter(t["before"][side_index(r,"opponent")])
        sv.append(float(s));ov.append(float(o))
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
        "self_absolute_mean":mean(sv),
        "opponent_absolute_mean":mean(ov),
        "mean_residual_opponent_minus_self":mean(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
    }

def interval_events(raw,start_day):
    out=[]
    for t in raw["surface_turns"]:
        d=int(t["day"]);h=int(t["hour"])
        ti=d*24+h
        if start_day*24 <= ti < (start_day+1)*24:
            out.append(t)
    return out

def interval_realized(raw,start_day,label,item=None,field="sell_cash_by_item"):
    p=side_index(raw,label)
    total=0.0
    for t in interval_events(raw,start_day):
        rp=t["realized_by_player"][p]
        if field=="market_cash_delta_all_ops":
            total+=float(rp[field])
        else:
            total+=float(rp[field].get(item,0) or 0)
    return total

def residual_change(raw,day,getter):
    a=anchor(raw,day);b=anchor(raw,day+1)
    sidx=side_index(raw,"self");oidx=side_index(raw,"opponent")
    ra=float(getter(a["before"][oidx]))-float(getter(a["before"][sidx]))
    rb=float(getter(b["before"][oidx]))-float(getter(b["before"][sidx]))
    return rb-ra

def shape(vals):
    if all(v>0 for v in vals): return "residual_increases_5of5"
    if all(v<0 for v in vals): return "residual_decreases_5of5"
    if all(v==0 for v in vals): return "flat_5of5"
    return "mixed"

def main():
    paths=sorted(Path(p) for p in glob.glob(
        "dynamic-surface-artifacts/**/dynamic_economic_surface_v0_*.json",
        recursive=True
    ))
    if len(paths)!=5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in paths]

    daily={}
    for day in DAYS:
        daily[str(day)]={
            "cash":metric_summary(raws,day,lambda s:s["cash"]),
            "inventory_display_mark":metric_summary(raws,day,lambda s:s["inventory_display_mark"]["total"]),
            "committed_production_mark":metric_summary(raws,day,lambda s:s["committed_production_mark"]["subtotal"]),
            "remaining_season_turns":metric_summary(raws,day,lambda s:s["time"]["remaining_season_turns"]),
            "assets":{},
            "output_stock":{},
            "shared_market":{},
        }
        for typ in ASSETS:
            daily[str(day)]["assets"][typ]={
                "present_asset_count":metric_summary(raws,day,lambda s,t=typ:s["asset_by_type"][t]["present_asset_count"]),
                "held_output_units":metric_summary(raws,day,lambda s,t=typ:s["asset_by_type"][t]["held_output_units"]),
                "current_harvestable_units":metric_summary(raws,day,lambda s,t=typ:s["asset_by_type"][t]["current_harvestable_units"]),
                "near_window_base_units_conditional":metric_summary(raws,day,lambda s,t=typ:s["asset_by_type"][t]["near_window_base_units_conditional"]),
            }
        for item in PRODUCTS:
            daily[str(day)]["output_stock"][item]={
                "carried":metric_summary(raws,day,lambda s,i=item:s["stock"]["carried_by_item"][i]),
                "shed":metric_summary(raws,day,lambda s,i=item:s["stock"]["shed_by_item"][i]),
                "on_hand":metric_summary(raws,day,lambda s,i=item:s["stock"]["on_hand_by_item"][i]),
                "display_mark":metric_summary(raws,day,lambda s,i=item:s["inventory_display_mark"]["by_item"][i]["mark"]),
            }
        # Shared market is not a side comparison. Preserve mean level across Battles.
        invs={};prices={}
        for item in PRODUCTS:
            invs[item]=mean([float(anchor(r,day)["market_before"]["inventory_by_item"].get(item,0)) for r in raws])
            prices[item]=mean([float(anchor(r,day)["market_before"]["displayed_price_by_item"].get(item,0)) for r in raws])
        daily[str(day)]["shared_market"]={
            "inventory_absolute_mean_by_item":invs,
            "displayed_price_absolute_mean_by_item":prices,
        }

    intervals={}
    for day in INTERVALS:
        cash_delta=[residual_change(r,day,lambda s:s["cash"]) for r in raws]
        prod_delta=[residual_change(r,day,lambda s:s["committed_production_mark"]["subtotal"]) for r in raws]
        invmark_delta=[residual_change(r,day,lambda s:s["inventory_display_mark"]["total"]) for r in raws]
        row={
            "cash_residual_change":{
                "mean":mean(cash_delta),"shape":shape(cash_delta),"by_seed":{str(r["seed"]):v for r,v in zip(raws,cash_delta)}
            },
            "committed_production_residual_change":{
                "mean":mean(prod_delta),"shape":shape(prod_delta),"by_seed":{str(r["seed"]):v for r,v in zip(raws,prod_delta)}
            },
            "inventory_mark_residual_change":{
                "mean":mean(invmark_delta),"shape":shape(invmark_delta),"by_seed":{str(r["seed"]):v for r,v in zip(raws,invmark_delta)}
            },
            "realized_sell":{},
            "asset_residual_change":{},
            "output_on_hand_residual_change":{},
        }
        for item in PRODUCTS:
            su=[interval_realized(r,day,"self",item,"sell_units_by_item") for r in raws]
            ou=[interval_realized(r,day,"opponent",item,"sell_units_by_item") for r in raws]
            sc=[interval_realized(r,day,"self",item,"sell_cash_by_item") for r in raws]
            oc=[interval_realized(r,day,"opponent",item,"sell_cash_by_item") for r in raws]
            row["realized_sell"][item]={
                "self_units_absolute_mean":mean(su),
                "opponent_units_absolute_mean":mean(ou),
                "unit_residual_mean":mean([o-s for s,o in zip(su,ou)]),
                "self_cash_absolute_mean":mean(sc),
                "opponent_cash_absolute_mean":mean(oc),
                "cash_residual_mean":mean([o-s for s,o in zip(sc,oc)]),
            }
            vals=[residual_change(r,day,lambda s,i=item:s["stock"]["on_hand_by_item"][i]) for r in raws]
            row["output_on_hand_residual_change"][item]={
                "mean":mean(vals),"shape":shape(vals),"by_seed":{str(r["seed"]):v for r,v in zip(raws,vals)}
            }
        for typ in ASSETS:
            row["asset_residual_change"][typ]={}
            for field in ("present_asset_count","held_output_units","current_harvestable_units","near_window_base_units_conditional"):
                vals=[residual_change(r,day,lambda s,t=typ,f=field:s["asset_by_type"][t][f]) for r in raws]
                row["asset_residual_change"][typ][field]={
                    "mean":mean(vals),"shape":shape(vals),"by_seed":{str(r["seed"]):v for r,v in zip(raws,vals)}
                }
        mc_s=[interval_realized(r,day,"self",field="market_cash_delta_all_ops") for r in raws]
        mc_o=[interval_realized(r,day,"opponent",field="market_cash_delta_all_ops") for r in raws]
        row["market_cash_all_ops"]={
            "self_absolute_mean":mean(mc_s),
            "opponent_absolute_mean":mean(mc_o),
            "residual_mean":mean([o-s for s,o in zip(mc_s,mc_o)]),
        }
        intervals[f"{day}->{day+1}"]=row

    payload={
        "schema":"kaggriculture.strong-origin-v2.dynamic-economic-surface.result.v0",
        "battle_count":5,
        "terminal_absolute":{
            "mean_self":mean([float(r["terminal"]["self"]) for r in raws]),
            "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in raws]),
            "mean_margin":mean([float(r["terminal"]["margin"]) for r in raws]),
        },
        "daily_absolute_surface":daily,
        "daily_transition_surface":intervals,
        "cases":[{"seed":r["seed"],"seat":r["seat"],"turn_count":len(r["surface_turns"]),"terminal":r["terminal"]} for r in raws],
        "boundary":[
            "Daily anchors are Day12..Day20 h0 public-world snapshots.",
            "Daily transition rows are DayN h0 inclusive -> DayN+1 h0 exclusive for realized market events.",
            "Asset types and product items remain separate; no cross-type quantity score is formed.",
            "Cash, inventory display mark, and committed-production mark remain separate layers.",
            "The shape field only states whether a residual increased/decreased/was flat in all five Battles or was mixed.",
            "No economic mode name, causal conversion, Action diagnosis, Candidate, or policy conclusion is generated."
        ]
    }
    Path("dynamic_economic_surface_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "terminal_absolute":payload["terminal_absolute"],
        "daily_value_layers":{
            str(d):{
                "cash":daily[str(d)]["cash"],
                "inventory":daily[str(d)]["inventory_display_mark"],
                "production":daily[str(d)]["committed_production_mark"],
            } for d in DAYS
        },
        "transition_value_layers":{
            k:{
                "cash":v["cash_residual_change"],
                "inventory":v["inventory_mark_residual_change"],
                "production":v["committed_production_residual_change"],
            } for k,v in intervals.items()
        }
    }
    print("DYNAMIC_ECONOMIC_SURFACE_RESULT "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
