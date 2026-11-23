"""Protocol V3.91 sec 2.31: after a 0xB3 trip the motor resumes once communication is stable and continuous.
Send read-only 0x92 every 5 ms for 1.5 s and report which reply opcodes come back over time. No current command."""
import time, can, collections
with can.Bus(interface='socketcan', channel='can0', can_filters=[{'can_id':0x241,'can_mask':0x7ff,'extended':False}]) as bus:
    t0=time.monotonic(); seen=[]
    while time.monotonic()-t0<1.5:
        bus.send(can.Message(arbitration_id=0x141,is_extended_id=False,data=bytes([0x92])+b'\0'*7),timeout=.02)
        end=time.monotonic()+.005
        while (r:=end-time.monotonic())>0:
            m=bus.recv(r)
            if m and len(m.data)==8: seen.append((round(time.monotonic()-t0,3),m.data[0]))
    c=collections.Counter(op for _,op in seen); print('reply opcodes:',{hex(k):v for k,v in c.items()})
    f=[t for t,op in seen if op==0x92]; print('first 0x92 reply at', f[0] if f else None, 's')
    # then one isolated status read
    bus.send(can.Message(arbitration_id=0x141,is_extended_id=False,data=bytes([0x9a])+b'\0'*7),timeout=.02)
    end=time.monotonic()+.05; rep=None
    while (r:=end-time.monotonic())>0 and rep is None:
        m=bus.recv(r)
        if m and len(m.data)==8: rep=bytes(m.data)
    print('0x9A right after:', rep.hex() if rep else None)
