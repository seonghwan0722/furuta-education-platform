import hashlib,json,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from furuta_platform.common import ROOT,SOURCE,config,model_xml
class LayoutTests(unittest.TestCase):
    def test_models_resolve_external_assets(self):
        for path in (ROOT/'models').rglob('*.xml'):
            r=ET.parse(path).getroot(); compiler=r.find('compiler')
            meshdir=compiler.get('meshdir','') if compiler is not None else ''
            for mesh in r.findall('asset/mesh'):
                if mesh.get('file'):
                    self.assertTrue((path.parent/meshdir/mesh.get('file')).is_file(),str(path)+': '+mesh.get('file'))
    def test_preserved_assets(self):
        records=json.loads((ROOT/'docs/reports/reorganization_manifest.json').read_text(encoding='utf-8'))['moves']
        checked=0
        for record in records:
            if not record['to'].startswith('models/'):
                continue  # Legacy run archives and import metadata are local only.
            base=ROOT/record['to']
            for rel,digest in record['files'].items():
                p=base if rel=='.' else base/rel
                if p.suffix.lower() in ('.xml','.stl','.zip','.png') or p.name.startswith('events.out.'):
                    self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),digest,str(p)); checked+=1
        self.assertGreater(checked,30)
    def test_active_config_and_model(self):
        self.assertTrue(SOURCE.is_file()); r=ET.fromstring(model_xml(config()))
        for mesh in r.findall('asset/mesh'):
            self.assertTrue(Path(mesh.get('file')).is_absolute()); self.assertTrue(Path(mesh.get('file')).is_file())
if __name__=='__main__':unittest.main()
