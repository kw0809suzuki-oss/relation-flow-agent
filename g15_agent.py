"""G15: action-history instrument for dynamic-style observation.

Carries the paired G14 switch forward and records Field, intervention, delayed
response, Continue/Cut, residual effect, and next action at each probe episode.
The trace is an observation instrument, not a proof of causal attribution.
"""

import os
import strong_origin_body as g8
import role_reentry_bridge as role_bridge
import outer_meaning_v0

_stats = {}
_probe_enabled = True


def set_probe_enabled(enabled):
    global _probe_enabled
    _probe_enabled = bool(enabled)


def reset_telemetry():
    global _stats
    g8.reset_telemetry()
    _stats = {
        "turns": 0, "opportunities": 0, "probes": 0, "continued": 0,
        "cuts": 0, "reentries": 0, "resonance_events": 0,
        "resonance_sum": 0.0, "resonance_max": 0.0,
        "last_r": None, "last_e": None, "last_w": None,
        "last_money": None, "last_cows": None,
        "history": [], "credit": 0.0, "probe_age": 0, "cooldown": 0,
        "probe_money": None, "probe_cows": None,
        "events": [], "snapshots": [], "pending_event": None,
        "growth_day": None, "growth_prev_final": None, "growth_current_final": None,
        "growth_velocity": {"money": 0.0, "land": 0.0, "hands": 0.0, "supply": 0.0},
        "self_growth_day": None, "self_growth_current_final": None,
        "self_growth_velocity": {"money": 0.0, "land": 0.0, "hands": 0.0, "supply": 0.0},
        "growth_weight_sum": 0.0, "growth_weight_max": 0.0,
        "last_snapshot": None, "flip_events": [], "last_action_pair": None, "boundary_events": [], "semantic_reversal_events": [],
        "role_reentry_context": {}, "role_reentry_hits": 0, "role_reentry_maximal": 0,
        "origin_gate_scaled_turns": 0, "origin_gate_scale_sum": 0.0,
        "adaptive_w_sum": 0.0, "adaptive_w_min": 1.0, "adaptive_w_turns": 0,
        "opponent_phase_counts": {}, "opponent_phase_transitions": [], "last_opponent_phase": None,
        "bundle_flow_v0_turns": 0, "bundle_flow_v0_suppressed_expansions": 0,
        "bundle_flow_v0_supported_turns": 0,
    }


def get_trace():
    return {
        "events": [dict(e) for e in _stats.get("events", [])],
        "snapshots": [dict(x) for x in _stats.get("snapshots", [])],
        "flip_events": [dict(x) for x in _stats.get("flip_events", [])],
        "boundary_events": [dict(x) for x in _stats.get("boundary_events", [])],
        "semantic_reversal_events": [dict(x) for x in _stats.get("semantic_reversal_events", [])],
        "opponent_phase_transitions": [dict(x) for x in _stats.get("opponent_phase_transitions", [])],
    }


def get_telemetry():
    base = dict(g8.get_telemetry())
    turns = max(1, _stats.get("turns", 0))
    base.update({
        "x_turns": _stats.get("turns", 0),
        "x_opportunities": _stats.get("opportunities", 0),
        "x_probes": _stats.get("probes", 0),
        "x_continued": _stats.get("continued", 0),
        "x_cuts": _stats.get("cuts", 0),
        "x_reentries": _stats.get("reentries", 0),
        "x_cooldown": _stats.get("cooldown", 0),
        "x_resonance": _stats.get("resonance_events", 0),
        "x_resonance_mean": round(_stats.get("resonance_sum", 0.0) / turns, 4),
        "x_resonance_max": round(_stats.get("resonance_max", 0.0), 4),
        "x_credit": round(_stats.get("credit", 0.0), 4),
        "role_reentry_hits": _stats.get("role_reentry_hits", 0),
        "role_reentry_maximal": _stats.get("role_reentry_maximal", 0),
        "origin_gate_scaled_turns": _stats.get("origin_gate_scaled_turns", 0),
        "origin_gate_scale_mean": round(_stats.get("origin_gate_scale_sum", 0.0) / max(1, turns), 6),
        "growth_weight_mean": round(_stats.get("growth_weight_sum", 0.0) / turns, 4),
        "growth_weight_max": round(_stats.get("growth_weight_max", 0.0), 4),
        "adaptive_w_mean": round(_stats.get("adaptive_w_sum", 0.0) / turns, 4),
        "adaptive_w_min": round(_stats.get("adaptive_w_min", 1.0), 4),
        "adaptive_w_turns": _stats.get("adaptive_w_turns", 0),
        "opponent_phase_counts": dict(_stats.get("opponent_phase_counts", {})),
        "opponent_phase_transitions": len(_stats.get("opponent_phase_transitions", [])),
        "bundle_flow_v0_turns": _stats.get("bundle_flow_v0_turns", 0),
        "bundle_flow_v0_suppressed_expansions": _stats.get("bundle_flow_v0_suppressed_expansions", 0),
        "bundle_flow_v0_supported_turns": _stats.get("bundle_flow_v0_supported_turns", 0),
    })
    return base


