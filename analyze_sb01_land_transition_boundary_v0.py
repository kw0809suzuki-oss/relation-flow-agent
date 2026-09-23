#!/usr/bin/env python3
"""SB-01 LAND transition boundary v0.

Existing artifacts only. No new Battle and no policy mutation.

Question:
Around realized BUY_LAND transitions, what did the immediately available
sampled State look like before Expansion, and how quickly did that newly opened
capacity become non-empty/productive afterwards?

This is an event-aligned observation. It does not label LAND as good/bad and
does not infer a causal policy rule.
"""
import json, math, statistics, sys
from pathlib import Path

TRANSITIONS=((1,25,50),(2,50,75))
SAMPLED_DAYS=(0,1,2,3,4,5,6,8,10,12)

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def quantile(xs,p):
    if not xs: return None
    ys=sorted(xs); pos=(len(ys)-1)*p
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)
def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {
      "n":len(xs),"mean":mean(xs),"median":median(xs),
      "q25":quantile(xs,.25),"q75":quantile(xs,.75),
      "min":min(xs) if xs else None,"max":max(xs) if xs else None
    }
def load_one(root,name):
    hits=list(root.glob(f"**/{name}"))
    if not hits: raise SystemExit(f"Missing {name}")
    return json.loads(hits[0].read_text(encoding="utf-8"))
def index_cases(payload):
    return {int(c["seed"]):c for c in payload["cases"]}
def load_cash(root):
    out={}
    for p in root.glob("**/sb01_exact_cash_flow_daily_*.json"):
        if "aggregate" in p.name: continue
        r=json.loads(p.read_text(encoding="utf-8"))
        out[int(r["seed"])]=r
    if len(out)!=50: raise SystemExit(f"Expected 50 Cash files, got {len(out)}")
    bad=[s for s,r in out.items() if r["self"]["error"]!=0 or r["opponent"]["error"]!=0]
    if bad: raise SystemExit(f"Cash reconstruction error: {bad}")
    return out

def state_for(seed,day,early,later,side):
    src=early if day<=6 else later
    return src[seed]["days"][str(day)][side]

def available_days(seed,early,later):
    return sorted(set(map(int,early[seed]["days"])) | set(map(int,later[seed]["days"])))

def crop_total(st):
    return sum(float(v) for v in st["committed_production"]["crop_count"].values())
def animal_total(st):
    return sum(float(v) for v in st["committed_production"]["animal_count"].values())
def seed_total(st):
    return sum(float(v) for v in st.get("seed_inventory_fact",{}).values())
def snapshot(st):
    cap=st["uncommitted_capacity"]
    unlocked=float(cap["unlocked_tiles"])
    empty=float(cap["empty_unlocked_tiles"])
    occupied=unlocked-empty
    return {
      "day":int(st["day"]),
      "cash":float(st["cash"]),
      "unlocked_tiles":unlocked,
      "empty_tiles":empty,
      "occupied_tiles":occupied,
      "occupancy_ratio":(occupied/unlocked if unlocked else None),
      "crop_count":crop_total(st),
      "animal_count":animal_total(st),
      "seed_inventory_total":seed_total(st),
      "committed_mark":float(st["committed_production"]["same_basis_subtotal"]),
      "remaining_turns":float(cap["remaining_season_turns"]),
    }

def land_event_days(cash_side):
    """Return one event per successfully executed BUY_LAND unit in time order."""
    events=[]
    for dstr in sorted(cash_side.get("daily_executed_units",{}),key=lambda x:int(x)):
        d=int(dstr)
        units=int((cash_side["daily_executed_units"].get(dstr,{}) or {}).get("BUY_LAND",0) or 0)
        spend=-float((cash_side.get("daily_ledger",{}).get(dstr,{}) or {}).get("BUY_LAND",0) or 0)
        if units<=0: continue
        for _ in range(units):
            events.append({"day":d,"day_total_spend":spend,"units_that_day":units})
    return events

def sampled_window(seed,event_day,early,later,side):
    ds=available_days(seed,early,later)
    pre=max((d for d in ds if d<=event_day),default=None)
    post=min((d for d in ds if d>=event_day+1),default=None)
    if pre is None: return None
    a=snapshot(state_for(seed,pre,early,later,side))
    b=snapshot(state_for(seed,post,early,later,side)) if post is not None else None
    return {
      "event_day":event_day,
      "pre_sample_day":pre,
      "pre_sample_lag_days":event_day-pre,
      "post_sample_day":post,
      "post_sample_lag_days":(post-event_day if post is not None else None),
      "pre":a,
      "post":b,
      "post_minus_pre":({
         "cash":b["cash"]-a["cash"],
         "empty_tiles":b["empty_tiles"]-a["empty_tiles"],
         "occupied_tiles":b["occupied_tiles"]-a["occupied_tiles"],
         "occupancy_ratio":b["occupancy_ratio"]-a["occupancy_ratio"],
         "crop_count":b["crop_count"]-a["crop_count"],
         "animal_count":b["animal_count"]-a["animal_count"],
         "seed_inventory_total":b["seed_inventory_total"]-a["seed_inventory_total"],
         "committed_mark":b["committed_mark"]-a["committed_mark"],
       } if b is not None else None)
    }

