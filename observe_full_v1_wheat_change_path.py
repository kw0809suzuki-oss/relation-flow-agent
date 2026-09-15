#!/usr/bin/env python3
"""Observe only WHEAT-delta change points from turn 2 through 120 on fresh seeds.
No terminal/margin labels; observer-only.
"""
import importlib.util, json
from pathlib import Path
from kaggle_environments import make
import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH='opponents/seyamalam_v21.py'
CASES=((3564,0),(3565,1),(3566,0),(3567,1),(3568,0))
END=120

def load_opp(tag):
    spec=importlib.util.spec_from_file_location(f'opp_{tag}',OPPONENT_PATH)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod.agent

def play(seed,seat,self_module,tag):
    self_module.reset_telemetry(); self_trace=[]; opp_trace=[]; opp=load_opp(tag)
    env=make('kaggriculture',configuration={'seed':seed},debug=False)
    def sw(obs):
        t=len(self_trace); a=self_module.agent(obs); m=obs.get('market',{})
        self_trace.append({'turn':t,'wheat_inventory':m.get('inventory',{}).get('WHEAT'),'wheat_price':m.get('prices',{}).get('WHEAT'),'action':a}); return a
    def ow(obs):
        t=len(opp_trace); a=opp(obs); opp_trace.append({'turn':t,'action':a}); return a
    players=[ow,ow]; players[seat]=sw; players[1-seat]=ow; env.run(players)
    return self_trace,opp_trace

def wheat_market(action):
    out=[]
    if not isinstance(action,dict): return out
    market=action.get('market',[]) or []
    for x in market:
        if isinstance(x,(list,tuple)) and 'WHEAT' in x:
            out.append(list(x))
    return out

def main():
    cases=[]
    for seed,seat in CASES:
        bs,bo=play(seed,seat,baseline_agent,f'b{seed}')
        cs,co=play(seed,seat,candidate_agent,f'c{seed}')
        n=min(len(bs),len(cs),END+1)
        deltas=[]
        for t in range(n):
            bi=bs[t]['wheat_inventory']; ci=cs[t]['wheat_inventory']
            deltas.append(None if bi is None or ci is None else ci-bi)
        points=[]
        prev=deltas[2] if len(deltas)>2 else None
        # include entry at t2
        if len(deltas)>2:
            points.append({'turn':2,'delta':deltas[2],'delta_step':None,'baseline_price':bs[2]['wheat_price'],'candidate_price':cs[2]['wheat_price']})
        for t in range(3,n):
            d=deltas[t]
            if d is None or prev is None:
                prev=d; continue
            if d!=prev:
                a_t=t-1
                points.append({
                    'turn':t,
                    'delta':d,
                    'delta_step':d-prev,
                    'action_turn':a_t,
                    'self_action_equal': bs[a_t]['action']==cs[a_t]['action'],
                    'opp_action_equal': (a_t<len(bo) and a_t<len(co) and bo[a_t]['action']==co[a_t]['action']),
                    'baseline_self_wheat_market':wheat_market(bs[a_t]['action']),
                    'candidate_self_wheat_market':wheat_market(cs[a_t]['action']),
                    'baseline_price':bs[t]['wheat_price'],
                    'candidate_price':cs[t]['wheat_price'],
                })
            prev=d
        cases.append({'seed':seed,'seat':seat,'points':points,'turn120_delta':deltas[120] if len(deltas)>120 else None})
    result={'schema':'kaggriculture.full-v1-wheat-change-path.v1','observer_only':True,'agent_mutated':False,'terminal_read':False,'margin_read':False,'cases':cases}
    Path('full_v1_wheat_change_path.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('WHEAT_CHANGE_PATH '+json.dumps(cases,separators=(',',':')))

if __name__=='__main__': main()