def _clip01(x): return max(0.0, min(1.0, x))


def _field(obs):
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    shed = private.get("shed", {})
    inventories = private.get("inventories", [])
    cows = shed.get("COW", 0) + sum(inv.get("COW", 0) for inv in inventories)
    farm_cows = fed_need = 0
    for row in me["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                cows += 1; farm_cows += 1
                if not tile.get("fed_today", False): fed_need += 1
    wheat = shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in inventories)
    return (me.get("money", 0), 1 + len(me.get("hands", [])), cows, farm_cows, wheat, fed_need, max(0, 30 - obs["day"]))


def _opponent_field(obs):
    other = obs["farms"][1 - obs["player"]]
    animals = 0; active_tiles = 0
    for row in other.get("tiles", []):
        for tile in row:
            if tile == "LOCKED" or tile is None: continue
            active_tiles += 1
            if isinstance(tile, dict) and tile.get("animal"): animals += 1
    return {"money": other.get("money", 0), "units": 1 + len(other.get("hands", [])), "hands": len(other.get("hands", [])), "land": len(other.get("unlocked_quadrants", [])), "active_tiles": active_tiles, "animals": animals, "supply": active_tiles + animals}


def _self_growth_field(obs):
    me = obs["farms"][obs["player"]]
    animals = 0; active_tiles = 0
    for row in me.get("tiles", []):
        for tile in row:
            if tile == "LOCKED" or tile is None: continue
            active_tiles += 1
            if isinstance(tile, dict) and tile.get("animal"): animals += 1
    snap = {"money": float(me.get("money", 0)), "land": float(len(me.get("unlocked_quadrants", []))), "hands": float(len(me.get("hands", []))), "supply": float(active_tiles + animals)}
    day = obs["day"]
    if _stats["self_growth_day"] is None:
        _stats["self_growth_day"] = day; _stats["self_growth_current_final"] = dict(snap)
    elif day != _stats["self_growth_day"]:
        prev = _stats["self_growth_current_final"] or snap
        _stats["self_growth_velocity"] = {key: snap[key] - prev.get(key, snap[key]) for key in snap}
        _stats["self_growth_day"] = day; _stats["self_growth_current_final"] = dict(snap)
    else:
        _stats["self_growth_current_final"] = dict(snap)
    return {"state": snap, "raw_velocity": dict(_stats["self_growth_velocity"])}


def _opponent_growth_field(obs, opponent):
    day = obs["day"]
    snap = {"money": float(opponent["money"]), "land": float(opponent["land"]), "hands": float(opponent["hands"]), "supply": float(opponent["supply"])}
    if _stats["growth_day"] is None:
        _stats["growth_day"] = day; _stats["growth_current_final"] = dict(snap)
    elif day != _stats["growth_day"]:
        prev = _stats["growth_current_final"] or snap
        _stats["growth_prev_final"] = dict(prev)
        _stats["growth_velocity"] = {k: snap[k] - prev.get(k, snap[k]) for k in snap}
        _stats["growth_day"] = day; _stats["growth_current_final"] = dict(snap)
    else:
        _stats["growth_current_final"] = dict(snap)
    v = _stats["growth_velocity"]
    expansion_level = _clip01(0.60 * _clip01(max(0.0, snap["land"] - 1.0) / 3.0) + 0.40 * _clip01(snap["hands"] / 6.0))
    production_level = _clip01(snap["supply"] / 60.0)
    capital_level = _clip01(snap["money"] / 90000.0)
    expansion_velocity = _clip01(0.60 * max(0.0, v["land"]) + 0.40 * max(0.0, v["hands"]) / 2.0)
    production_velocity = _clip01(max(0.0, v["supply"]) / 12.0)
    capital_velocity = _clip01(max(0.0, v["money"]) / 20000.0)
    momentum = _clip01((expansion_velocity + production_velocity + capital_velocity) / 3.0)
    return {"Expansion": {"level": expansion_level, "velocity": expansion_velocity}, "Production": {"level": production_level, "velocity": production_velocity}, "Capital": {"level": capital_level, "velocity": capital_velocity}, "Momentum": momentum, "raw_velocity": dict(v)}


