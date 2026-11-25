"""Replace the CAD M6x30 bolt (head 13.3 x ~3.3, shank 5.8 x 29) with the measured one (2026-11-02 caliper):
head dia 13.3, head height 5.1 (domed: R3 top edge), length under head 30.0, thread major 5.8.
Head underside stays on the rod end face (CAD y = -140.0); the bolt axis is along -y at x = 76, z = 18 (CAD pose)."""
import pickle, tempfile, os
import cadquery as cq
from OCP.BRepTools import BRepTools
ser = pickle.load(open('/home/claude/mj11/parts.pkl', 'rb'))
head = cq.Workplane('XY').circle(13.3/2).extrude(5.1).faces('>Z').edges().fillet(3.0)        # +z = away from the rod
shank = cq.Workplane('XY').circle(5.8/2).extrude(-30.0)
bolt = head.union(shank).val()
# local z -> CAD -y, local origin -> (76, -140.0, 18)
bolt = bolt.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90).translate(cq.Vector(76.0, -140.0, 18.0))
bb = bolt.BoundingBox(); print('new bolt bbox y %.2f..%.2f x %.2f..%.2f z %.2f..%.2f vol %.1f' % (bb.ymin, bb.ymax, bb.xmin, bb.xmax, bb.zmin, bb.zmax, bolt.Volume()))
fn = tempfile.mktemp(suffix='.brep'); BRepTools.Write_s(bolt.wrapped, fn); s = open(fn, 'rb').read(); os.remove(fn)
out = []
for leaf, path, data, rgb in ser:
    if leaf.startswith('M6x30_button_bolt_weight'):
        data = s; print('replaced', leaf)
    out.append((leaf, path, data, rgb))
pickle.dump(out, open('/home/claude/mj11/parts.pkl', 'wb'))
