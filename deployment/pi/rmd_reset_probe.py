"""Send RMD system reset (0x76), then probe status (0x9A) for up to 3 s. No current command is sent."""
import struct, time, can
with can.Bus(interface='socketcan', channel='can0', can_filters=[{'can_id':0x241,'can_mask':0x7ff,'extended':False}]) as bus:
    def send(op, payload=b'\0'*7): bus.send(can.Message(arbitration_id=0x141,is_extended_id=False,data=bytes([op])+payload),timeout=.02)
    def probe(op):
        send(op); end=time.monotonic()+.1
        while (r:=end-time.monotonic())>0:
            m=bus.recv(r)
            if m and len(m.data)==8 and m.data[0]==op: return bytes(m.data)
        return None
    print('before reset 0x9A:', probe(0x9a), flush=True)
    send(0x76); print('sent 0x76 reset', flush=True)
    t0=time.monotonic(); rep=None
    while time.monotonic()-t0<3 and rep is None:
        time.sleep(.2); rep=probe(0x9a)
    if rep:
        v,f=struct.unpack_from('<HH',rep,4); print(f'after reset: voltage {v/10:.1f} V, faults 0x{f:04x}, at {time.monotonic()-t0:.1f} s', flush=True)
        print('0xB3 now (write 0 = read back?) skipped', flush=True)
    else: print('after reset: still no reply', flush=True)