def _opponent_cycle_phase(growth):
    v = growth.get("raw_velocity", {})
    money_v = float(v.get("money", 0.0) or 0.0); land_v = float(v.get("land", 0.0) or 0.0); hands_v = float(v.get("hands", 0.0) or 0.0); supply_v = float(v.get("supply", 0.0) or 0.0)
    expansion_move = land_v > 0 or hands_v > 0; production_move = supply_v > 0
    capital_collect = money_v > 1000 and not expansion_move and supply_v <= 0
    capital_spend = money_v < -1000 and (expansion_move or production_move)
    last = _stats.get("last_opponent_phase")
    if capital_spend and last == "collection": phase = "reinvestment"
    elif expansion_move: phase = "expansion"
    elif production_move: phase = "production"
    elif capital_collect: phase = "collection"
    elif capital_spend: phase = "reinvestment"
    else: phase = "unclear"
    description = {"expansion":"opponent is expanding capacity","production":"opponent production is increasing","collection":"opponent is accumulating money while expansion is quiet","reinvestment":"opponent is spending accumulated money back into growth","unclear":"opponent cycle position is not yet clear"}[phase]
    counts = _stats["opponent_phase_counts"]; counts[phase] = counts.get(phase, 0) + 1
    if last is not None and last != phase:
        _stats["opponent_phase_transitions"].append({"turn": _stats.get("turns", 0), "from": last, "to": phase, "raw_velocity": dict(v)})
    _stats["last_opponent_phase"] = phase
    return {"phase": phase, "description": description, "raw_velocity": dict(v)}


def _signals(money, units, cows, farm_cows, wheat, fed_need, remaining):
    cash_boundary = 1.0 - min(1.0, abs(money - 1100.0) / 1100.0)
    feed_ratio = 0.0 if farm_cows == 0 else fed_need / max(1.0, farm_cows)
    feed_boundary = 1.0 - min(1.0, abs(feed_ratio - 0.50) / 0.50)
    labor_need = max(2.0, cows * 0.75 + 1.0)
    labor_boundary = 1.0 - min(1.0, abs(units - labor_need) / labor_need)
    r = _clip01(max(cash_boundary, feed_boundary, labor_boundary))
    readiness = min(_clip01(money / 1100.0), _clip01(units / 2.0), _clip01(remaining / 10.0))
    if cows == 0: e = 0.30 * readiness
    else:
        feed_leg = _clip01(wheat / max(1.0, fed_need + 1.0)); labor_leg = _clip01(units / max(2.0, cows * 0.75 + 1.0)); cash_leg = _clip01(money / 1800.0)
        e = _clip01(cows / 4.0) * min(feed_leg, labor_leg, cash_leg, _clip01(remaining / 10.0))
    feed_p = _clip01(feed_ratio + (0.25 if cows and wheat <= fed_need else 0.0)); cow_p = _clip01((money / 1800.0) * (remaining / 20.0)); labor_p = _clip01((cows + 1.0) / max(2.0, units) * (money / 1800.0))
    vals = sorted((feed_p, cow_p, labor_p), reverse=True); w = _clip01(1.0 - abs(vals[0] - vals[1]))
    return r, e, w, feed_ratio


def _percentile(values, q):
    if not values: return 1.0
    xs = sorted(values); return xs[min(len(xs) - 1, int((len(xs) - 1) * q))]


