#!/usr/bin/env python3
"""Cash Flow Time Profile Observer v2.

Reuses the v1 descriptive money trough -> next peak wave definition, then asks
how that observed money flow changes as remaining time shrinks.

This is diagnostic only. It does not claim causal profit attribution and does
not change the terminal-money objective.
"""
import json, statistics
import observe_cash_flow_wave_v1 as v1

BANDS=[("day00_09",0,9),("day10_19",10,19),("day20_24",20,24),("day25_29",25,29)]

def mean(xs): return statistics.mean(xs) if xs else None

def percentile(xs,q):
    if not xs: return None
    ys=sorted(xs)
    if len(ys)==1: return ys[0]
    pos=(len(ys)-1)*q
    lo=int(pos); hi=min(lo+1,len(ys)-1); f=pos-lo
    return ys[lo]*(1-f)+ys[hi]*f

def band_summary(rows,start,end):
    waves=[w for r in rows for w in r["waves"] if start <= w["trough_day"] <= end]
    durations=[w["recovery_turns"] for w in waves]
    gains=[w["recovery_gain"] for w in waves]
    total_gain=sum(gains)
    total_turns=sum(durations)
    return {
      "matches":len(rows),
      "wave_count":len(waves),
      "mean_waves_per_match":len(waves)/len(rows) if rows else None,
      "mean_recovery_turns":mean(durations),
      "median_recovery_turns":statistics.median(durations) if durations else None,
      "p90_recovery_turns":percentile(durations,0.9),
      "mean_recovery_gain":mean(gains),
      "median_recovery_gain":statistics.median(gains) if gains else None,
      "total_recovery_gain":total_gain,
      "recovery_gain_per_recovery_turn":(total_gain/total_turns) if total_turns else None,
    }

def main():
    rows=[v1.play(int(seed),int(seat)) for seed,seat in v1.base.DEFAULT_CASES]
    ranked=sorted(rows,key=lambda r:r["terminal_self"])
    n=min(4,max(1,len(ranked)//3))
    groups={"low_terminal":ranked[:n],"high_terminal":ranked[-n:]}
    profiles={}
    for name,group in groups.items():
        profiles[name]={
          "mean_terminal":mean([r["terminal_self"] for r in group]),
          "bands":{label:band_summary(group,start,end) for label,start,end in BANDS}
        }
    comparisons={}
    for label,_,_ in BANDS:
        h=profiles["high_terminal"]["bands"][label]
        l=profiles["low_terminal"]["bands"][label]
        comparisons[label]={
          "high_minus_low_waves_per_match":h["mean_waves_per_match"]-l["mean_waves_per_match"],
          "high_minus_low_recovery_turns":h["mean_recovery_turns"]-l["mean_recovery_turns"],
          "high_minus_low_recovery_gain":h["mean_recovery_gain"]-l["mean_recovery_gain"],
          "high_minus_low_gain_per_turn":h["recovery_gain_per_recovery_turn"]-l["recovery_gain_per_recovery_turn"],
        }
    out={
      "schema":"cash-flow-time-profile.v2",
      "objective":"terminal self",
      "definition":"v1 money trough -> next money peak, grouped by trough day; descriptive only",
      "bands":[{"label":x,"start_day":a,"end_day":b} for x,a,b in BANDS],
      "profiles":profiles,
      "comparisons":comparisons,
      "all_matches":rows,
      "boundary":[
        "recovery_gain is observed cash change, not profit or produced value",
        "local money extrema can reflect buy/sell microstructure rather than an independent capital cycle",
        "band assignment uses trough day; a recovery peak may cross a band boundary",
        "terminal reward/final processing is not part of the observed money wave"
      ]
    }
    with open("cash_flow_time_profile_v2.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
    print("CASH_FLOW_TIME_PROFILE_V2 "+json.dumps({
      "low_terminal":profiles["low_terminal"]["mean_terminal"],
      "high_terminal":profiles["high_terminal"]["mean_terminal"],
      "comparisons":comparisons
    },separators=(",",":")))

if __name__=="__main__": main()
