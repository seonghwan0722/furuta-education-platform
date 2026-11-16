"""Short integration experiment; explicitly not a reward/convergence benchmark."""
import contextlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from furuta_platform.cli import main
from furuta_platform.common import config
from furuta_platform.env import FurutaEnv
from stable_baselines3.common.env_checker import check_env

def invoke(args,log):
    before=sys.argv
    try:
        sys.argv=['furuta_platform.cli']+args
        with log.open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f): main()
    finally: sys.argv=before

def run():
    root=ROOT/'runs/reward_v1_smoke'; root.mkdir(exist_ok=False)
    results=[]
    for seed in (42,43):
        parent=None
        for stage in ('baseline','balance','mixed','swingup'):
            path=ROOT/('configs/rev5_baseline.json' if stage=='baseline' else f'configs/rev5_shaped_{stage}.json')
            env=FurutaEnv(config(path)); check_env(env); env.close()
            dest=root/f'{stage}_seed{seed}'
            args=['train','--config',str(path),'--run',str(dest),'--steps','512','--seed',str(seed)]
            if parent is not None and stage!='baseline': args+=['--initialize-from',str(parent)]
            invoke(args,root/f'{stage}_{seed}_train.log')
            for start in ('balance','swingup'):
                invoke(['evaluate','--run',str(dest),'--episodes','3','--seed','1000','--eval-start',start],root/f'{stage}_{seed}_{start}_eval.log')
                name='evaluation.json' if start=='swingup' else 'evaluation_balance.json'
                data=json.loads((dest/name).read_text(encoding='utf-8'))
                rows=data['episodes']
                results.append({'training_seed':seed,'stage':stage,'evaluation_start':start,'training_steps_this_stage':512,'success_rate':data['success_rate'],'mean_hold_s':sum(x['longest_hold_s'] for x in rows)/len(rows),'mean_rmse_rad':sum(x['angle_rmse_rad'] for x in rows)/len(rows),'fault_rate':sum(x['fault'] for x in rows)/len(rows),'mean_duration_s':sum(x['duration_s'] for x in rows)/len(rows)})
            if stage!='baseline': parent=dest
            print('completed',stage,seed,flush=True)
        invoke(['export','--run',str(parent)],root/f'export_{seed}.log')
    report={'purpose':'Integration smoke only; 512 steps/stage, no performance conclusion. Baseline total 512 vs staged total 1536 are not equal-budget comparisons. Evaluation seeds 1000,1001,1002 fixed for all.','results':results}
    (ROOT/'docs/reports/reward_v1_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':run()