def _market_semantic(action):
    orders = (action or {}).get("market", []); kinds = {o[0] for o in orders if o}
    if any(k == "SELL" for k in kinds): return "SELL"
    if any(k in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL") for k in kinds): return "BUY"
    if any(k in ("HIRE", "BUY_LAND") for k in kinds): return "EXPAND"
    return "NONE"


def _unit_semantic(action):
    acts=[]
    if action:
        acts.append(action.get("farmer", ["PASS"])); acts.extend(action.get("hands", []))
    kinds=[a[0] for a in acts if a]
    if any(k in ("NORTH","SOUTH","EAST","WEST") for k in kinds): return "MOVE"
    if any(k in ("DIG","PLANT","WATER","HARVEST","FEED","CARE","DROP","PICKUP","PLACE","BUILD_PASTURE","COLLECT_FERTILIZER") for k in kinds): return "WORK"
    if kinds and all(k == "PASS" for k in kinds): return "PASS"
    return "OTHER" if kinds else "NONE"


def agent(obs):
    global _stats
    if not _stats: reset_telemetry()
    money, units, cows, farm_cows, wheat, fed_need, remaining = _field(obs)
    me_now = obs["farms"][obs["player"]]
    current_unit_pos_sig = (tuple(me_now.get("farmer", ())), tuple(tuple(pos) for pos in me_now.get("hands", [])))
    current_role_state = {"money": money, "units": units, "cows": cows, "wheat": wheat, "feed_need": fed_need, "land": len(me_now.get("unlocked_quadrants", [])), "day": obs["day"]}
    role_context = role_bridge.observe(_stats.get("snapshots", []), current_role_state, current_unit_pos_sig, lambda action: f"{_market_semantic(action)}:{_unit_semantic(action)}")
    _stats["role_reentry_context"] = role_context
    if role_context.get("matched_count", 0) > 0: _stats["role_reentry_hits"] += 1
    _stats["role_reentry_maximal"] += role_context.get("maximal_count", 0)

    opponent = _opponent_field(obs); growth = _opponent_growth_field(obs, opponent); self_growth = _self_growth_field(obs); opponent_cycle = _opponent_cycle_phase(growth)
    r, e, w, feed_ratio = _signals(money, units, cows, farm_cows, wheat, fed_need, remaining)
    field_description = {
        "self": {"money": money, "units": units, "cows": cows, "wheat": wheat, "feed_need": fed_need, "remaining": remaining},
        "opponent": dict(opponent), "self_motion": dict(self_growth), "opponent_cycle": dict(opponent_cycle),
        "observed_relations": {"R": round(r,4), "E": round(e,4), "W": round(w,4)},
        "uncertain": opponent_cycle.get("phase") == "unclear", "action_instruction": None, "strategy_instruction": None,
    }
    closure_day = os.getenv("OUTER_MEANING_CLOSURE_DAY")
    if closure_day is not None:
        meaning = outer_meaning_v0.closure_meaning(obs, int(closure_day))
        if meaning is not None:
            field_description["outer_meaning"] = meaning

    option_day = os.getenv("OUTER_MEANING_OPTION_PRESERVATION_DAY")
    if option_day is not None:
        meaning = outer_meaning_v0.option_preservation_meaning(obs, int(option_day))
        if meaning is not None:
            field_description["outer_meaning"] = meaning

    connected_context = dict(role_context)
    if os.getenv("G15_CONNECT_OPPONENT_FIELD_DESCRIPTION", "1") == "1":
        connected_context["field_description"] = field_description; connected_context["field_description_connected"] = True
    else: connected_context["field_description_connected"] = False
    _stats["role_reentry_context"] = connected_context

    expansion = growth["Expansion"]["level"]; production = growth["Production"]["level"]; capital = growth["Capital"]["level"]; momentum = growth["Momentum"]
    growth_weight = _clip01(0.24*expansion + 0.24*production + 0.32*capital + 0.20*momentum)
    lr, le, lw = _stats["last_r"], _stats["last_e"], _stats["last_w"]
    dr = 0.0 if lr is None else r-lr; de = 0.0 if le is None else e-le; dw = 0.0 if lw is None else w-lw
    remove_r_relation = os.getenv("G15_REMOVE_R_RELATION", "0") == "1"; remove_e_relation = os.getenv("G15_REMOVE_E_RELATION", "0") == "1"; remove_w_relation = os.getenv("G15_REMOVE_W_RELATION", "0") == "1"; adaptive_w = os.getenv("G15_ADAPTIVE_W_AMPLITUDE", "0") == "1"
    relation_motion = _clip01(abs(dr)+abs(de)+abs(dw)); field_instability = max(relation_motion, momentum); w_alpha = max(0.50, 1.0-0.50*field_instability) if adaptive_w else 1.0
    if remove_r_relation:
        level=(e*w)**0.5 if min(e,w)>0 else 0.0; motion=min(1.0,abs(de)+abs(dw))
    elif remove_e_relation:
        level=(r*w)**0.5 if min(r,w)>0 else 0.0; motion=min(1.0,abs(dr)+abs(dw))
    elif remove_w_relation:
        level=(r*e)**0.5 if min(r,e)>0 else 0.0; motion=min(1.0,abs(dr)+abs(de))
    else:
        level=(r*e*(w**w_alpha))**(1.0/(2.0+w_alpha)) if min(r,e)>0 and (w>0 or w_alpha==0.0) else 0.0
        motion=min(1.0,abs(dr)+abs(de)+w_alpha*abs(dw))
    resonance=_clip01(0.70*level+0.30*motion); history=_stats["history"]; gate=max(0.18,_percentile(history[-24:],0.70)) if len(history)>=6 else 0.22
    origin_integration=g8.get_origin_integration(); gate_scale=float(origin_integration.get("gate_scale",1.0) or 1.0); gate_scale=max(0.96,min(1.04,gate_scale)); effective_gate=max(0.16,gate*gate_scale)
    _stats["origin_gate_scale_sum"] += gate_scale
    if abs(gate_scale-1.0)>1e-9: _stats["origin_gate_scaled_turns"] += 1
    disable_resonance_control = os.getenv("G15_DISABLE_RESONANCE_CONTROL", "0") == "1"
    raw_opportunity = (not disable_resonance_control) and resonance>=effective_gate and money>=850 and remaining>=8
    opportunity = _probe_enabled and raw_opportunity and _stats["probe_age"]==0 and _stats["cooldown"]==0
    if raw_opportunity: _stats["opportunities"] += 1; _stats["resonance_events"] += 1

    if _stats["probe_age"] > 0:
        _stats["probe_age"] += 1
        if _stats["probe_age"] >= 5:
            md=money-_stats["probe_money"]; cd=cows-_stats["probe_cows"]; outcome=max(-0.4,min(0.4,md/4000.0)); outcome += 0.30 if cd>0 else (-0.15 if cd<0 else 0.0); outcome += max(-0.15,min(0.15,de)); _stats["credit"] = 0.55*_stats["credit"]+0.45*outcome
            decision="Continue" if outcome>=0 else "Cut"
            if outcome>=0: _stats["continued"] += 1
            else: _stats["cuts"] += 1
            pending=_stats.get("pending_event")
            if pending is not None and pending < len(_stats["events"]):
                _stats["events"][pending].update({"response_turn":_stats["turns"],"response_day":obs["day"],"money_after":money,"cows_after":cows,"r_after":round(r,4),"e_after":round(e,4),"w_after":round(w,4),"opponent_after":dict(opponent),"outcome":round(outcome,4),"decision":decision,"credit_after":round(_stats["credit"],4),"role_reentry_context":dict(connected_context)})
            _stats["pending_event"]=None; _stats["reentries"] += 1; _stats["probe_age"]=0; _stats["probe_money"]=_stats["probe_cows"]=None; _stats["cooldown"]=18
    else:
        _stats["credit"] *= 0.92
        if _stats["cooldown"]>0: _stats["cooldown"] -= 1

    capacity=min(8,max(2,int(units*1.2))); growth_capacity=capacity; severe_stress=remaining<5 or money<300 or (farm_cows>0 and feed_ratio>=1.0 and wheat==0)
    if severe_stress or _stats["credit"] < -0.12:
        target,feed_carry,mode=min(cows,capacity),2,"cut"
    elif _probe_enabled and not disable_resonance_control and _stats["credit"]>=0.08 and resonance>=max(0.16,effective_gate*0.85):
        target,feed_carry,mode=min(growth_capacity,max(cows+1,3)),4,"continue"
    elif opportunity:
        target,feed_carry,mode=min(growth_capacity,max(cows+1,2)),3,"probe"; _stats["probe_age"]=1; _stats["probe_money"],_stats["probe_cows"]=money,cows; _stats["probes"] += 1
        _stats["events"].append({"probe_index":_stats["probes"],"turn":_stats["turns"],"day":obs["day"],"field":{"money":money,"units":units,"cows":cows,"farm_cows":farm_cows,"wheat":wheat,"feed_need":fed_need,"remaining":remaining,"opponent":dict(opponent)},"relation":{"R":round(r,4),"E":round(e,4),"W":round(w,4),"dR":round(dr,4),"dE":round(de,4),"dW":round(dw,4)},"resonance":round(resonance,4),"gate":round(gate,4),"effective_gate":round(effective_gate,4),"origin_integration":dict(origin_integration),"effect":"raise livestock target by one within capacity"})
        _stats["pending_event"] = len(_stats["events"])-1
    else:
        target,feed_carry,mode=min(growth_capacity,max(cows,1 if money>=1100 and remaining>=10 else 0)),2,"hold"

    # Value Bundle Flow Control v0.
    # Keep the native strategy intact; only suppress a new livestock expansion
    # when the next cycle would consume the cash buffer or cannot fit in time.
    # Product stock is observed separately and is never counted as current cash.
    if os.getenv("BUNDLE_FLOW_CONTROL_V0", "0") == "1":
        private_now = obs.get("private", {}) or {}
        prices_now = (obs.get("market", {}) or {}).get("prices", {}) or {}
        stores = [private_now.get("shed", {}) or {}] + list(private_now.get("inventories", []) or [])
        bundle_value = 0.0
        total_wheat = 0.0
        for store in stores:
            if not isinstance(store, dict):
                continue
            total_wheat += float(store.get("WHEAT", 0) or 0)
            for item, qty in store.items():
                price = prices_now.get(item)
                if isinstance(qty, (int, float)) and isinstance(price, (int, float)):
                    bundle_value += float(qty) * float(price)
        wheat_price = max(1.0, float(prices_now.get("WHEAT", 25) or 25))
        expansion_cost = 400.0 if target > cows else 0.0
        next_cows = max(float(cows), float(target))
        feed_gap = max(0.0, next_cows * 2.0 - total_wheat)
        reinvestment_cost = expansion_cost + feed_gap * wheat_price
        cash_after_reinvestment = float(money) - reinvestment_cost
        remaining_fit = remaining >= 8
        cash_fit = cash_after_reinvestment >= 900.0
        _stats["bundle_flow_v0_turns"] += 1

        if target > cows and (not remaining_fit or not cash_fit):
            target = cows
            feed_carry = min(feed_carry, 2)
            _stats["bundle_flow_v0_suppressed_expansions"] += 1
        else:
            # When the native choice already fits the whole cycle, do not
            # replace it.  Keep enough feed in motion to avoid starving the
            # next value-forming leg.
            if cows > 0 and total_wheat >= 3 and remaining >= 4 and money >= 900:
                feed_carry = max(feed_carry, 3)
            _stats["bundle_flow_v0_supported_turns"] += 1

        connected_context["bundle_flow_v0"] = {
            "bundle_value": round(bundle_value, 2),
            "reinvestment_cost": round(reinvestment_cost, 2),
            "cash_after_reinvestment": round(cash_after_reinvestment, 2),
            "remaining_fit": bool(remaining_fit),
            "cash_fit": bool(cash_fit),
            "target_after": int(target),
            "feed_carry_after": int(feed_carry),
            "future_sale_counted_as_cash": False,
        }

    g8.COW_TARGETS=((31,target),); g8.FEED_CARRY=feed_carry; g8.set_reentry_context(connected_context)
    _stats["turns"] += 1; _stats["resonance_sum"] += resonance; _stats["resonance_max"] = max(_stats["resonance_max"],resonance); _stats["growth_weight_sum"] += growth_weight; _stats["growth_weight_max"] = max(_stats["growth_weight_max"],growth_weight); _stats["adaptive_w_sum"] += w_alpha; _stats["adaptive_w_min"] = min(_stats["adaptive_w_min"],w_alpha)
    if adaptive_w and w_alpha < 1.0-1e-9: _stats["adaptive_w_turns"] += 1
    history.append(resonance); _stats["last_r"],_stats["last_e"],_stats["last_w"]=r,e,w; _stats["last_money"],_stats["last_cows"]=money,cows
    action=g8.agent(obs); origin_trace=g8.get_last_trace() if hasattr(g8,"get_last_trace") else {}
    me=obs["farms"][obs["player"]]; private=obs["private"]; shed_sig=tuple(sorted(private.get("shed",{}).items())); inv_sig=tuple(tuple(sorted(inv.items())) for inv in private.get("inventories",[])); tile_sig=tuple(tuple(repr(tile) for tile in row) for row in me.get("tiles",[])); unit_pos_sig=(tuple(me.get("farmer",())),tuple(tuple(pos) for pos in me.get("hands",[])))
    snapshot={"turn":_stats["turns"]-1,"day":obs["day"],"mode":mode,"money":money,"units":units,"cows":cows,"wheat":wheat,"land":len(me.get("unlocked_quadrants",[])),"shed_sig":shed_sig,"inv_sig":inv_sig,"tile_sig":tile_sig,"unit_pos_sig":unit_pos_sig,"feed_need":fed_need,"remaining":remaining,"R":round(r,4),"E":round(e,4),"W":round(w,4),"W_alpha":round(w_alpha,4),"resonance":round(resonance,4),"target":target,"feed_carry":feed_carry,"raw_opportunity":bool(raw_opportunity),"opportunity":bool(opportunity),"gate_margin":round(resonance-effective_gate,6),"gate_conditions":{"resonance_pass":bool(resonance>=effective_gate),"money_pass":bool(money>=850),"remaining_pass":bool(remaining>=8),"resonance_control_enabled":bool(not disable_resonance_control),"probe_enabled":bool(_probe_enabled),"probe_age_zero":bool(_stats["probe_age"]==0),"cooldown_zero":bool(_stats["cooldown"]==0),"probe_age":int(_stats["probe_age"]),"cooldown":int(_stats["cooldown"])},"opponent":dict(opponent),"growth_field":growth,"opponent_cycle":opponent_cycle,"growth_weight":round(growth_weight,4),"gate":round(gate,4),"effective_gate":round(effective_gate,4),"origin_integration":dict(origin_integration),"action":action,"base_action":origin_trace.get("base_action",{}),"origin_internal":origin_trace.get("internal",{}),"origin_reading_current":origin_trace.get("origin_reading",{}),"origin_integration_current":origin_trace.get("origin_integration",{}),"applied_origin_integration":origin_trace.get("applied_origin_integration",{}),"direction_control_mode":origin_trace.get("direction_control_mode"),"direction_control_comparable_entry":origin_trace.get("direction_control_comparable_entry",False),"direction_control_used":origin_trace.get("direction_control_used",False),"direction_state_delta_applied":origin_trace.get("direction_state_delta_applied",False),"applied_candidate_direction":origin_trace.get("applied_candidate_direction",{}),"abstraction_transmission_enabled":origin_trace.get("abstraction_transmission_enabled",False),"applied_flow_abstraction":origin_trace.get("applied_flow_abstraction",{}),"selected_candidate_direction":origin_trace.get("selected_candidate_direction",{}),"alternative_candidate_direction":origin_trace.get("alternative_candidate_direction",{}),"crop_commitment_enabled":origin_trace.get("crop_commitment_enabled",False),"crop_commitment_scale":origin_trace.get("crop_commitment_scale",1.0),"overlay_changed_farmer":origin_trace.get("overlay_changed_farmer",False),"overlay_changed_hands":origin_trace.get("overlay_changed_hands",False),"overlay_changed_market":origin_trace.get("overlay_changed_market",False),"role_reentry_context":dict(role_context)}
    prev=_stats.get("last_snapshot")
    if prev is not None:
        prev_market_sem=_market_semantic(prev.get("action")); cur_market_sem=_market_semantic(action); prev_unit_sem=_unit_semantic(prev.get("action")); cur_unit_sem=_unit_semantic(action)
        if prev_market_sem!=cur_market_sem or prev_unit_sem!=cur_unit_sem:
            _stats["semantic_reversal_events"].append({"turn":snapshot["turn"],"day":snapshot["day"],"market_from":prev_market_sem,"market_to":cur_market_sem,"unit_from":prev_unit_sem,"unit_to":cur_unit_sem,"state_before":{"money":prev.get("money"),"units":prev.get("units"),"cows":prev.get("cows"),"wheat":prev.get("wheat"),"feed_need":prev.get("feed_need"),"land":prev.get("land"),"day":prev.get("day")},"state_after":{"money":snapshot.get("money"),"units":snapshot.get("units"),"cows":snapshot.get("cows"),"wheat":snapshot.get("wheat"),"feed_need":snapshot.get("feed_need"),"land":snapshot.get("land"),"day":snapshot.get("day")},"observer_only":True})
        boundary_axes=("money","tile_sig","inv_sig","day"); boundary_delta={k:prev.get(k)!=snapshot.get(k) for k in boundary_axes}; prev_internal=prev.get("origin_internal",{}); cur_internal=snapshot.get("origin_internal",{}); prev_market=prev_internal.get("market"); cur_market=cur_internal.get("market"); prev_units=(prev_internal.get("farmer_action"),prev_internal.get("hand_actions")); cur_units=(cur_internal.get("farmer_action"),cur_internal.get("hand_actions")); market_dir_changed=prev_market!=cur_market; unit_dir_changed=prev_units!=cur_units
        if any(boundary_delta.values()) and (market_dir_changed or unit_dir_changed):
            _stats["boundary_events"].append({"turn":snapshot["turn"],"day":snapshot["day"],"state_delta":boundary_delta,"market_direction_changed":market_dir_changed,"unit_direction_changed":unit_dir_changed,"action_changed":prev.get("action")!=action,"observer_only":True})
    if prev is not None and prev.get("action") != action:
        state_keys=("money","units","cows","wheat","feed_need","land","shed_sig","inv_sig","tile_sig","day"); state_delta={k:prev.get(k)!=snapshot.get(k) for k in state_keys}; state_changed=any(state_delta.values()); relation_changed=any(prev.get(k)!=snapshot.get(k) for k in ("R","E","W","resonance")); mode_changed=prev.get("mode")!=mode; target_changed=prev.get("target")!=target; feed_changed=prev.get("feed_carry")!=feed_carry; prev_action=prev.get("action"); prev2=_stats["snapshots"][-2] if len(_stats["snapshots"])>=2 else None; roundtrip=bool(prev2 is not None and prev2.get("action")==action and prev_action!=action); suspicious_no_state=not state_changed
        _stats["flip_events"].append({"turn":snapshot["turn"],"day":snapshot["day"],"state_changed":state_changed,"relation_changed":relation_changed,"mode_changed":mode_changed,"target_changed":target_changed,"feed_changed":feed_changed,"base_action_changed":prev.get("base_action")!=snapshot.get("base_action"),"overlay_changed":bool(snapshot.get("overlay_changed_farmer") or snapshot.get("overlay_changed_hands") or snapshot.get("overlay_changed_market")),"origin_strategy_changed":prev.get("origin_internal",{}).get("strategy_name")!=snapshot.get("origin_internal",{}).get("strategy_name"),"origin_targets_changed":prev.get("origin_internal",{}).get("targets")!=snapshot.get("origin_internal",{}).get("targets"),"origin_market_changed":prev.get("origin_internal",{}).get("market")!=snapshot.get("origin_internal",{}).get("market"),"origin_units_changed":prev.get("origin_internal",{}).get("farmer_action")!=snapshot.get("origin_internal",{}).get("farmer_action") or prev.get("origin_internal",{}).get("hand_actions")!=snapshot.get("origin_internal",{}).get("hand_actions"),"flip_type":"both" if (prev.get("origin_internal",{}).get("market")!=snapshot.get("origin_internal",{}).get("market") and (prev.get("origin_internal",{}).get("farmer_action")!=snapshot.get("origin_internal",{}).get("farmer_action") or prev.get("origin_internal",{}).get("hand_actions")!=snapshot.get("origin_internal",{}).get("hand_actions"))) else "market_only" if prev.get("origin_internal",{}).get("market")!=snapshot.get("origin_internal",{}).get("market") else "unit_only" if (prev.get("origin_internal",{}).get("farmer_action")!=snapshot.get("origin_internal",{}).get("farmer_action") or prev.get("origin_internal",{}).get("hand_actions")!=snapshot.get("origin_internal",{}).get("hand_actions")) else "other","state_delta":state_delta,"suspicious_no_state":suspicious_no_state,"roundtrip":roundtrip,"phenomenon_class":"suspicious_no_state" if suspicious_no_state else "roundtrip_candidate" if roundtrip else "normal_tracking","prev_mode":prev.get("mode"),"mode":mode,"prev_target":prev.get("target"),"target":target,"prev_feed":prev.get("feed_carry"),"feed":feed_carry})
    _stats["snapshots"].append(snapshot); _stats["last_snapshot"]=snapshot
    if mode=="probe" and _stats["events"]: _stats["events"][-1]["action"]=action
    return action