def summarize_events(rows):
    present=[r for r in rows if r is not None]
    out={"n_events":len(present)}
    for key in ("event_day","pre_sample_day","pre_sample_lag_days","post_sample_day","post_sample_lag_days"):
        out[key]=summ([r.get(key) for r in present])
    for phase in ("pre","post"):
        pp=[r[phase] for r in present if r.get(phase) is not None]
        out[phase]={}
        for key in ("cash","unlocked_tiles","empty_tiles","occupied_tiles","occupancy_ratio",
                    "crop_count","animal_count","seed_inventory_total","committed_mark","remaining_turns"):
            out[phase][key]=summ([x[key] for x in pp])
    diffs=[r["post_minus_pre"] for r in present if r.get("post_minus_pre") is not None]
    out["post_minus_pre"]={}
    for key in ("cash","empty_tiles","occupied_tiles","occupancy_ratio","crop_count",
                "animal_count","seed_inventory_total","committed_mark"):
        out["post_minus_pre"][key]=summ([x[key] for x in diffs])

    rate_rows=[]
    for r in present:
        if r.get("post_minus_pre") is None or r.get("post_sample_day") is None:
            continue
        span=r["post_sample_day"]-r["pre_sample_day"]
        if span<=0: continue
        rate_rows.append((span,r["post_minus_pre"]))
    out["sample_span_days"]=summ([span for span,_ in rate_rows])
    out["post_minus_pre_per_sample_day"]={}
    for key in ("cash","empty_tiles","occupied_tiles","occupancy_ratio","crop_count",
                "animal_count","seed_inventory_total","committed_mark"):
        out["post_minus_pre_per_sample_day"][key]=summ([x[key]/span for span,x in rate_rows])
    return out

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    early=index_cases(load_one(root,"sb01_early_daily_economic_localization_v0.json"))
    later=index_cases(load_one(root,"sb01_economic_layers_v0.json"))
    cash=load_cash(root)
    seeds=sorted(set(early)&set(later)&set(cash))
    if len(seeds)!=50: raise SystemExit(f"Expected 50 common seeds, got {len(seeds)}")

    raw=[]
    by_transition={}
    for ordinal,from_tiles,to_tiles in TRANSITIONS:
        side_rows={"self":[],"opponent":[]}
        event_day_only={"self":[],"opponent":[]}
        for seed in seeds:
            for side in ("self","opponent"):
                evs=land_event_days(cash[seed][side])
                ev=evs[ordinal-1] if len(evs)>=ordinal else None
                event_day_only[side].append(ev["day"] if ev else None)
                row=None
                if ev is not None:
                    row=sampled_window(seed,ev["day"],early,later,side)
                    if row:
                        row.update({
                          "seed":seed,"side":side,"transition_ordinal":ordinal,
                          "from_tiles":from_tiles,"to_tiles":to_tiles,
                          "event_day_total_land_spend":ev["day_total_spend"],
                          "event_day_land_units":ev["units_that_day"],
                        })
                        raw.append(row)
                side_rows[side].append(row)

        entry={
          "from_tiles":from_tiles,"to_tiles":to_tiles,
          "self":summarize_events(side_rows["self"]),
          "opponent":summarize_events(side_rows["opponent"]),
          "paired_event_day_gap_opponent_minus_self":summ([
              (o-s) for s,o in zip(event_day_only["self"],event_day_only["opponent"])
              if s is not None and o is not None
          ]),
          "paired_event_day_counts":{
             "self_earlier":sum(1 for s,o in zip(event_day_only["self"],event_day_only["opponent"]) if s is not None and o is not None and s<o),
             "opponent_earlier":sum(1 for s,o in zip(event_day_only["self"],event_day_only["opponent"]) if s is not None and o is not None and o<s),
             "same_day":sum(1 for s,o in zip(event_day_only["self"],event_day_only["opponent"]) if s is not None and o is not None and s==o),
             "paired":sum(1 for s,o in zip(event_day_only["self"],event_day_only["opponent"]) if s is not None and o is not None),
          },
        }
        by_transition[f"{from_tiles}_to_{to_tiles}"]=entry

    # Outer-objective check: does earlier self Expansion correspond to higher/lower terminal self?
    first_self_rows=[r for r in raw if r["side"]=="self" and r["transition_ordinal"]==1]
    terminal_by_seed={int(s):float(early[s]["terminal"]["self"]) for s in seeds}
    margin_by_seed={int(s):float(early[s]["terminal"]["margin"]) for s in seeds}
    early5=[r for r in first_self_rows if r["event_day"]==5]
    late89=[r for r in first_self_rows if r["event_day"]>=8]
    def cohort(rows):
        return {
          "n":len(rows),
          "terminal_self":summ([terminal_by_seed[r["seed"]] for r in rows]),
          "terminal_margin":summ([margin_by_seed[r["seed"]] for r in rows]),
        }
    xs=[float(r["event_day"]) for r in first_self_rows]
    ys=[terminal_by_seed[r["seed"]] for r in first_self_rows]
    mx=mean(xs); my=mean(ys)
    num=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    den=(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))**0.5
    timing_terminal_check={
      "self_first_land_day5":cohort(early5),
      "self_first_land_day8_or_9":cohort(late89),
      "pearson_event_day_vs_terminal_self":(num/den if den else None),
      "boundary":"Descriptive cohort check only; seed composition differs and this is not causal evidence."
    }

    payload={
      "schema":"kaggriculture.sb01.land-transition-boundary.v0",
      "battle_count":50,
      "sampled_days":list(SAMPLED_DAYS),
      "transitions":by_transition,
      "timing_terminal_check":timing_terminal_check,
      "rows":raw,
      "boundary":[
        "Existing artifacts only; no new Battle and no policy mutation.",
        "LAND event day comes from successfully executed BUY_LAND units in the exact Cash ledger.",
        "State snapshots are day-boundary samples, not exact pre/post-turn states.",
        "When the event day itself is not sampled (for example day 7), the nearest earlier sampled day is used and lag is reported explicitly.",
        "Post State is the first sampled day at least one day after the LAND event; its lag is reported explicitly.",
        "Occupancy = 1 - empty_unlocked_tiles / unlocked_tiles. It is a descriptive physical axis, not a strategy rule.",
        "Committed mark uses the existing same-basis public-rule valuation and is kept separate from physical occupancy.",
        "This analysis does not label Expansion early/late, good/bad, or causal."
      ]
    }
    Path("sb01_land_transition_boundary_v0.json").write_text(
      json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={}
    for k,e in by_transition.items():
        compact[k]={
          "paired_event_day_gap_opp_minus_self_mean":e["paired_event_day_gap_opponent_minus_self"]["mean"],
          "event_day_counts":e["paired_event_day_counts"],
          "self_event_day_mean":e["self"]["event_day"]["mean"],
          "opp_event_day_mean":e["opponent"]["event_day"]["mean"],
          "self_pre_empty_mean":e["self"]["pre"]["empty_tiles"]["mean"],
          "opp_pre_empty_mean":e["opponent"]["pre"]["empty_tiles"]["mean"],
          "self_pre_occupancy_mean":e["self"]["pre"]["occupancy_ratio"]["mean"],
          "opp_pre_occupancy_mean":e["opponent"]["pre"]["occupancy_ratio"]["mean"],
          "self_pre_cash_mean":e["self"]["pre"]["cash"]["mean"],
          "opp_pre_cash_mean":e["opponent"]["pre"]["cash"]["mean"],
          "self_post_occupied_gain_mean":e["self"]["post_minus_pre"]["occupied_tiles"]["mean"],
          "opp_post_occupied_gain_mean":e["opponent"]["post_minus_pre"]["occupied_tiles"]["mean"],
          "self_post_occupied_gain_per_sample_day_mean":e["self"]["post_minus_pre_per_sample_day"]["occupied_tiles"]["mean"],
          "opp_post_occupied_gain_per_sample_day_mean":e["opponent"]["post_minus_pre_per_sample_day"]["occupied_tiles"]["mean"],
          "self_post_committed_mark_gain_mean":e["self"]["post_minus_pre"]["committed_mark"]["mean"],
          "opp_post_committed_mark_gain_mean":e["opponent"]["post_minus_pre"]["committed_mark"]["mean"],
          "self_post_committed_mark_gain_per_sample_day_mean":e["self"]["post_minus_pre_per_sample_day"]["committed_mark"]["mean"],
          "opp_post_committed_mark_gain_per_sample_day_mean":e["opponent"]["post_minus_pre_per_sample_day"]["committed_mark"]["mean"],
          "self_pre_lag_mean":e["self"]["pre_sample_lag_days"]["mean"],
          "opp_pre_lag_mean":e["opponent"]["pre_sample_lag_days"]["mean"],
          "self_post_lag_mean":e["self"]["post_sample_lag_days"]["mean"],
          "opp_post_lag_mean":e["opponent"]["post_sample_lag_days"]["mean"],
        }
    compact["timing_terminal_check"]={
      "day5_n":timing_terminal_check["self_first_land_day5"]["n"],
      "day5_terminal_self_mean":timing_terminal_check["self_first_land_day5"]["terminal_self"]["mean"],
      "late_n":timing_terminal_check["self_first_land_day8_or_9"]["n"],
      "late_terminal_self_mean":timing_terminal_check["self_first_land_day8_or_9"]["terminal_self"]["mean"],
      "pearson_event_day_vs_terminal_self":timing_terminal_check["pearson_event_day_vs_terminal_self"],
    }
    print("SB01_LAND_TRANSITION_BOUNDARY "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
