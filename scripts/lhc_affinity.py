#!/usr/bin/env python3
"""Gate and manage affinity using live BOINC task identity, never process names."""

import argparse
import errno
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse


DATA_DIR = Path('/var/lib/boinc-client')
BOINCCMD = '/usr/local/bin/boinccmd'
PROJECT_DIR = 'lhcathome.cern.ch_lhcathome'


def log(message):
    print(time.strftime('%Y-%m-%d %H:%M:%S') + ' | ' + message, flush=True)


def is_lhc(url):
    parsed = urlparse(url)
    return (parsed.scheme in ('http', 'https')
            and parsed.hostname == 'lhcathome.cern.ch'
            and parsed.path.rstrip('/') == '/lhcathome')


def parse_tasks(output):
    tasks = []
    task = None
    for line in output.splitlines():
        if re.fullmatch(r'\s*\d+\) -+\s*', line):
            task = {}
            tasks.append(task)
        elif task is not None and ': ' in line:
            key, value = line.strip().split(': ', 1)
            task[key] = value
    if '======== Tasks ========' not in output:
        raise RuntimeError('BOINC task query did not return a task list')
    return tasks


def get_tasks():
    result = subprocess.run(
        [BOINCCMD, '--get_tasks'], cwd=DATA_DIR,
        text=True, capture_output=True, timeout=8,
        env={**os.environ, 'LC_ALL': 'C'}, check=True,
    )
    return parse_tasks(result.stdout)


def executing(task):
    return (task.get('active_task_state') == 'EXECUTING'
            and task.get('scheduler state') == 'scheduled'
            and task.get('state') == 'downloaded'
            and task.get('PID', '').isdigit()
            and int(task['PID']) > 0)


def process_identity(pid):
    """Return parent PID and kernel start time, including for individual threads."""
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return int(fields[1]), int(fields[19])


def processes():
    snapshot = {}
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                snapshot[int(entry.name)] = process_identity(int(entry.name))
            except (OSError, ValueError, IndexError):
                pass  # A process can exit while /proc is being read.
    return snapshot


def descendants(roots, snapshot):
    children = {}
    for pid, (parent, _) in snapshot.items():
        children.setdefault(parent, []).append(pid)
    found = set()
    pending = list(roots)
    while pending:
        pid = pending.pop()
        if pid in snapshot and pid not in found:
            found.add(pid)
            pending.extend(children.get(pid, ()))
    return found


def docker_roots(tasks):
    """Match only exact BOINC container names for executing LHC tasks."""
    roots = set()
    for task in tasks:
        if 'docker' not in task.get('plan_class', '').lower():
            continue
        name = f"boinc__{PROJECT_DIR}__{task['name']}".lower()
        result = subprocess.run(
            ['docker', 'inspect', '--type', 'container', name],
            capture_output=True, text=True, timeout=5, check=True,
        )
        info = json.loads(result.stdout)[0]
        state = info['State']
        if (info['Name'] == '/' + name and state['Running']
                and not state.get('Paused') and int(state['Pid']) > 0):
            roots.add(int(state['Pid']))
    return roots


def task_processes(active, snapshot):
    roots = {int(task['PID']) for task in active}
    # External VBoxHeadless processes can be reparented. Their working directory
    # must be the exact slot of a currently executing LHC task, with BOINC's UID.
    slots = {}
    for task in active:
        root = int(task['PID'])
        if root in snapshot and task.get('slot', '').isdigit():
            try:
                slots[str(DATA_DIR / 'slots' / task['slot'])] = Path(f'/proc/{root}').stat().st_uid
            except OSError:
                pass
    for pid in snapshot:
        try:
            directory = os.readlink(f'/proc/{pid}/cwd')
            if directory in slots and Path(f'/proc/{pid}').stat().st_uid == slots[directory]:
                roots.add(pid)
        except OSError:
            pass
    # The task listing has no plan_class on some BOINC versions. A live wrapper
    # executable identifies Docker mode only after RPC has identified its task.
    for task in active:
        try:
            executable = os.readlink(f"/proc/{task['PID']}/exe")
            if Path(executable).name.startswith('docker_wrapper'):
                task = dict(task, plan_class='docker')
                roots.update(docker_roots([task]))
        except FileNotFoundError:
            pass
    return descendants(roots, snapshot)


def lhc_processes(tasks, snapshot):
    active = [task for task in tasks if executing(task) and is_lhc(task.get('project URL', ''))]
    return active, task_processes(active, snapshot)


