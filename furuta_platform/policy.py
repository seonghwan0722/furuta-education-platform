"""NumPy-only deterministic actor: no pickle or torch required on Pi."""
import hashlib,json
from pathlib import Path
import numpy as np
class Policy:
    def __init__(self,folder):
        p=Path(folder); self.meta=json.loads((p/'manifest.json').read_text(encoding='utf-8-sig'))
        raw=(p/'actor.npz').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=self.meta['sha256']: raise ValueError('policy hash mismatch')
        if self.meta['schema']!='furuta-io-v1': raise ValueError('schema mismatch')
        self.weights=np.load(p/'actor.npz',allow_pickle=False)
    def predict(self,obs):
        x=np.asarray(obs,dtype=np.float32)
        if x.shape!=(6,) or not np.isfinite(x).all() or np.any(np.abs(x)>1.00001): raise ValueError('bad observation')
        for i in range(self.meta['layers']):
            x=self.weights[f'w{i}']@x+self.weights[f'b{i}']
            if i<self.meta['layers']-1: x=np.tanh(x)
        if x.shape!=(1,) or not np.isfinite(x).all(): raise ValueError('bad inference')
        return np.clip(x,-1,1)
