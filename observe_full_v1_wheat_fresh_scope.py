#!/usr/bin/env python3
"""Observe WHEAT divergence on fresh seeds without terminal/margin labels."""
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
        self_trace.append({'turn':t,'wheat_inventory':m.get('inventory',{}).get('WHEAT'),'action':a}); return a
    def ow(obs):
        t=len(opp_trace); a=opp(obs); opp_trace.append({'turn':t,'action':a}); return a
    players=[ow,ow]; players[seat]=sw; players[1-seat]=ow; env.run(players)
    return self_trace,opp_trace

def main():
    out=[]
    for seed,seat in CASES:
        bs,bo=play(seed,seat,baseline_agent,f'b{seed}'); cs,co=play(seed,seat,candidate_agent,f'c{seed}')
        n=min(len(bs),len(cs),END+1); series=[]
        for t in range(n):
            bi=bs[t]['wheat_inventory']; ci=cs[t]['wheat_inventory']; d=None if bi is None or ci is None else ci-bi
            series.append(d)
        zeros=[t for t,d in enumerate(series) if t>=2 and d==0]
        sign_changes=[]; last=None
        growth=0; contraction=0; opp_equal_growth=0; self_diff_growth=0
        for t,d in enumerate(series):
            if d is None: continue
            s=0 if d==0 else (1 if d>0 else -1)
            if last is None: last=s
            elif s!=last: sign_changes.append({'turn':t,'from':last,'to':s,'delta':d}); last=s
        for t in range(3,n):
            p,c=series[t-1],series[t]
            if p is None or c is None or p==c: continue
            if c<p:
                growth+=1
                if t-1 < len(bo) and t-1 < len(co) and bo[t-1]['action']==co[t-1]['action']: opp_equal_growth+=1
                if bs[t-1]['action']!=cs[t-1]['action']: self_diff_growth+=1
            else: contraction+=1
        out.append({'seed':seed,'seat':seat,'turn2_delta':series[2] if len(series)>2 else None,'turn120_delta':series[120] if len(series)>120 else None,'first_zero_after_2':zeros[0] if zeros else None,'zero_count_after_2':len(zeros),'sign_changes':sign_changes,'growth_count':growth,'contraction_count':contraction,'growth_opp_equal_count':opp_equal_growth,'growth_self_diff_count':self_diff_growth})
    result={'schema':'kaggriculture.full-v1-wheat-fresh-scope.v1','observer_only':True,'agent_mutated':False,'terminal_read':False,'margin_read':False,'cases':out}
    Path('full_v1_wheat_fresh_scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('WHEAT_FRESH_SCOPE '+json.dumps(out,separators=(',',':')))
if __name__=='__main__': main()
