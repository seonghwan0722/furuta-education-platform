import json,unittest,math,tempfile,hashlib
from pathlib import Path
import numpy as np
from furuta_platform.common import config,observe,model_xml
from furuta_platform.policy import Policy
from deployment.pi.replay import Guard
class Actor:
    def predict(self,obs): return np.array([.5])
class Tests(unittest.TestCase):
    def packet(self):return {'schema':'furuta-io-v1','status':'ok','seq':1,'t_pi_s':1.,'state':[0,0,0,0]}
    def test_observation(self):
        c=config(); np.testing.assert_allclose(observe(0,0,0,0,c),[0,1,0,1,0,0]); self.assertEqual(observe(0,0,200,0,c)[4],1)
        with self.assertRaises(ValueError):observe(0,float('nan'),0,0,c)
    def test_faults(self):
        for mutate in [lambda p:p.update(t_pi_s=0),lambda p:p.update(status='bad'),lambda p:p.update(state=[0,0,100,0]),lambda p:p.update(state=[0,float('nan'),0,0]),lambda p:p.update(t_pi_s=2)]:
            g=Guard(config(),.1); p=self.packet(); mutate(p); self.assertEqual(g.command(p,1.05,Actor())['torque_nm'],0); self.assertTrue(g.latched)
        g=Guard(config(),.1); p=self.packet(); self.assertAlmostEqual(g.command(p,1.05,Actor())['torque_nm'],.025); self.assertEqual(g.command(p,1.05,Actor())['torque_nm'],0)
    def test_actor_integrity(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); np.savez(p/'actor.npz',w0=np.zeros((1,6)),b0=np.array([2.]))
            meta={'schema':'furuta-io-v1','layers':1,'sha256':hashlib.sha256((p/'actor.npz').read_bytes()).hexdigest()}; (p/'manifest.json').write_text(json.dumps(meta))
            self.assertEqual(float(Policy(p).predict(np.zeros(6))[0]),1)
            (p/'actor.npz').write_bytes(b'bad')
            with self.assertRaises(ValueError):Policy(p)
    def test_model_adapter(self):
        import xml.etree.ElementTree as ET
        r=ET.fromstring(model_xml(config())); self.assertEqual(r.find('actuator/motor').get('gear'),'1'); self.assertEqual(len(list(r.iter('joint'))),2)
    def test_encoder(self):
        from deployment.pi.encoder import Encoder
        e=Encoder(0,1,0,.1)
        self.assertFalse(e.update(3.13,0)[2])
        angle,v,valid=e.update(-3.13,.01)
        self.assertTrue(valid); self.assertGreater(angle,3.14); self.assertGreater(v,0)
        with self.assertRaises(ValueError): e.update(0,.5)
    def test_transport(self):
        import socket
        from deployment.pi.transport import JsonLineChannel
        class Stream:
            def __init__(self,chunks): self.chunks=list(chunks); self.sent=b''
            def settimeout(self,t): pass
            def recv(self,n): return self.chunks.pop(0) if self.chunks else b''
            def sendall(self,b): self.sent+=b
        s=Stream([b'{"seq":',b'1}\n']); ch=JsonLineChannel(s,.05)
        self.assertEqual(ch.receive(),{'seq':1})
        with self.assertRaises(ConnectionError): ch.receive()
        ch.send({'enable':False}); self.assertEqual(json.loads(s.sent),{'enable':False})
        with self.assertRaises(ValueError):JsonLineChannel(Stream([b'x'*4097]),.05).receive()
if __name__=='__main__':unittest.main()
