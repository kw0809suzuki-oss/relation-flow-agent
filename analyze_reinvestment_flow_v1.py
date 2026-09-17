#!/usr/bin/env python3
"""Outside-in observer for the Master-vs-Flow coordinate.

No policy change. Ask only where the existing Agent's asset loop reconnects:
capital -> asset stock -> liquidation -> reinvestment/expansion -> next asset stock -> terminal.
"""
import json
from pathlib import Path

SRC=Path("scale_baseline_v1.json")
OUT=Path("reinvestment_flow_v1.json")


def analyze(case):
    rows=case["observations"]
    events=[]
    for prev,cur in zip(rows,rows[1:]):
        money_delta=cur["money"]-prev["money"]
        stock_delta=cur["produced_value"]-prev["produced_value"]
        expanded=(cur["land"]>prev["land"] or cur["hands"]>prev["hands"] or
                  ((cur.get("animals") or 0)>(prev.get("animals") or 0)))
        liquidation=(money_delta>0 and stock_delta<0)
        if liquidation or expanded:
            events.append({"day":cur["day"],"money_delta":money_delta,"stock_delta":stock_delta,
                           "liquidation":liquidation,"expanded":expanded,
                           "land":cur["land"],"hands":cur["hands"],"animals":cur.get("animals"),
                           "stock":cur["produced_value"]})
    # Descriptive connection: expansion within 2 observed days after a liquidation.
    liquid=[e for e in events if e["liquidation"]]
    exp=[e for e in events if e["expanded"]]
    connected=[]
    for l in liquid:
        nxt=next((e for e in exp if l["day"]<=e["day"]<=l["day"]+2),None)
        connected.append({"liquidation_day":l["day"],"expansion_day":nxt["day"] if nxt else None})
    return {"seed":case["seed"],"seat":case["seat"],"terminal":case["terminal"],
            "liquidation_events":len(liquid),"expansion_events":len(exp),
            "liquidation_to_expansion_links":sum(x["expansion_day"] is not None for x in connected),
            "links":connected,"events":events}


def main():
    data=json.loads(SRC.read_text())
    cases=[analyze(c) for c in data["cases"]]
    liq=sum(c["liquidation_events"] for c in cases); links=sum(c["liquidation_to_expansion_links"] for c in cases)
    out={"coordinate":"asset formation -> liquidation -> reinvestment -> next asset formation -> terminal",
         "policy_mutated":False,"boundary":"descriptive only; temporal adjacency is not causal attribution",
         "cases":cases,"summary":{"case_count":len(cases),"liquidation_events":liq,
         "liquidation_to_expansion_links":links,"link_rate":(links/liq if liq else None)}}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("REINVESTMENT_FLOW_V1 "+json.dumps(out["summary"],separators=(",",":")))
if __name__=="__main__": main()
