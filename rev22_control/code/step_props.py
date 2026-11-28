import sys, json
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_Label
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.TopLoc import TopLoc_Location
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
doc=TDocStd_Document(TCollection_ExtendedString("doc"))
r=STEPCAFControl_Reader(); r.SetNameMode(True)
r.ReadFile(sys.argv[1]); r.Transfer(doc)
st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
def name(l):
    a=TDataStd_Name()
    if l.FindAttribute(TDataStd_Name.GetID_s(),a): return a.Get().ToExtString()
    return "?"
out=[]
def walk(l,loc,path):
    if st.IsAssembly_s(l):
        cs=TDF_LabelSequence(); st.GetComponents_s(l,cs)
        for i in range(1,cs.Length()+1):
            c=cs.Value(i); ref=TDF_Label(); st.GetReferredShape_s(c,ref)
            walk(ref, loc.Multiplied(st.GetLocation_s(c)), path+[name(c)])
    else:
        s=st.GetShape_s(l).Moved(loc)
        ex=TopExp_Explorer(s,TopAbs_SOLID); k=0
        while ex.More():
            sol=ex.Current(); g=GProp_GProps(); BRepGProp.VolumeProperties_s(sol,g)
            c=g.CentreOfMass(); M=g.MatrixOfInertia()
            I=[[M.Value(i,j) for j in (1,2,3)] for i in (1,2,3)]
            b=Bnd_Box(); BRepBndLib.Add_s(sol,b); p0=b.CornerMin();p1=b.CornerMax();bb=[p0.X(),p0.Y(),p0.Z(),p1.X(),p1.Y(),p1.Z()]
            out.append(dict(path="/".join(path+[name(l)]),k=k,V=g.Mass(),c=[c.X(),c.Y(),c.Z()],I=I,bb=list(bb)))
            k+=1; ex.Next()
fs=TDF_LabelSequence(); st.GetFreeShapes(fs)
for i in range(1,fs.Length()+1): walk(fs.Value(i),TopLoc_Location(),[])
json.dump(out,open(sys.argv[2],'w'),indent=0)
print(len(out))
