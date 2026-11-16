from pathlib import Path
import shutil,hashlib,json
root=Path(r'C:\Capstone1').resolve()
moves=[('Capstone1/Mujoco/files','legacy/mujoco_initial'),('test','models/legacy_cad'),('furuta_rev5_lite_mujoco','models/rev5/source'),('pi','deployment/pi'),('furuta_platform/config.json','configs/rev5_baseline.json'),('furuta_platform/test_contract.py','tests/test_contract.py'),('docs/static_audit.json','docs/reports/static_audit.json'),('docs/validation.txt','docs/reports/validation_initial.txt'),('docs/IO_SPEC.md','docs/interfaces/IO_SPEC.md'),('README-FURUTA.md','README.md'),('__MACOSX','legacy/macos_metadata')]
def checked(p):
    q=(root/p).resolve()
    if not q.is_relative_to(root) or q==root: raise ValueError(q)
    return q
records=[]
for src,dst in moves:
    a,b=checked(src),checked(dst)
    if not a.exists() or b.exists(): raise ValueError(f'preflight: {a} -> {b}')
    files=list(a.rglob('*')) if a.is_dir() else [a]
    records.append({'from':src,'to':dst,'files':{str(p.relative_to(a)) if a.is_dir() else '.':hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}})
for rec in records:
    a,b=checked(rec['from']),checked(rec['to']); b.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(a),str(b))
    for rel,digest in rec['files'].items():
        p=b if rel=='.' else b/rel
        if hashlib.sha256(p.read_bytes()).hexdigest()!=digest: raise RuntimeError(f'hash mismatch: {p}')
for name in ('runs','docs/hardware','docs/experiments','deployment/teensy'):
    checked(name).mkdir(parents=True,exist_ok=True)
for name in ('Capstone1/Mujoco','Capstone1'):
    p=checked(name)
    if p.exists() and not any(p.iterdir()): p.rmdir()
checked('docs/reports/reorganization_manifest.json').write_text(json.dumps({'note':'Hashes verified immediately after move, before path edits','moves':records},indent=2),encoding='utf-8')
print('Moved and hash-verified',len(records),'entries;',sum(len(r['files']) for r in records),'files preserved')
