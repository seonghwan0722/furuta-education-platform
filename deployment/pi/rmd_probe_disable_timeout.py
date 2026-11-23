"""Probe RMD status, then immediately write 0xB3 = 0 (communication-interruption protection off). No current command."""
import struct, time, can
with can.Bus(interface='socketcan', channel='can0', can_filters=[{'can_id':0x241,'can_mask':0x7ff,'extended':False}]) as bus:
    def req(op, payload=b'\0'*7):
        bus.send(can.Message(arbitration_id=0x141,is_extended_id=False,data=bytes([op])+payload),timeout=.02); end=time.monotonic()+.1
        while (r:=end-time.monotonic())>0:
            m=bus.recv(r)
            if m and len(m.data)==8 and m.data[0]==op: return bytes(m.data)
        return None
    s=req(0x9a); print('0x9A', s.hex() if s else None, flush=True)
    e=req(0xb3, b'\0'*3+struct.pack('<I',0)); print('0xB3=0 reply', e.hex() if e else None, flush=True)
    if s: v,f=struct.unpack_from('<HH',s,4); print(f'voltage {v/10:.1f} V faults 0x{f:04x}')
