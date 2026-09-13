from collections import Counter

from x_engine import XField, counter_crop_weights, counter_opportunity

BASE_PRICE = {"WHEAT": 25, "STRAWBERRY": 120, "MELON": 250}
SEED_COST = {"WHEAT": 10, "STRAWBERRY": 100, "MELON": 80}
FIRST_YIELD = {"WHEAT": 2, "STRAWBERRY": 10, "MELON": 10}
MAX_YIELD_DAY = {"WHEAT": 4, "STRAWBERRY": 10, "MELON": 12}
SHOP_DEMAND = {
    "WHEAT": {"BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "ICE_CREAM_SHOP", "FARMERS_MARKET"},
    "STRAWBERRY": {"BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"},
    "MELON": set(),
}
COMPONENTS = ("ORIGIN", "CROP", "COUNTER", "LABOR", "PRODUCTION", "SELLING", "LIQUID", "ENDGAME", "MARKET")

_TELEMETRY = {"turns": 0, "relation_sum": Counter(), "weight_sum": Counter(), "allocation_sum": Counter()}
_TRACE = []
_GROWTH_PREV_DAY = None
_GROWTH_CURRENT_DAY = None
_GROWTH_CURRENT_STATE = None


def reset_telemetry():
    _TELEMETRY["turns"] = 0
    _TELEMETRY["relation_sum"].clear()
    _TELEMETRY["weight_sum"].clear()
    _TELEMETRY["allocation_sum"].clear()


def reset_trace():
    global _GROWTH_PREV_DAY, _GROWTH_CURRENT_DAY, _GROWTH_CURRENT_STATE
    _TRACE.clear(); _GROWTH_PREV_DAY = None; _GROWTH_CURRENT_DAY = None; _GROWTH_CURRENT_STATE = None


def get_trace(): return list(_TRACE)


def get_telemetry():
    t = _TELEMETRY["turns"]
    return {
        "turns": t,
        "mean_relations": {k: _TELEMETRY["relation_sum"][k] / t if t else 0.0 for k in _TELEMETRY["relation_sum"]},
        "mean_weights": {k: _TELEMETRY["weight_sum"][k] / t if t else 0.0 for k in COMPONENTS},
        "mean_allocation": {c: _TELEMETRY["allocation_sum"][c] / t if t else 0.0 for c in BASE_PRICE},
    }


def fib_hire_cost(n):
    a,b=1,1
    for _ in range(n): a,b=b,a+b
    return a


def clamp01(x): return max(0.0, min(1.0, float(x)))


def opponent_growth_field(field, day):
    global _GROWTH_PREV_DAY, _GROWTH_CURRENT_DAY, _GROWTH_CURRENT_STATE
    supply = sum(field.opp_supply.values())
    current = {"day": day, "money": float(field.opp_money), "land": float(field.opp_land), "hands": float(field.opp_hands), "supply": float(supply)}
    if _GROWTH_CURRENT_DAY is None:
        _GROWTH_CURRENT_DAY = day; _GROWTH_CURRENT_STATE = current
    elif day > _GROWTH_CURRENT_DAY:
        _GROWTH_PREV_DAY = _GROWTH_CURRENT_STATE; _GROWTH_CURRENT_DAY = day; _GROWTH_CURRENT_STATE = current
    else:
        _GROWTH_CURRENT_STATE = current
    if _GROWTH_PREV_DAY is None:
        velocity = {"money":0.0,"land":0.0,"hands":0.0,"supply":0.0}
    else:
        velocity = {k: current[k] - _GROWTH_PREV_DAY[k] for k in ("money","land","hands","supply")}
    expansion_level = 0.5 * clamp01(current["land"] / 3.0) + 0.5 * clamp01(current["hands"] / 12.0)
    production_level = current["supply"] / (current["supply"] + 30.0) if current["supply"] > 0 else 0.0
    capital_level = current["money"] / (current["money"] + 10000.0) if current["money"] > 0 else 0.0
    expansion_velocity = 0.5 * clamp01(max(0.0, velocity["land"]) / 1.0) + 0.5 * clamp01(max(0.0, velocity["hands"]) / 3.0)
    production_velocity = clamp01(max(0.0, velocity["supply"]) / 10.0)
    capital_velocity = max(0.0, velocity["money"]) / (max(0.0, velocity["money"]) + 5000.0) if velocity["money"] > 0 else 0.0
    momentum = (expansion_velocity + production_velocity + capital_velocity) / 3.0
    return {"expansion":{"level":expansion_level,"velocity":expansion_velocity},"production":{"level":production_level,"velocity":production_velocity},"capital":{"level":capital_level,"velocity":capital_velocity},"momentum":momentum,"raw_velocity":velocity}


def describe_opponent_cycle(growth):
    velocity=growth["raw_velocity"]
    expansion_signal=growth["expansion"]["velocity"]
    production_signal=growth["production"]["velocity"]
    collection_signal=clamp01(max(0.0,velocity["money"])/5000.0)
    reinvestment_signal=clamp01(expansion_signal*clamp01(max(0.0,-velocity["money"])/3000.0))
    signals={"expansion":expansion_signal,"production":production_signal,"collection":collection_signal,"reinvestment":reinvestment_signal}
    strongest=max(signals,key=signals.get); phase=strongest if signals[strongest]>=0.12 else "unclear"
    text=("Opponent cycle is unclear; no single growth motion dominates." if phase=="unclear" else f"Opponent shows {phase} motion. Expansion={expansion_signal:.2f}, production={production_signal:.2f}, collection={collection_signal:.2f}, reinvestment={reinvestment_signal:.2f}. Cause remains unconfirmed.")
    return {"phase":phase,"text":text,"signals":signals,"momentum":growth["momentum"],"growth":{"expansion_level":growth["expansion"]["level"],"production_level":growth["production"]["level"],"capital_level":growth["capital"]["level"]},"uncertain":phase=="unclear"}


def relation_layer(field, capacity, occupied, visible_work):
    occupancy = occupied / capacity if capacity else 1.0
    units = max(1, field.my_hands + 1)
    price_ratios=[float(field.prices.get(crop,base))/float(base) for crop,base in BASE_PRICE.items() if base>0]
    market_peak=max(price_ratios,default=1.0); market_floor=min(price_ratios,default=1.0)
    money_scale=max(1000.0,field.my_money,field.opp_money)
    return {
        "capital_pressure":clamp01((900.0-field.my_money)/900.0),
        "labor_pressure":clamp01(visible_work/max(1.0,units*6.0)),
        "production_pressure":clamp01((0.72-occupancy)/0.72),
        "market_opportunity":clamp01((market_peak-1.0)/0.75),
        "market_distortion":clamp01((market_peak-market_floor)/1.0),
        "time_pressure":clamp01(1.0-field.remaining_days/30.0),
        "opponent_pressure":clamp01((field.opp_money-field.my_money)/money_scale+0.5),
        "counter_opportunity":clamp01(counter_opportunity(field,BASE_PRICE)),
    }


def origin_read(rel, field_description):
    weights=component_weights(rel)
    return {"field_description":field_description,"attention":{"opponent_motion":field_description["momentum"],"expansion":field_description["signals"]["expansion"],"production":field_description["signals"]["production"],"collection":field_description["signals"]["collection"],"reinvestment":field_description["signals"]["reinvestment"]},"weights":weights}


def component_weights(rel):
    raw={
        "ORIGIN":0.35+0.25*(1.0-rel["market_distortion"]),
        "CROP":0.25+0.55*rel["market_opportunity"]+0.20*rel["production_pressure"],
        "COUNTER":0.70*rel["counter_opportunity"]+0.30*rel["opponent_pressure"],
        "LABOR":0.15+0.85*rel["labor_pressure"],
        "PRODUCTION":0.20+0.70*rel["production_pressure"]+0.20*rel["market_opportunity"],
        "SELLING":0.10+0.50*rel["market_opportunity"]+0.35*rel["time_pressure"],
        "LIQUID":0.10+0.45*rel["capital_pressure"]+0.45*rel["time_pressure"],
        "ENDGAME":clamp01((rel["time_pressure"]-0.78)/0.22),
        "MARKET":0.15+0.55*rel["market_distortion"]+0.25*rel["opponent_pressure"],
    }
    total=sum(max(0.0,v) for v in raw.values()) or 1.0
    return {k:max(0.0,raw[k])/total for k in COMPONENTS}


def compose_flow(field, rel, weights, scores, capacity, occupied):
    production_scale=clamp01(0.35+0.55*weights["PRODUCTION"]+0.30*weights["CROP"]-0.35*weights["LIQUID"]-0.55*weights["ENDGAME"])
    desired_occupancy=0.45+0.45*production_scale
    reserve=int(250+900*weights["LIQUID"]+700*weights["ENDGAME"]+250*rel["capital_pressure"])
    labor_intensity=clamp01(0.20+0.85*weights["LABOR"]+0.20*weights["PRODUCTION"]-0.45*weights["ENDGAME"])
    land_intensity=clamp01(0.15+0.65*weights["PRODUCTION"]+0.25*weights["CROP"]-0.60*weights["LIQUID"])
    selling_intensity=clamp01(0.15+0.75*weights["SELLING"]+0.75*weights["ENDGAME"])
    crop_signal={}; avg_opp=sum(field.opp_supply.get(c,0) for c in BASE_PRICE)/max(1,len(BASE_PRICE))
    for crop in BASE_PRICE:
        base=max(0.0,float(scores.get(crop,0.0))); scarcity=max(0.0,avg_opp-field.opp_supply.get(crop,0))/max(1.0,avg_opp+1.0)
        crop_signal[crop]=0.15*weights["ORIGIN"]+base*(0.55*weights["CROP"]+0.30*weights["MARKET"])+scarcity*weights["COUNTER"]
    usable=max(occupied,int(capacity*desired_occupancy)); usable=max(1,min(capacity,usable)); total=sum(crop_signal.values())
    if total<=0: crop_signal={c:1.0 for c in BASE_PRICE}; total=float(len(BASE_PRICE))
    targets={c:int(usable*crop_signal[c]/total) for c in BASE_PRICE}; remainder=usable-sum(targets.values())
    for crop in sorted(BASE_PRICE,key=lambda c:crop_signal[c],reverse=True):
        if remainder<=0: break
        targets[crop]+=1; remainder-=1
    return {"targets":targets,"reserve":reserve,"labor_intensity":labor_intensity,"land_intensity":land_intensity,"selling_intensity":selling_intensity,"desired_occupancy":desired_occupancy}


def agent(obs):
    player=obs["player"]; me=obs["farms"][player]; opp=obs["farms"][1-player]; private=obs["private"]
    day=obs["day"]; remaining_days=30-day; tiles=me["tiles"]; prices=obs.get("market",{}).get("prices",{}); shops=obs.get("town",{}).get("unlocked_shops",[]); market=[]
    my_plants={c:[] for c in BASE_PRICE}; opp_plants={c:0 for c in BASE_PRICE}; harvest_targets=[]; water_targets=[]; weeds=[]; empty_tiles=[]; unlocked_count=0
    for y,row in enumerate(tiles):
        for x,tile in enumerate(row):
            if tile!="LOCKED": unlocked_count+=1
            if tile=="LOCKED": continue
            if tile is None: empty_tiles.append((x,y)); continue
            if not isinstance(tile,dict): continue
            kind=tile.get("kind")
            if kind=="WEED": weeds.append((x,y))
            elif kind=="PLANT":
                crop=tile.get("crop")
                if crop in my_plants:
                    my_plants[crop].append((x,y)); age=day-tile.get("planted_day",day)
                    if tile.get("yield_units",0)>0 and (crop=="STRAWBERRY" or age>=MAX_YIELD_DAY[crop]): harvest_targets.append((x,y))
                    if not tile.get("watered_today",False): water_targets.append((x,y))
    for row in opp.get("tiles",[]):
        for tile in row:
            if isinstance(tile,dict) and tile.get("kind")=="PLANT" and tile.get("crop") in opp_plants: opp_plants[tile["crop"]]+=1
    capacity=unlocked_count; occupied=capacity-len(empty_tiles)
    field=XField(day=day,remaining_days=remaining_days,my_money=me.get("money",0),opp_money=opp.get("money",0),my_land=len(me.get("unlocked_quadrants",[])),opp_land=len(opp.get("unlocked_quadrants",[])),my_hands=len(me.get("hands",[])),opp_hands=len(opp.get("hands",[])),prices=prices,my_supply={c:len(my_plants[c]) for c in BASE_PRICE},opp_supply=opp_plants)
    town_demand={c:sum(1 for shop in shops if shop in SHOP_DEMAND[c]) for c in BASE_PRICE}; scores=counter_crop_weights(field,BASE_PRICE,town_demand)
    for crop in BASE_PRICE:
        if remaining_days<=FIRST_YIELD[crop]+1: scores[crop]=0.0
    visible_work=len(water_targets)+len(harvest_targets)+len(weeds)+max(0,int(capacity*0.65)-occupied)
    relations=relation_layer(field,capacity,occupied,visible_work); growth_field=opponent_growth_field(field,day); field_description=describe_opponent_cycle(growth_field); origin_context=origin_read(relations,field_description); weights=origin_context["weights"]
    flow=compose_flow(field,relations,weights,scores,capacity,occupied); targets=flow["targets"]
    _TRACE.append({"day":day,"field":{"my_money":field.my_money,"opp_money":field.opp_money,"my_land":field.my_land,"opp_land":field.opp_land,"my_hands":field.my_hands,"opp_hands":field.opp_hands,"prices":dict(field.prices),"my_supply":dict(field.my_supply),"opp_supply":dict(field.opp_supply)},"relations":dict(relations),"opponent_growth_field":{"expansion":dict(growth_field["expansion"]),"production":dict(growth_field["production"]),"capital":dict(growth_field["capital"]),"momentum":growth_field["momentum"],"raw_velocity":dict(growth_field["raw_velocity"])},"field_description":{"phase":field_description["phase"],"text":field_description["text"],"signals":dict(field_description["signals"]),"uncertain":field_description["uncertain"]},"origin_read":{"attention":dict(origin_context["attention"])},"weights":dict(weights),"flow":{"targets":dict(targets),"reserve":flow["reserve"],"labor_intensity":flow["labor_intensity"],"land_intensity":flow["land_intensity"],"selling_intensity":flow["selling_intensity"],"desired_occupancy":flow["desired_occupancy"]}})
    _TELEMETRY["turns"]+=1
    for k,v in relations.items(): _TELEMETRY["relation_sum"][k]+=v
    for k,v in weights.items(): _TELEMETRY["weight_sum"][k]+=v
    for crop in BASE_PRICE: _TELEMETRY["allocation_sum"][crop]+=targets[crop]
    projected_cash=me.get("money",0); reserve=flow["reserve"]
    for item in ("WHEAT","STRAWBERRY","MELON","MILK","WOOL","EGG","FERTILIZER"):
        qty=private.get("shed",{}).get(item,0)
        if qty>0 and len(market)<10 and (flow["selling_intensity"]>=0.22 or remaining_days<=5): market.append(["SELL",item,qty])
    occupancy=occupied/capacity if capacity else 1.0; quadrants=len(me.get("unlocked_quadrants",[])); land_cost={1:1000,2:2000,3:4000}.get(quadrants)
    if land_cost and remaining_days>=7 and occupancy>=flow["desired_occupancy"] and flow["land_intensity"]>=0.22 and projected_cash-land_cost>=reserve and len(market)<10: market.append(["BUY_LAND"]); projected_cash-=land_cost
    seed_plan=[]
    for crop in BASE_PRICE:
        have=private.get("seeds",{}).get(crop,0); live=len(my_plants[crop]); need=max(0,targets[crop]-live-have)
        if need<=0 or scores[crop]<=0: continue
        affordable=max(0,int((projected_cash-reserve)//SEED_COST[crop])); buy=min(need,affordable,8)
        if buy>0: seed_plan.append((targets[crop]-live,scores[crop],crop,buy))
    for _,_,crop,buy in sorted(seed_plan,reverse=True):
        if len(market)>=10: break
        cost=buy*SEED_COST[crop]
        if projected_cash-cost>=reserve: market.append(["BUY_SEED",crop,buy]); projected_cash-=cost
    work=len(water_targets)+len(harvest_targets)+len(weeds)+max(0,sum(targets.values())-sum(len(v) for v in my_plants.values())); current=1+len(me.get("hands",[])); hires=me.get("hires_today",0); desired_load=max(3.0,9.0-5.0*flow["labor_intensity"])
    while work>current*desired_load and len(market)<10:
        cost=fib_hire_cost(hires)
        if projected_cash-cost<reserve: break
        market.append(["HIRE"]); projected_cash-=cost; hires+=1; current+=1
    reserved=set()
    def nearest(points,x,y):
        available=[p for p in points if p not in reserved]
        return min(available,key=lambda p:abs(p[0]-x)+abs(p[1]-y)) if available else None
    def move(target,x,y):
        tx,ty=target
        if x<tx:return ["EAST"]
        if x>tx:return ["WEST"]
        if y<ty:return ["SOUTH"]
        if y>ty:return ["NORTH"]
        return ["PASS"]
    deficits={c:targets[c]-len(my_plants[c])-private.get("seeds",{}).get(c,0) for c in BASE_PRICE}; priority=sorted(BASE_PRICE,key=lambda c:(deficits[c]>0,deficits[c],scores[c]),reverse=True)
    def choose_crop(seeds):
        for crop in priority:
            if scores[crop]>0 and len(my_plants[crop])<targets[crop] and seeds.get(crop,0)>0:return crop
        return None
    def unit_action(x,y,seeds):
        cur=tiles[y][x]
        if isinstance(cur,dict):
            if cur.get("kind")=="WEED": reserved.add((x,y)); return ["DIG"]
            if cur.get("kind")=="PLANT":
                crop=cur.get("crop"); age=day-cur.get("planted_day",day)
                if cur.get("yield_units",0)>0 and (crop=="STRAWBERRY" or (crop in MAX_YIELD_DAY and age>=MAX_YIELD_DAY[crop])): reserved.add((x,y)); return ["HARVEST"]
                if not cur.get("watered_today",False): reserved.add((x,y)); return ["WATER"]
        if cur is None:
            crop=choose_crop(seeds)
            if crop: seeds[crop]-=1; reserved.add((x,y)); return ["PLANT",crop]
        for points in (harvest_targets,water_targets,weeds):
            target=nearest(points,x,y)
            if target is not None: reserved.add(target); return move(target,x,y)
        if any(len(my_plants[c])<targets[c] for c in targets):
            target=nearest(empty_tiles,x,y)
            if target is not None: reserved.add(target); return move(target,x,y)
        return ["PASS"]
    seeds={c:private.get("seeds",{}).get(c,0) for c in BASE_PRICE}; units=[("farmer",me["farmer"])]+[(i,p) for i,p in enumerate(me.get("hands",[]))]; actions={}
    def task_distance(pos):
        x,y=pos; points=harvest_targets+water_targets+weeds+empty_tiles
        return min((abs(px-x)+abs(py-y) for px,py in points),default=999)
    for key,(x,y) in sorted(units,key=lambda u:task_distance(u[1])): actions[key]=unit_action(x,y,seeds)
    return {"farmer":actions["farmer"],"hands":[actions[i] for i in range(len(me.get("hands",[])))],"market":market}