def reset_existing():
    # One deployment migration: the old script did not save original masks.
    # Restore confirmed BOINC tasks to the live client's allowed CPU set.
    result = subprocess.run(
        ['systemctl', 'show', 'boinc-client.service', '--property=MainPID', '--value'],
        capture_output=True, text=True, timeout=5, check=True,
    )
    client = int(result.stdout.strip())
    if client <= 0:
        return
    baseline = os.sched_getaffinity(client)
    tasks = [task for task in get_tasks() if task.get('PID', '').isdigit()
             and int(task['PID']) > 0 and task.get('state') == 'downloaded']
    snapshot = processes()
    for pid in task_processes(tasks, snapshot):
        try:
            if process_identity(pid) != snapshot[pid]:
                continue
            for thread in Path(f'/proc/{pid}/task').iterdir():
                os.sched_setaffinity(int(thread.name), baseline)
            log(f'PASS: released old affinity for BOINC PID {pid} to CPUs={sorted(baseline)}')
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.ESRCH):
                raise


class Affinity:
    def __init__(self):
        self.saved = {}
        self.masks = set()

    def restore(self, retained=frozenset()):
        for tid, (birth, original) in list(self.saved.items()):
            if tid in retained:
                continue
            try:
                if process_identity(tid)[1] == birth:
                    os.sched_setaffinity(tid, original)
                del self.saved[tid]
            except OSError as error:
                if error.errno in (errno.ENOENT, errno.ESRCH):
                    del self.saved[tid]
                else:
                    log(f'FAIL: restoring thread {tid}: {error}')

    def apply(self, pids, snapshot, mask):
        retained = set()
        changed = 0
        for pid in sorted(pids):
            try:
                if process_identity(pid) != snapshot[pid]:
                    continue
                # Children created after a rotation inherit a restricted mask.
                # Remember the task tree's original mask before pinning parents.
                parent = snapshot[pid][0]
                baseline = self.saved.get(parent, (None, None))[1]
                if baseline is None:
                    baseline = os.sched_getaffinity(pid)
                for thread in Path(f'/proc/{pid}/task').iterdir():
                    tid = int(thread.name)
                    birth = process_identity(tid)[1]
                    current = os.sched_getaffinity(tid)
                    if tid not in self.saved or self.saved[tid][0] != birth:
                        original = baseline if frozenset(current) in self.masks else current
                        self.saved[tid] = (birth, set(original))
                    retained.add(tid)
                    if current != mask:
                        os.sched_setaffinity(tid, mask)
                        changed += 1
            except OSError as error:
                if error.errno not in (errno.ENOENT, errno.ESRCH):
                    log(f'FAIL: assigning LHC PID {pid}: {error}')
        self.masks.add(frozenset(mask))
        self.restore(retained)
        return len(retained), changed


def window(pool, count, offset):
    return {pool[(offset + index) % len(pool)] for index in range(count)}


def manage(args):
    allowed = sorted(os.sched_getaffinity(0))
    if args.pool > len(allowed) or not 1 <= args.cores <= args.pool:
        raise RuntimeError('CPU pool exceeds allowed CPUs or active count is invalid')
    pool = allowed[:args.pool]
    affinity = Affinity()
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    offset = 0
    try:
        while not stopping:
            snapshot = processes()
            active, pids = lhc_processes(get_tasks(), snapshot)
            if not active or not pids:
                return
            mask = window(pool, args.cores, offset)
            threads, changed = affinity.apply(pids, snapshot, mask)
            log(f'PASS: LHC tasks={len(active)} processes={len(pids)} threads={threads} '
                f'pool={pool} CPUs={sorted(mask)} rotation={offset} changed={changed}')
            offset = (offset + args.step) % len(pool)
            deadline = time.monotonic() + args.interval
            while not stopping and time.monotonic() < deadline:
                time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    finally:
        affinity.restore()
        log('LHC affinity manager stopped; surviving managed threads restored')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check', 'manage', 'reset-existing'))
    parser.add_argument('--cores', type=int, default=4)
    parser.add_argument('--pool', type=int, default=14)
    parser.add_argument('--step', type=int, default=4)
    parser.add_argument('--interval', type=float, default=10)
    args = parser.parse_args()
    try:
        if args.mode == 'reset-existing':
            reset_existing()
            return 0
        if args.mode == 'check':
            tasks = get_tasks()
            return 0 if any(executing(task) and is_lhc(task.get('project URL', ''))
                            and Path(f"/proc/{task['PID']}").exists() for task in tasks) else 1
        if args.interval <= 0 or args.step < 1:
            raise RuntimeError('Polling interval and rotation step must be positive')
        manage(args)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        log(f'FAIL: LHC affinity: {error}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
