import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from furuta_platform.common import config
from furuta_platform.history import TrainingHistory,identity,differences

def model(steps):
    return SimpleNamespace(num_timesteps=steps,_n_updates=10,learning_rate=.0003,clip_range=lambda _: .2,policy='test actor')
class HistoryTests(unittest.TestCase):
    def setup_run(self,path,c):
        path.mkdir(); (path/'versions.json').write_text('{}'); (path/'config.json').write_text(json.dumps(c))
    def test_same_filename_keeps_receipts_and_checks_hash(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'run'; c=config(); self.setup_run(out,c)
            h=TrainingHistory(out,c,model(0),257,note='test')
            path=out/'policy.zip'; path.write_bytes(b'first')
            first=h.save_receipt(path,model(256),'checkpoint')
            path.write_bytes(b'second'); second=h.save_receipt(path,model(512),'final'); h.finish(model(512),'completed')
            records=list((out/'history'/h.id/'artifacts').glob('*.json'))
            self.assertEqual(len(records),2); self.assertNotEqual(first['artifact_sha256'],second['artifact_sha256'])
            self.assertEqual(identity(path)['receipt_id'],second['receipt_id'])
            self.assertEqual(second['training_context']['config'],c)
            data=json.loads((out/'training.json').read_text()); self.assertEqual(data['actual_stage_steps'],512); self.assertEqual(data['requested_stage_steps'],257)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError): identity(path)
    def test_parent_lineage_and_changes(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=Path(t)/'a',Path(t)/'b'; c=config(); self.setup_run(a,c)
            h=TrainingHistory(a,c,model(0),512); (a/'policy.zip').write_bytes(b'parent'); h.save_receipt(a/'policy.zip',model(512),'final')
            changed=copy.deepcopy(c); changed['seed']=43; self.setup_run(b,changed)
            child=TrainingHistory(b,changed,model(0),256,parent=a); (b/'policy.zip').write_bytes(b'child')
            receipt=child.save_receipt(b/'policy.zip',model(256),'final')
            self.assertEqual(receipt['cumulative_steps'],768)
            self.assertEqual(child.record['changes_from_parent']['config']['seed'],{'before':42,'after':43})
            self.assertEqual(child.record['parent']['training_id'],h.id)
    def test_old_parent_has_unknown_total(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'policy.zip'; p.write_bytes(b'legacy')
            self.assertIsNone(identity(p)['cumulative_steps']); self.assertEqual(identity(p)['provenance'],'not_recorded')
if __name__=='__main__':unittest.main()
