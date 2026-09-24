#!/usr/bin/env python3
"""Reachable Future x Action Contact Shadow v0.

Observation-only replay. The combat policy/action is unchanged.

Tracks the already-certified Day4 MELON -> Day10 production opportunity from
Day4 h10 through h23. At every self decision:
- whether a Day4 MELON productive-State entry is still physically reachable
- the minimum MOVE...PLANT action sequence from any current unit to an empty tile
- the actual action returned by Body-only
- whether the opportunity remains reachable in the next observed State

Contact classification:
- CONTACT: reachable becomes unreachable at an intermediate Day4 State before h23,
  without actual Day4 MELON entry.
- NO_CONTACT: reachable remains present at every pre-action State through h23,
  but no actual Day4 MELON entry occurs.
- REALIZED: an actual Day4 MELON entry occurs after h10.

MELON is an observation tag for the previously certified public-rule reachable
future, not a Candidate or recommendation.
"""
import copy,json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"reachable_future_action_contact_shadow_v0_{SEED}.json")


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)


def unit_positions(me):
    return [tuple(me["farmer"])] + [tuple(x) for x in (me.get("hands",[]) or [])]


def empty_tiles(me):
    out=[]
    for y,row in enumerate(me.get("tiles",[]) or []):
        for x,t in enumerate(row or []):
            if t is None:
                out.append((x,y))
    return out


def melon_day4_count(me):
    n=0
    for row in me.get("tiles",[]) or []:
        for t in row or []:
            if (isinstance(t,dict) and t.get("kind")=="PLANT"
                and t.get("crop")=="MELON"
                and int(t.get("planted_day",-999))==4):
                n+=1
    return n


def path_actions(src,dst):
    x,y=src; tx,ty=dst
    seq=[]
    while x<tx: seq.append(["EAST"]); x+=1
    while x>tx: seq.append(["WEST"]); x-=1
    while y<ty: seq.append(["SOUTH"]); y+=1
    while y>ty: seq.append(["NORTH"]); y-=1
    seq.append(["PLANT","MELON"])
    return seq


def shadow(obs):
    player=int(obs["player"])
    me=obs["farms"][player]
    private=obs.get("private",{}) or {}
    day=int(obs.get("day",-1))
    hour=int(obs.get("hour",-1))
    seeds=int((private.get("seeds",{}) or {}).get("MELON",0) or 0)
    units=unit_positions(me)
    empties=empty_tiles(me)
    entry_count=melon_day4_count(me)

    remaining_turns=(24-hour) if day==4 else 0
    best=None
    if day==4 and seeds>0 and units and empties:
        candidates=[]
        for ui,u in enumerate(units):
            for e in empties:
                seq=path_actions(u,e)
                candidates.append((len(seq),ui,u,e,seq))
        candidates.sort(key=lambda x:(x[0],x[1],x[2],x[3]))
        best=candidates[0]
    reachable=bool(best is not None and best[0] <= remaining_turns)
    return {
        "day":day,"hour":hour,
        "melon_seed_stock":seeds,
        "unit_positions":[list(x) for x in units],
        "empty_unlocked_count":len(empties),
        "day4_melon_entry_count":entry_count,
        "remaining_action_turns_in_day":remaining_turns,
        "reachable":reachable,
        "min_actions":None if best is None else best[0],
        "min_moves":None if best is None else best[0]-1,
        "selected_unit_index":None if best is None else best[1],
        "selected_unit_position":None if best is None else list(best[2]),
        "selected_empty_tile":None if best is None else list(best[3]),
        "minimum_sequence":None if best is None else best[4],
        "public_future":{
            "origin_day_if_entered":4,
            "next_production_day":10,
            "harvest_eligible_day":14,
        }
    }


def action_by_unit(action,me):
    out=[{"unit_index":0,"role":"farmer","position":list(me["farmer"]),
          "action":copy.deepcopy(action.get("farmer",["PASS"]))}]
    hands=list(me.get("hands",[]) or [])
    acts=list(action.get("hands",[]) or [])
    while len(acts)<len(hands): acts.append(["PASS"])
    for i,pos in enumerate(hands,1):
        out.append({"unit_index":i,"role":"hand","position":list(pos),
                    "action":copy.deepcopy(acts[i-1])})
    return out


