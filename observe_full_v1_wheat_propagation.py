#!/usr/bin/env python3
"""Shadow observer for WHEAT market propagation from turn 2 to 120.
Records only baseline-vs-Full-v1 WHEAT market inventory deltas and structural sign changes.
No policy behavior is changed.
"""
import importlib.util
import json
from pathlib import Path
from kaggle_environments import make
import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH = "opponents/seyamalam_v21.py"
CASES = ((3514,0),(3528,0),(3530,0),(3554,0),(3561,1))
START, END = 0, 120

def load_opponent():
    spec = importlib.util.spec_from_file_location("seyamalam_v21_prop", OPPONENT_PATH)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.agent

def play(seed, seat, self_module):
    self_module.reset_telemetry()
    opp = load_opponent(); trace=[]
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    def self_wrapped(obs):
        t=len(trace)
        action=self_module.agent(obs)
        m=obs.get("market",{})
        trace.append({"turn":t,"day":obs.get("day"),"wheat_inventory":m.get("inventory",{}).get("WHEAT"),"wheat_price":m.get("prices",{}).get("WHEAT"),"action":action})
        return action
    players=[opp,opp]; players[seat]=self_wrapped
    env.run(players)
    return trace

def segments(ds):
    out=[]; start=0; prev=None
    for i,d in enumerate(ds):
        s=0 if d==0 else (1 if d>0 else -1)
        if prev is None: prev=s; start=i
        elif s!=prev:
            out.append({"start":start,"end":i-1,"sign":prev,"start_delta":ds[start],"end_delta":ds[i-1]})
            start=i; prev=s
    out.append({"start":start,"end":len(ds)-1,"sign":prev,"start_delta":ds[start],"end_delta":ds[-1]})
    return out

def main():
    rows=[]
    for seed,seat in CASES:
        b=play(seed,seat,baseline_agent); c=play(seed,seat,candidate_agent)
        n=min(len(b),len(c),END+1)
        series=[]
        for t in range(n):
            bi=b[t]["wheat_inventory"]; ci=c[t]["wheat_inventory"]
            series.append({"turn":t,"day":b[t]["day"],"baseline_inventory":bi,"candidate_inventory":ci,"delta":None if bi is None or ci is None else ci-bi,"baseline_price":b[t]["wheat_price"],"candidate_price":c[t]["wheat_price"]})
        ds=[x["delta"] for x in series if x["delta"] is not None]
        zeros=[x["turn"] for x in series if x["delta"]==0 and x["turn"]>=2]
        sign_changes=[]; last=None
        for x in series:
            d=x["delta"]
            if d is None: continue
            s=0 if d==0 else (1 if d>0 else -1)
            if last is None: last=s
            elif s!=last:
                sign_changes.append({"turn":x["turn"],"from":last,"to":s,"delta":d}); last=s
        rows.append({"seed":seed,"seat":seat,"turn2_delta":series[2]["delta"] if len(series)>2 else None,"turn120_delta":series[120]["delta"] if len(series)>120 else None,"first_zero_after_2":zeros[0] if zeros else None,"zero_count_after_2":len(zeros),"sign_changes":sign_changes,"segments":segments(ds),"series":series})
    result={"schema":"kaggriculture.full-v1-wheat-propagation.v1","observer_only":True,"agent_mutated":False,"cases":rows}
    Path("full_v1_wheat_propagation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    compact=[]
    for r in rows:
        compact.append({"seed":r["seed"],"turn2_delta":r["turn2_delta"],"turn120_delta":r["turn120_delta"],"first_zero_after_2":r["first_zero_after_2"],"zero_count":r["zero_count_after_2"],"sign_changes":r["sign_changes"][:12]})
    print("WHEAT_PROPAGATION "+json.dumps(compact,separators=(",",":")))
if __name__=="__main__": main()
