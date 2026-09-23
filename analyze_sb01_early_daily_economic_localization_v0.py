#!/usr/bin/env python3
"""SB-01 Early Daily Economic Localization v0.

Uses the same derive_side() boundary as SB-01 Economic Layers v0.
No total score and no causal conclusion. The goal is temporal localization:
when do capacity and committed-production gaps first appear across Day 0..6?
"""
import json
import statistics
import sys
from pathlib import Path

from analyze_sb01_economic_layers_v0 import derive_side, CROPS, ANIMALS

DAYS = tuple(range(0, 7))


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def summarize_pair(rows, getter):
    self_vals=[getter(r["self"]) for r in rows]
    opp_vals=[getter(r["opponent"]) for r in rows]
    gaps=[o-s for s,o in zip(self_vals,opp_vals)]
    return {
        "self_absolute_mean": mean(self_vals),
        "opponent_absolute_mean": mean(opp_vals),
        "mean_gap_opponent_minus_self": mean(gaps),
        "median_gap_opponent_minus_self": median(gaps),
        "opponent_ahead_cases": sum(g>0 for g in gaps),
        "self_ahead_cases": sum(g<0 for g in gaps),
        "equal_cases": sum(g==0 for g in gaps),
        "min_gap": min(gaps) if gaps else None,
        "max_gap": max(gaps) if gaps else None,
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_early_daily_input_*.json"))
    if not files:
        files=sorted(root.glob("**/sb01_early_daily_input_*.json"))
    if not files:
        raise SystemExit("No early-daily input files found")

    cases=[]
    missing=[]
    for path in files:
        raw=json.loads(path.read_text(encoding="utf-8"))
        seed=int(raw["seed"]); seat=int(raw["seat"])
        if any(str(d) not in raw["state_export"].get(str(seat),{}) for d in DAYS) or any(
            str(d) not in raw["state_export"].get(str(1-seat),{}) for d in DAYS
        ):
            missing.append(seed); continue
        perday={}
        for d in DAYS:
            so=raw["state_export"][str(seat)][str(d)]["observation"]
            oo=raw["state_export"][str(1-seat)][str(d)]["observation"]
            perday[str(d)]={"self":derive_side(so),"opponent":derive_side(oo)}
        cases.append({"seed":seed,"seat":seat,"terminal":raw["terminal_result"],"days":perday})

    if missing:
        raise SystemExit(f"Missing days for seeds {missing}")

    days={}
    for d in DAYS:
        rows=[c["days"][str(d)] for c in cases]
        cash=summarize_pair(rows, lambda s:s["cash"])
        unlocked=summarize_pair(rows, lambda s:s["uncommitted_capacity"]["unlocked_tiles"])
        empty=summarize_pair(rows, lambda s:s["uncommitted_capacity"]["empty_unlocked_tiles"])
        crop=summarize_pair(rows, lambda s:s["committed_production"]["crop_current_price_potential_mark"])
        animal=summarize_pair(rows, lambda s:s["committed_production"]["animal_base_current_price_potential_mark"])
        committed=summarize_pair(rows, lambda s:s["committed_production"]["same_basis_subtotal"])

        crop_by_type={}
        for c in CROPS:
            crop_by_type[c]=summarize_pair(rows, lambda s,k=c:s["committed_production"]["crop_mark_by_type"].get(k,0))
        animal_by_type={}
        for a in ANIMALS:
            animal_by_type[a]=summarize_pair(rows, lambda s,k=a:s["committed_production"]["animal_mark_by_type"].get(k,0))

        # Cross-layer cases: self cash not behind while opponent production ahead.
        cross=[]
        for c in cases:
            r=c["days"][str(d)]
            cash_gap=r["opponent"]["cash"]-r["self"]["cash"]
            prod_gap=(r["opponent"]["committed_production"]["same_basis_subtotal"]-
                      r["self"]["committed_production"]["same_basis_subtotal"])
            if cash_gap <= 0 and prod_gap > 0:
                cross.append({"seed":c["seed"],"cash_gap":cash_gap,"committed_gap":prod_gap})

        days[str(d)]={
            "cash":cash,
            "unlocked_tiles":unlocked,
            "empty_unlocked_tiles":empty,
            "crop_production_mark":crop,
            "animal_production_mark":animal,
            "committed_production_mark":committed,
            "crop_mark_by_type":crop_by_type,
            "animal_mark_by_type":animal_by_type,
            "cross_layer":{
                "cash_not_behind_but_production_behind_cases":len(cross),
                "mean_production_gap_in_those_cases":mean([x["committed_gap"] for x in cross]) if cross else None,
                "seeds":[x["seed"] for x in cross],
            },
        }

    # Mechanical localization only: first day where opponent mean committed-production gap > 0.
    first_mean_prod_ahead=None
    first_all50_prod_ahead=None
    for d in DAYS:
        s=days[str(d)]["committed_production_mark"]
        if first_mean_prod_ahead is None and s["mean_gap_opponent_minus_self"] > 0:
            first_mean_prod_ahead=d
        if first_all50_prod_ahead is None and s["opponent_ahead_cases"] == len(cases):
            first_all50_prod_ahead=d

    terminal_self=[float(c["terminal"]["self"]) for c in cases]
    terminal_opp=[float(c["terminal"]["opponent"]) for c in cases]
    terminal_margin=[float(c["terminal"]["margin"]) for c in cases]

    payload={
        "schema":"kaggriculture.sb01.early-daily-economic-localization.v0",
        "battle_count":len(cases),
        "target_days":list(DAYS),
        "terminal_absolute":{
            "mean_self":mean(terminal_self),
            "mean_opponent":mean(terminal_opp),
            "mean_margin":mean(terminal_margin),
            "wins":sum(x>0 for x in terminal_margin),
        },
        "days":days,
        "mechanical_localization":{
            "first_day_opponent_mean_committed_production_ahead":first_mean_prod_ahead,
            "first_day_opponent_committed_production_ahead_50_of_50":first_all50_prod_ahead,
        },
        "boundary":[
            "Temporal localization only.",
            "No Action cause is inferred.",
            "Capacity metrics remain physical and are not added to monetary marks.",
            "Production marks reuse the same explicit assumptions as analyze_sb01_economic_layers_v0.py.",
        ],
        "cases":cases,
    }
    Path("sb01_early_daily_economic_localization_v0.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
        "battle_count":len(cases),
        "terminal":payload["terminal_absolute"],
        "mechanical_localization":payload["mechanical_localization"],
        "days":{
            str(d):{
                "cash_gap":days[str(d)]["cash"]["mean_gap_opponent_minus_self"],
                "unlocked_gap":days[str(d)]["unlocked_tiles"]["mean_gap_opponent_minus_self"],
                "empty_gap":days[str(d)]["empty_unlocked_tiles"]["mean_gap_opponent_minus_self"],
                "crop_gap":days[str(d)]["crop_production_mark"]["mean_gap_opponent_minus_self"],
                "animal_gap":days[str(d)]["animal_production_mark"]["mean_gap_opponent_minus_self"],
                "committed_gap":days[str(d)]["committed_production_mark"]["mean_gap_opponent_minus_self"],
                "production_ahead_cases":days[str(d)]["committed_production_mark"]["opponent_ahead_cases"],
                "cash_not_behind_but_production_behind":days[str(d)]["cross_layer"]["cash_not_behind_but_production_behind_cases"],
            } for d in DAYS
        }
    }
    print("SB01_EARLY_DAILY_LOCALIZATION "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
