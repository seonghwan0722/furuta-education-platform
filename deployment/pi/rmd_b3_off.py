"""Set RMD 0xB3 (communication-interruption protection) back to 0 = off (team decision 2026-11-18).
Keeps communication continuous (0x92 every 5 ms) before and after, per protocol V3.91 sec 2.31. No current command."""
import time, can
with can.Bus(interface='socketcan', channel='can0', can_filters=[{'can_id':0x241,'can_mask':0x7ff,'extended':False}]) as bus:
    def tx(op,payload=b'\0'*7): bus.send(can.Message(arbitration_id=0x141,is_extended_id=False,data=bytes([op])+payload),timeout=.02)
    def pump(sec):
        t0=time.monotonic(); last=None
        while time.monotonic()-t0<sec:
            tx(0x92); end=time.monotonic()+.005
            while (r:=end-time.monotonic())>0:
                m=bus.recv(r)
                if m and len(m.data)==8: last=bytes(m.data)
        return last
    print('pump reply', pump(0.6).hex(), flush=True)
    tx(0xb3, b'\0'*7); end=time.monotonic()+.05; rep=None
    while (r:=end-time.monotonic())>0:
        m=bus.recv(r)
        if m and len(m.data)==8 and m.data[0]==0xb3: rep=bytes(m.data); break
    print('0xB3 write 0 reply', rep.hex() if rep else None, flush=True)
    pump(0.2)
time.sleep(1.0)
with can.Bus(interface='socketcan', channel='can0', can_filters=[{'can_id':0x241,'can_mask':0x7ff,'extended':False}]) as bus:
    for op in (0x9a,0x92):
        bus.send(can.Message(arbitration_id=0x141,is_extended_id=False,data=bytes([op])+b'\0'*7),timeout=.02)
        end=time.monotonic()+.1; rep=None
        while (r:=end-time.monotonic())>0 and rep is None:
            m=bus.recv(r)
            if m and len(m.data)==8: rep=bytes(m.data)
        print(f'after 1 s idle, 0x{op:02x} ->', rep.hex() if rep else None, flush=True)
