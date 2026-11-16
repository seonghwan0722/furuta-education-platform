"""Training provenance and immutable save receipts, independent of torch."""
import copy,hashlib,json,subprocess,sys,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .common import ROOT,SOURCE

def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now(): return datetime.now(timezone(timedelta(hours=9))).isoformat()
def write_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp'); tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8'); tmp.replace(path)
def identity(path):
    path=Path(path); digest=sha256(path); sidecar=Path(str(path)+'.metadata.json')
    result={'path':str(path.resolve()),'sha256':digest,'training_id':None,'cumulative_steps':None,'provenance':'not_recorded'}
    if sidecar.exists():
        record=json.loads(sidecar.read_text(encoding='utf-8'))
        if record['artifact_sha256']!=digest: raise ValueError('Policy provenance hash mismatch: '+str(path))
        result.update(training_id=record['training_id'],cumulative_steps=record['cumulative_steps'],provenance='recorded',receipt_id=record['receipt_id'],training_snapshot=record['training_snapshot'])
    return result
def differences(old,new,prefix=''):
    result={}
    for key in sorted(set(old)|set(new)):
        name=prefix+key
        if key in old and key in new and isinstance(old[key],dict) and isinstance(new[key],dict):
            result.update(differences(old[key],new[key],name+'.'))
        elif old.get(key)!=new.get(key) or (key in old)!=(key in new):
            result[name]={'before':old.get(key),'after':new.get(key)}
    return result
class TrainingHistory:
    def __init__(self,out,c,model,requested_steps,note='',parent=None,command=None,checkpoint_every=10000):
        self.out=Path(out); self.id=uuid.uuid4().hex
        sources={}
        for path in sorted((ROOT/'furuta_platform').glob('*.py')):
            rel=path.relative_to(ROOT); sources[str(rel)]=sha256(path)
            target=self.out/'history'/self.id/'code'/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(path.read_bytes())
        try:
            rev=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=3)
            git_commit=rev.stdout.strip() if rev.returncode==0 else None
        except (OSError,subprocess.TimeoutExpired): git_commit=None
        params={k:getattr(model,k,None) for k in ('n_steps','batch_size','n_epochs','gamma','gae_lambda','ent_coef','vf_coef','max_grad_norm','normalize_advantage','target_kl','seed','n_envs')}
        params['learning_rate']=model.learning_rate if isinstance(model.learning_rate,(int,float)) else 'callable; see code snapshot'
        params['clip_range_at_start']=float(model.clip_range(1.))
        params['policy']=str(model.policy)
        self.parent=identity(Path(parent)/'policy.zip') if parent else None
        self.record={'schema':'furuta-training-v1','training_id':self.id,'started_at':now(),'status':'running','note':note,'command':command or list(sys.argv),'config':copy.deepcopy(c),'requested_stage_steps':requested_steps,'actual_stage_steps':0,'parent':self.parent,'optimizer_state':'inherited' if parent else 'new','seed_reset':c['seed'],'hyperparameters':params,'versions':json.loads((self.out/'versions.json').read_text(encoding='utf-8')),'git_commit':git_commit,'code_sha256':sources,'source_xml_sha256':sha256(SOURCE),'mesh_sha256':{str(p.relative_to(SOURCE.parent)):sha256(p) for p in sorted((SOURCE.parent/'meshes').glob('*')) if p.is_file()}}
        self.record['checkpoint_every_requested_steps']=checkpoint_every
        self.record['changes_from_parent']=None
        if parent:
            old=json.loads((Path(parent)/'config.json').read_text(encoding='utf-8-sig'))
            self.record['changes_from_parent']={'config':differences(old,c),'code':None}
            snapshot=self.parent.get('training_snapshot')
            if snapshot and Path(snapshot).exists():
                previous=json.loads(Path(snapshot).read_text(encoding='utf-8'))
                self.record['changes_from_parent']['code']=differences(previous['code_sha256'],sources)
        write_json(self.out/'history'/self.id/'training_start.json',self.record)
        write_json(self.out/'training.json',self.record)
    def save_receipt(self,path,model,kind):
        steps=int(model.num_timesteps)
        previous=0 if self.parent is None else self.parent['cumulative_steps']
        receipt={'schema':'furuta-policy-receipt-v1','receipt_id':uuid.uuid4().hex,'saved_at':now(),'training_id':self.id,'kind':kind,'artifact_path':str(Path(path).resolve()),'artifact_sha256':sha256(path),'stage_steps':steps,'cumulative_steps':None if previous is None else previous+steps,'optimizer_updates_inherited_plus_stage':int(getattr(model,'_n_updates',0)),'training_snapshot':str((self.out/'history'/self.id/'training_start.json').resolve())}
        receipt['training_context']={key:copy.deepcopy(value) for key,value in self.record.items() if key not in ('status','actual_stage_steps','finished_at','error')}
        write_json(self.out/'history'/self.id/'artifacts'/(receipt['receipt_id']+'.json'),receipt)
        write_json(str(path)+'.metadata.json',receipt)
        return receipt
    def finish(self,model,status,error=None):
        self.record.update(status=status,finished_at=now(),actual_stage_steps=int(model.num_timesteps),error=error)
        write_json(self.out/'history'/self.id/'training_end.json',self.record)
        write_json(self.out/'training.json',self.record)
