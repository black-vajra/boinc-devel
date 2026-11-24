import json
import os
import signal
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/thermal_guardian_executor.py'

class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.sock, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.sock.settimeout(10)
        self.proc = subprocess.Popen([sys.executable, str(SCRIPT), '--fd', str(child.fileno())], pass_fds=(child.fileno(),))
        child.close()
        self.addCleanup(self.cleanup)
        self.assertEqual(self.recv()['kind'], 'READY')

    def cleanup(self):
        self.sock.close()
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=3)

    def recv(self):
        return json.loads(self.sock.recv(4096))

    def send(self, kind, value):
        self.sock.send(json.dumps(dict(kind=kind,value=value)).encode())

    def emergency(self):
        self.send('THERMAL','EMERGENCY')
        msg=self.recv()
        self.assertEqual(msg['state'],'COUNTDOWN')
        return msg['deadline']

    def check_deadline(self, deadline):
        while True:
            msg=self.recv()
            if msg['kind']=='SIMULATED_SHUTDOWN':
                break
        late=msg['at']-deadline
        print(f' deadline lateness: {late:.6f}s', flush=True)
        self.assertGreaterEqual(late,0)
        self.assertLess(late,0.25)
        self.assertEqual(self.proc.wait(timeout=2),0)

    def test_unattended(self):
        self.check_deadline(self.emergency())

    def test_recovery_and_fault(self):
        d=self.emergency()
        self.send('THERMAL','NORMAL')
        self.assertEqual(self.recv()['deadline'],d)
        self.send('THERMAL','FAULT')
        self.assertEqual(self.recv()['deadline'],d)
        self.check_deadline(d)

    def test_sender_stopped(self):
        # Separate sender process holds a copy of the endpoint, then freezes.
        code='import os,signal,socket,json,sys; s=socket.socket(fileno=int(sys.argv[1])); s.send(json.dumps(dict(kind="THERMAL",value="EMERGENCY")).encode()); os.kill(os.getpid(),signal.SIGSTOP)'
        p=subprocess.Popen([sys.executable,'-c',code,str(self.sock.fileno())],pass_fds=(self.sock.fileno(),))
        try:
            msg=self.recv()
            self.assertEqual(msg['state'],'COUNTDOWN')
            self.check_deadline(msg['deadline'])
        finally:
            p.kill(); p.wait(timeout=3)

    def test_critical(self):
        start=time.monotonic()
        self.send('THERMAL','CRITICAL')
        msg=self.recv()
        self.assertEqual(msg['kind'],'SIMULATED_SHUTDOWN')
        self.assertLess(msg['at']-start,0.25)

    def test_yes(self):
        self.emergency()
        start=time.monotonic()
        self.send('OPERATOR','YES')
        msg=self.recv()
        self.assertEqual(msg['kind'],'SIMULATED_SHUTDOWN')
        self.assertLess(msg['at']-start,0.25)

    def test_override_then_critical(self):
        self.emergency()
        self.send('OPERATOR','NO')
        msg=self.recv()
        self.assertEqual(msg['state'],'OVERRIDE')
        self.send('OPERATOR','NO')
        self.assertEqual(self.recv()['deadline'],msg['deadline'])
        self.send('THERMAL','CRITICAL')
        self.assertEqual(self.recv()['kind'],'SIMULATED_SHUTDOWN')

    def test_peer_loss(self):
        d=self.emergency()
        self.sock.close()
        self.assertEqual(self.proc.wait(timeout=9),0)
        self.assertGreaterEqual(time.monotonic(),d)
        self.assertLess(time.monotonic()-d,0.25)

if __name__=='__main__':
    unittest.main()
