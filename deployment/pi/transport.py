"""Bounded JSONL stream adapter for a future transport. Motor enable stays false."""
import json,socket,time
MAX_FRAME=4096
class JsonLineChannel:
    def __init__(self,sock,timeout):
        self.sock=sock; sock.settimeout(timeout); self.buffer=b''
    def receive(self):
        while b'\n' not in self.buffer:
            chunk=self.sock.recv(1024)
            if not chunk: raise ConnectionError('disconnected')
            self.buffer+=chunk
            if len(self.buffer)>MAX_FRAME: raise ValueError('oversized frame')
        line,self.buffer=self.buffer.split(b'\n',1)
        return json.loads(line)
    def send(self,message):
        raw=json.dumps(message,allow_nan=False,separators=(',',':')).encode()+b'\n'
        if len(raw)>MAX_FRAME: raise ValueError('oversized frame')
        self.sock.sendall(raw)
def serve_disabled(channel,guard,actor,log):
    """Pass a connected socket explicitly. Reference transport, no physical adapter."""
    try:
        while True:
            packet=channel.receive(); now=time.monotonic(); cmd=guard.command(packet,now,actor)
            channel.send(cmd)
            log.write(json.dumps({'receive_t_pi_s':now,'packet':packet,'command':cmd},allow_nan=False)+'\n'); log.flush()
            if guard.latched: break
    except Exception as e:
        guard.latched=True
        try: channel.send({'schema':'furuta-io-v1','enable':False,'torque_nm':0,'fault':str(e)})
        except (OSError,ValueError): pass
    finally:
        channel.sock.close()