def main():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

    records=[]
    pending=None
    start_entry_count=None

    def observed(obs):
        nonlocal pending,start_entry_count
        player=int(obs["player"])
        me=obs["farms"][player]
        d=int(obs.get("day",-1)); h=int(obs.get("hour",-1))

        # The current observation is the post-action State for the previous
        # self decision.
        if pending is not None:
            post=shadow(obs)
            pending["post_state"]={
                "day":post["day"],"hour":post["hour"],
                "reachable":post["reachable"],
                "melon_seed_stock":post["melon_seed_stock"],
                "empty_unlocked_count":post["empty_unlocked_count"],
                "day4_melon_entry_count":post["day4_melon_entry_count"],
                "min_actions":post["min_actions"],
                "minimum_sequence":post["minimum_sequence"],
            }
            pending["actual_entry_realized_after_action"]=(
                post["day4_melon_entry_count"] > pending["pre_state"]["day4_melon_entry_count"]
            )
            pending=None

        action=body_only.agent(obs)

        if d==4 and 10<=h<=23:
            pre=shadow(obs)
            if start_entry_count is None:
                start_entry_count=pre["day4_melon_entry_count"]
            trace=body_only.body.get_last_trace()
            rec={
                "turn":{"day":d,"hour":h},
                "pre_state":pre,
                "actual_action_by_unit":action_by_unit(action,me),
                "actual_action":copy.deepcopy(action),
                "base_action":copy.deepcopy(trace.get("base_action",{})),
                "overlay_changed_farmer":bool(trace.get("overlay_changed_farmer")),
                "overlay_changed_hands":bool(trace.get("overlay_changed_hands")),
                "overlay_changed_market":bool(trace.get("overlay_changed_market")),
                "post_state":None,
                "actual_entry_realized_after_action":False,
            }
            records.append(rec)
            pending=rec
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=observed
    env.run(players)

    # If the final h23 pending record was not closed by another self call,
    # inspect the terminal/day5 observation from env steps.
    if pending is not None:
        final_obs=plain(env.state[SEAT].observation)
        post=shadow(final_obs)
        pending["post_state"]={
            "day":post["day"],"hour":post["hour"],
            "reachable":post["reachable"],
            "melon_seed_stock":post["melon_seed_stock"],
            "empty_unlocked_count":post["empty_unlocked_count"],
            "day4_melon_entry_count":post["day4_melon_entry_count"],
            "min_actions":post["min_actions"],
            "minimum_sequence":post["minimum_sequence"],
        }
        pending["actual_entry_realized_after_action"]=(
            post["day4_melon_entry_count"] > pending["pre_state"]["day4_melon_entry_count"]
        )

    actual_realized=any(r["actual_entry_realized_after_action"] for r in records)
    first_contact=None
    # Intermediate loss only; h23->Day5 is the natural window close and is
    # classified as NO_CONTACT when reachability survived through h23.
    for r in records:
        h=r["turn"]["hour"]
        if h>=23: continue
        if r["pre_state"]["reachable"] and r["post_state"] is not None:
            if (not r["post_state"]["reachable"]) and not r["actual_entry_realized_after_action"]:
                first_contact={
                    "day":4,"hour":h,
                    "actual_action":copy.deepcopy(r["actual_action"]),
                    "pre_min_actions":r["pre_state"]["min_actions"],
                    "post_day":r["post_state"]["day"],
                    "post_hour":r["post_state"]["hour"],
                }
                break

    pre_hours=[r["turn"]["hour"] for r in records if r["pre_state"]["reachable"]]
    reachable_all_pre=(pre_hours==list(range(10,24)))

    if actual_realized:
        classification="REALIZED"
    elif first_contact is not None:
        classification="CONTACT"
    elif reachable_all_pre:
        classification="NO_CONTACT"
    else:
        classification="UNRESOLVED"

    payload={
        "schema":"kaggriculture.strong-origin-v2.reachable-future-action-contact-shadow.v0",
        "seed":SEED,"seat":SEAT,
        "policy_mutated":False,
        "tracked_future":{
            "observation_tag":"Day4 MELON entry -> Day10 production opportunity",
            "candidate":False,
            "recommendation":False,
        },
        "classification":classification,
        "first_contact":first_contact,
        "actual_entry_realized":actual_realized,
        "reachable_at_every_pre_action_state_h10_h23":reachable_all_pre,
        "reachable_pre_hours":pre_hours,
        "records":records,
        "boundary":[
            "The Body's returned actions are unchanged.",
            "MELON is used only as the previously certified reachable-future observation tag.",
            "CONTACT counts only loss at an intermediate Day4 State before h23; natural window close after the final h23 decision is NO_CONTACT if reachability survived through h23.",
            "Reachability is physical under public movement/PLANT rules with seed already held in the current State; no value judgment is made.",
            "No Candidate, Direction, or policy mutation."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REACHABLE_FUTURE_ACTION_CONTACT_SHADOW "+json.dumps({
        "seed":SEED,"classification":classification,
        "first_contact":first_contact,
        "actual_entry_realized":actual_realized,
        "reachable_pre_hours":pre_hours,
        "last_record":records[-1] if records else None,
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
