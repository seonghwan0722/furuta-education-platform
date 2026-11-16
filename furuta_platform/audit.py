"""Static source audit; does not claim MuJoCo compilation success."""
import json,math,struct
import numpy as np
from .common import SOURCE,ROOT,ARM,PEND
import xml.etree.ElementTree as ET

def main():
    r=ET.parse(SOURCE).getroot(); rows=[]; missing=[]
    for mesh in r.findall('asset/mesh'):
        path=SOURCE.parent/mesh.get('file')
        if not path.is_file(): missing.append(str(path))
    for b in r.iter('body'):
        e=b.find('inertial')
        if e is None: continue
        v=list(map(float,e.get('fullinertia').split())); I=np.array([[v[0],v[3],v[4]],[v[3],v[1],v[5]],[v[4],v[5],v[2]]]); eig=np.linalg.eigvalsh(I)
        rows.append({'body':b.get('name'),'mass_kg':float(e.get('mass')),'com_m':list(map(float,e.get('pos').split())),'fullinertia_kg_m2':v,'positive_definite':bool(min(eig)>0),'triangle':bool(eig[2]<=eig[0]+eig[1]+1e-12)})
    subtree=next(b for b in r.iter('body') if b.find(f"joint[@name='{PEND}']") is not None)
    names={b.get('name') for b in subtree.iter('body')}; p=[x for x in rows if x['body'] in names]
    mass=sum(x['mass_kg'] for x in p); com=sum(x['mass_kg']*np.array(x['com_m']) for x in p)/mass
    anchor=np.array([-.0185,0,.018]); d=com-anchor
    Ip=sum(np.array([[x['fullinertia_kg_m2'][0],x['fullinertia_kg_m2'][3],x['fullinertia_kg_m2'][4]],[x['fullinertia_kg_m2'][3],x['fullinertia_kg_m2'][1],x['fullinertia_kg_m2'][5]],[x['fullinertia_kg_m2'][4],x['fullinertia_kg_m2'][5],x['fullinertia_kg_m2'][2]]])+x['mass_kg']*((np.dot(np.array(x['com_m'])-anchor,np.array(x['com_m'])-anchor))*np.eye(3)-np.outer(np.array(x['com_m'])-anchor,np.array(x['com_m'])-anchor)) for x in p)
    result={'mode':'static XML only; every body transform is identity in this source','mesh_count':len(r.findall('asset/mesh')),'missing':missing,'joints':[x.attrib for x in r.iter('joint')],'actuator_count':len(r.findall('actuator/*')),'pendulum':{'mass_kg':mass,'com_m':com.tolist(),'pivot_m':anchor.tolist(),'radial_com_length_m':float(np.linalg.norm(d[1:])),'up_raw_rad':math.atan2(d[1],d[2]),'inertia_at_pivot_kg_m2':Ip.tolist()},'bodies':rows}
    (ROOT/'docs/reports/static_audit.json').write_text(json.dumps(result,indent=2)); print(json.dumps({k:v for k,v in result.items() if k!='bodies'},indent=2))
if __name__=='__main__':main()
