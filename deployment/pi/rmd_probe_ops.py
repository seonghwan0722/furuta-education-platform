"""Probe which read-only RMD commands get replies (no current command)."""
import time, can
with can.Bus(interface='socketcan', channel='can0', can_filters=[{'can_id':0x241,'can_mask':0x7ff,'extended':False}]) as bus:
    for op in (0x92,0x9a,0x9c,0x9a,0x92):
        bus.send(can.Message(arbitration_id=0x141,is_extended_id=False,data=bytes([op])+b'\0'*7),timeout=.02)
        end=time.monotonic()+.2; got=[]
        while (r:=end-time.monotonic())>0:
            m=bus.recv(r)
            if m and len(m.data)==8: got.append(bytes(m.data).hex())
        print(hex(op),'->',got,flush=True)
