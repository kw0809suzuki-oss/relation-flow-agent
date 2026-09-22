"""Model-side realizable-capacity hypothesis bundle v0.

Flow-chan supplies only the abstract direction. This model body discovers
commitment structures in the current native plan and operationalizes one
hypothesis arm at a time. The hypotheses are probes, not rules or evidence.
"""

from collections import Counter
import os
from x_engine import XField, choose_x_origin, counter_crop_weights, counter_opportunity, counter_weight

_FLOW_ABSTRACTION = None

def set_flow_abstraction(meaning):
    global _FLOW_ABSTRACTION
    _FLOW_ABSTRACTION = dict(meaning or {}) if isinstance(meaning, dict) else None

def get_flow_abstraction():
    return dict(_FLOW_ABSTRACTION or {})

def set_model_selection(selection):
    del selection

def get_model_selected_crop():
    return None

def set_model_direction(direction):
    del direction

BASE_PRICE = {"WHEAT": 25, "STRAWBERRY": 120, "MELON": 250}
SEED_COST = {"WHEAT": 10, "STRAWBERRY": 100, "MELON": 80}
FIRST_YIELD = {"WHEAT": 2, "STRAWBERRY": 10, "MELON": 10}
MAX_YIELD_DAY = {"WHEAT": 4, "STRAWBERRY": 10, "MELON": 12}
SHOP_DEMAND = {
    "WHEAT": {"BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "ICE_CREAM_SHOP", "FARMERS_MARKET"},
    "STRAWBERRY": {"BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"},
    "MELON": set(),
}
STRATEGIES = {
    "BALANCED": {"mix": {"WHEAT": .32, "MELON": .18, "STRAWBERRY": .50}, "occupancy_target": .72, "max_units": 9, "reserve_base": 650},
    "CROP_RUSH": {"mix": {"WHEAT": .20, "MELON": .30, "STRAWBERRY": .50}, "occupancy_target": .80, "max_units": 10, "reserve_base": 500},
    "LIQUID": {"mix": {"WHEAT": .70, "MELON": .20, "STRAWBERRY": .10}, "occupancy_target": .65, "max_units": 7, "reserve_base": 900},
    "ENDGAME": {"mix": {"WHEAT": 1., "MELON": 0., "STRAWBERRY": 0.}, "occupancy_target": .55, "max_units": 5, "reserve_base": 1200},
}

_TELEMETRY = {"origins": Counter(), "distortion_trigger_turns": 0, "crop_trigger_turns": 0,
              "counter_active_turns": 0, "turns": 0, "distortion_sum": 0.0,
              "distortion_max": 0.0, "counter_opportunity_sum": 0.0,
              "counter_opportunity_max": 0.0, "counter_weight_sum": 0.0, "counter_weight_max": 0.0}


def reset_telemetry():
    _TELEMETRY["origins"].clear()
    for k in ("distortion_trigger_turns","crop_trigger_turns","counter_active_turns","turns"):
        _TELEMETRY[k] = 0
    for k in ("distortion_sum","distortion_max","counter_opportunity_sum","counter_opportunity_max","counter_weight_sum","counter_weight_max"):
        _TELEMETRY[k] = 0.0


def get_telemetry():
    turns = _TELEMETRY["turns"]
    return {
        "origins": dict(_TELEMETRY["origins"]),
        "distortion_trigger_turns": _TELEMETRY["distortion_trigger_turns"],
        "crop_trigger_turns": _TELEMETRY["crop_trigger_turns"],
        "counter_active_turns": _TELEMETRY["counter_active_turns"],
        "turns": turns,
        "mean_distortion": _TELEMETRY["distortion_sum"] / turns if turns else 0.0,
        "max_distortion": _TELEMETRY["distortion_max"],
        "mean_counter_opportunity": _TELEMETRY["counter_opportunity_sum"] / turns if turns else 0.0,
        "max_counter_opportunity": _TELEMETRY["counter_opportunity_max"],
        "mean_counter_weight": _TELEMETRY["counter_weight_sum"] / turns if turns else 0.0,
        "max_counter_weight": _TELEMETRY["counter_weight_max"],
    }


def fib_hire_cost(n):
    a,b=1,1
    for _ in range(n): a,b=b,a+b
    return a


def origin_targets(name, day, capacity):
    s=STRATEGIES[name]; mix=dict(s["mix"])
    if day < 7 and name not in ("ENDGAME","LIQUID"):
        mix={"WHEAT":.52,"MELON":.48,"STRAWBERRY":0.}
    elif day >= 24:
        mix={"WHEAT":.82,"MELON":.18,"STRAWBERRY":0.}
    usable=max(8,int(capacity*s["occupancy_target"]))
    return {c:int(usable*w) for c,w in mix.items()}


def agent(obs):
    player=obs["player"]; me=obs["farms"][player]; opp=obs["farms"][1-player]
    private=obs["private"]; day=obs["day"]; remaining_days=30-day
    tiles=me["tiles"]; prices=obs.get("market",{}).get("prices",{}); shops=obs.get("town",{}).get("unlocked_shops",[])
    market=[]
    my_plants={c:[] for c in BASE_PRICE}; opp_plants={c:0 for c in BASE_PRICE}
    harvest_targets=[]; water_targets=[]; weeds=[]; empty_tiles=[]; unlocked_count=0
    for y,row in enumerate(tiles):
        for x,tile in enumerate(row):
            if tile != "LOCKED": unlocked_count += 1
            if tile == "LOCKED": continue
            if tile is None: empty_tiles.append((x,y)); continue
            if not isinstance(tile,dict): continue
            kind=tile.get("kind")
            if kind=="WEED": weeds.append((x,y))
            elif kind=="PLANT":
                crop=tile.get("crop")
                if crop in my_plants:
                    my_plants[crop].append((x,y)); age=day-tile.get("planted_day",day); yu=tile.get("yield_units",0)
                    if yu>0 and (crop=="STRAWBERRY" or age>=MAX_YIELD_DAY[crop]): harvest_targets.append((x,y))
                    if not tile.get("watered_today",False): water_targets.append((x,y))
    for row in opp.get("tiles",[]):
        for tile in row:
            if isinstance(tile,dict) and tile.get("kind")=="PLANT" and tile.get("crop") in opp_plants:
                opp_plants[tile["crop"]]+=1
    capacity=unlocked_count; occupied=capacity-len(empty_tiles); occupancy=occupied/capacity if capacity else 1.
    field=XField(day=day, remaining_days=remaining_days, my_money=me.get("money",0), opp_money=opp.get("money",0),
                 my_land=len(me.get("unlocked_quadrants",[])), opp_land=len(opp.get("unlocked_quadrants",[])),
                 my_hands=len(me.get("hands",[])), opp_hands=len(opp.get("hands",[])), prices=prices,
                 my_supply={c:len(my_plants[c]) for c in BASE_PRICE}, opp_supply=opp_plants)
    xdecision=choose_x_origin(field,BASE_PRICE)
    strategy_name=xdecision.origin; strategy=STRATEGIES[strategy_name]
    targets=origin_targets(strategy_name,day,capacity)
    town_demand={c:sum(1 for shop in shops if shop in SHOP_DEMAND[c]) for c in BASE_PRICE}
    scores=counter_crop_weights(field,BASE_PRICE,town_demand)
    for crop in BASE_PRICE:
        if remaining_days <= FIRST_YIELD[crop]+1: scores[crop]=0.
    best_crop=max(scores,key=scores.get)
    opportunity=counter_opportunity(field,BASE_PRICE); cweight=counter_weight(field,BASE_PRICE)
    _TELEMETRY["turns"] += 1; _TELEMETRY["origins"][strategy_name] += 1
    _TELEMETRY["distortion_sum"] += xdecision.distortion; _TELEMETRY["distortion_max"] = max(_TELEMETRY["distortion_max"], xdecision.distortion)
    _TELEMETRY["counter_opportunity_sum"] += opportunity; _TELEMETRY["counter_opportunity_max"] = max(_TELEMETRY["counter_opportunity_max"], opportunity)
    _TELEMETRY["counter_weight_sum"] += cweight; _TELEMETRY["counter_weight_max"] = max(_TELEMETRY["counter_weight_max"], cweight)
    if xdecision.distortion >= .10: _TELEMETRY["distortion_trigger_turns"] += 1
    if scores[best_crop] >= 1.20: _TELEMETRY["crop_trigger_turns"] += 1
    if cweight > 0.0: _TELEMETRY["counter_active_turns"] += 1
    if xdecision.distortion >= .10 or scores[best_crop] >= 1.20:
        shift=max(2,int(capacity*.12)); donors=[c for c in targets if c!=best_crop and targets[c]>0]
        for donor in sorted(donors,key=lambda c:scores[c]):
            take=min(shift,targets[donor]); targets[donor]-=take; targets[best_crop]+=take; shift-=take
            if shift<=0: break
    if cweight > 0.0 and scores[best_crop] > 0.0:
        shift=max(1,int(capacity*.12*cweight)); donors=[c for c in targets if c!=best_crop and targets[c]>0]
        for donor in sorted(donors,key=lambda c:scores[c]):
            take=min(shift,targets[donor]); targets[donor]-=take; targets[best_crop]+=take; shift-=take
            if shift<=0: break
    reserve=strategy["reserve_base"]+20*occupied; projected_cash=me["money"]
    for item in ("WHEAT","STRAWBERRY","MELON","MILK","WOOL","EGG","FERTILIZER"):
        qty=private.get("shed",{}).get(item,0)
        if qty>0 and len(market)<10: market.append(["SELL",item,qty])
    quadrants=len(me.get("unlocked_quadrants",[])); land_cost={1:1000,2:2000,3:4000}.get(quadrants)
    current_units=1+len(me.get("hands",[]))
    land_activation_capacity=current_units*max(1,remaining_days)
    land_realizable_ok=len(empty_tiles) < land_activation_capacity
    if strategy_name not in ("LIQUID","ENDGAME") and land_cost and remaining_days>=9 and occupancy>=strategy["occupancy_target"] and projected_cash-land_cost>=reserve and len(market)<10:
        if not (str((_FLOW_ABSTRACTION or {}).get("phase","") or "").upper()=="OPTION_PRESERVATION" and os.getenv("ORIGIN_COMMITMENT_HYPOTHESIS","none").strip().lower()=="land_activation" and not land_realizable_ok):
            market.append(["BUY_LAND"]); projected_cash-=land_cost
    seed_plan=[]
    for crop in BASE_PRICE:
        have=private.get("seeds",{}).get(crop,0); live=len(my_plants[crop]); need=max(0,targets[crop]-live-have)
        if need<=0 or scores[crop]<=0: continue
        affordable=max(0,int((projected_cash-reserve)//SEED_COST[crop])); buy=min(need,affordable,8)
        if buy>0: seed_plan.append((scores[crop],crop,buy))
    abstraction_phase=str((_FLOW_ABSTRACTION or {}).get("phase","") or "").upper()
    realizable_received=abstraction_phase=="OPTION_PRESERVATION"
    hypothesis_mode=os.getenv("ORIGIN_COMMITMENT_HYPOTHESIS","none").strip().lower()

    immediate_planting_surface=min(len(empty_tiles),1+len(me.get("hands",[])))
    existing_seed_commitment=sum(int(private.get("seeds",{}).get(c,0) or 0) for c in BASE_PRICE)
    seed_realizable_budget=max(0,immediate_planting_surface-existing_seed_commitment)

    for _,crop,buy in sorted(seed_plan,reverse=True):
        if len(market)>=10: break
        if realizable_received and hypothesis_mode=="seed_surface":
            buy=min(buy,seed_realizable_budget)
            if buy<=0: continue
        cost=buy*SEED_COST[crop]
        if projected_cash-cost>=reserve:
            market.append(["BUY_SEED",crop,buy]); projected_cash-=cost
            if realizable_received and hypothesis_mode=="seed_surface":
                seed_realizable_budget=max(0,seed_realizable_budget-buy)
    work=len(water_targets)+len(harvest_targets)+len(weeds)+max(0,sum(targets.values())-sum(len(v) for v in my_plants.values()))
    desired=1+min(strategy["max_units"]-1,max(1,(work+7)//8)); current=1+len(me.get("hands",[])); hires=me.get("hires_today",0)
    native_desired=desired
    if realizable_received and hypothesis_mode=="hire_workload":
        realizable_units=max(1,min(strategy["max_units"],(work+7)//8))
        desired=min(desired,realizable_units)
    while current<desired and len(market)<10:
        cost=fib_hire_cost(hires); value=60 if strategy_name=="CROP_RUSH" else 50
        if cost>value or projected_cash-cost<reserve: break
        market.append(["HIRE"]); projected_cash-=cost; hires+=1; current+=1
    def nearest(points,x,y): return min(points,key=lambda p:abs(p[0]-x)+abs(p[1]-y)) if points else None
    def move(target,x,y):
        tx,ty=target
        if x<tx:return ["EAST"]
        if x>tx:return ["WEST"]
        if y<ty:return ["SOUTH"]
        if y>ty:return ["NORTH"]
        return ["PASS"]
    deficits={c:targets[c]-len(my_plants[c])-private.get("seeds",{}).get(c,0) for c in BASE_PRICE}
    priority=sorted(BASE_PRICE,key=lambda c:(deficits[c]>0,scores[c]),reverse=True)
    def choose_crop(seed_allowance):
        for c in priority:
            if scores[c]>0 and len(my_plants[c])<targets[c] and seed_allowance.get(c,0)>0:return c
        return None
    def unit_action(x,y,seeds):
        cur=tiles[y][x]
        if isinstance(cur,dict):
            if cur.get("kind")=="WEED":return ["DIG"]
            if cur.get("kind")=="PLANT":
                crop=cur.get("crop"); age=day-cur.get("planted_day",day)
                if cur.get("yield_units",0)>0 and (crop=="STRAWBERRY" or (crop in MAX_YIELD_DAY and age>=MAX_YIELD_DAY[crop])):return ["HARVEST"]
                if not cur.get("watered_today",False):return ["WATER"]
        if cur is None:
            crop=choose_crop(seeds)
            if crop: seeds[crop]-=1; return ["PLANT",crop]
        for points in (harvest_targets,water_targets,weeds):
            t=nearest(points,x,y)
            if t is not None:return move(t,x,y)
        if empty_tiles and any(len(my_plants[c])<targets[c] for c in targets):
            t=nearest(empty_tiles,x,y)
            if t is not None:return move(t,x,y)
        return ["PASS"]
    seeds={c:private.get("seeds",{}).get(c,0) for c in BASE_PRICE}
    fx,fy=me["farmer"]; farmer_action=unit_action(fx,fy,seeds)
    hand_actions=[unit_action(hx,hy,seeds) for hx,hy in me.get("hands",[])]
    return {"farmer":farmer_action,"hands":hand_actions,"market":market}
