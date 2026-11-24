#!/usr/bin/env python3
"""Independent read-only diagnostic worker. No shutdown authority."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

COMMANDS = {
    'sensors': ['sensors'],
    'boinc-tasks': ['boinccmd', '--get_tasks'],
    'boinc-service': ['systemctl', 'status', 'boinc-client.service', '--no-pager'],
    'processes': ['ps', '-eLo', 'pid,ppid,tid,psr,pcpu,pmem,comm'],
    'memory': ['free', '-h'],
    'swap': ['swapon', '--show'],
    'uptime': ['uptime'],
    'kernel': ['journalctl', '-k', '-n', '80', '--no-pager'],
}

def publish(directory, name, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as f:
            temporary = Path(f.name)
            json.dump(data, f, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, directory / (name + '.json'))
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def collect(command, timeout=2):
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                errors='replace', timeout=timeout, check=False)
        return dict(command=command, returncode=result.returncode,
                    stdout=result.stdout, stderr=result.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return dict(command=command, error=str(exc))

def hardware():
    from thermal_guardian import discover_temperatures, discover_gpu, read_number, read_text
    fans = []
    for h in Path('/sys/class/hwmon').glob('hwmon*'):
        values = {p.name: read_number(p) for pattern in ('fan*_input','fan*_target','pwm[0-9]','pwm*_enable') for p in h.glob(pattern)}
        if values:
            fans.append(dict(driver=read_text(h/'name'), device=str((h/'device').resolve()), values=values))
    rapl = Path('/sys/class/powercap/intel-rapl:0')
    a = read_number(rapl/'energy_uj')
    start = time.monotonic()
    time.sleep(0.2)
    b = read_number(rapl/'energy_uj')
    elapsed = time.monotonic()-start
    maximum = read_number(rapl/'max_energy_range_uj')
    watts = ((b-a)%maximum)/1e6/elapsed if a is not None and b is not None and maximum and maximum > 0 else None
    return dict(temperatures=discover_temperatures(), gpu=discover_gpu(), fans=fans, cpu_package_watts=watts,
                rapl_limits_uw={p.name:read_number(p) for p in rapl.glob('constraint_*_power_limit_uw')})

def run(directory, payload, stall=False, commands=None):
    publish(directory, 'trigger', payload['trigger'])
    publish(directory, 'thermal-history', payload['history'])
    publish(directory, 'collection-status', {'state':'IN_PROGRESS'})
    if stall:
        time.sleep(120)
    publish(directory, 'hardware', hardware())
    outcomes = {}
    for name, command in (COMMANDS if commands is None else commands).items():
        result = collect(command)
        publish(directory, name, result)
        outcomes[name] = 'PASS' if result.get('returncode') == 0 else 'WARN'
    publish(directory, 'collection-status', {'state':'COMPLETE', 'commands':outcomes})

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--stall', action='store_true')
    a = p.parse_args()
    run(a.directory, json.loads(a.input.read_text()), a.stall)

if __name__ == '__main__':
    main()
