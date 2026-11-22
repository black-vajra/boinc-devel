#!/usr/bin/env python3
"""Regression tests for project selection, lifecycle, and thread masks."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('affinity', Path(__file__).parents[1] / 'scripts/lhc_affinity.py')
affinity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(affinity)


def task(pid, url='https://lhcathome.cern.ch/lhcathome/', state='EXECUTING'):
    return {'name': 'test_task', 'PID': str(pid), 'project URL': url,
            'active_task_state': state, 'scheduler state': 'scheduled', 'state': 'downloaded'}


class Selection(unittest.TestCase):
    def test_reported_suspended_cms_is_inactive(self):
        text = '''======== Tasks ========
1) -----------
   name: Einstein
   project URL: https://einstein.phys.uwm.edu/
   state: downloaded
   scheduler state: scheduled
   active_task_state: EXECUTING
   PID: 1501203
2) -----------
   name: CMS_1537_1795018634.874498_0
   project URL: https://lhcathome.cern.ch/lhcathome/
   state: downloaded
   scheduler state: preempted
   active_task_state: SUSPENDED
   PID: 973932
'''
        tasks = affinity.parse_tasks(text)
        self.assertFalse(any(affinity.executing(t) and affinity.is_lhc(t['project URL']) for t in tasks))

    def test_exact_project_url(self):
        self.assertTrue(affinity.is_lhc('http://lhcathome.cern.ch/lhcathome'))
        for url in ('https://lhcathome.cern.ch.evil/lhcathome/',
                    'https://einstein.phys.uwm.edu/', 'https://lhcathome.cern.ch/other/'):
            self.assertFalse(affinity.is_lhc(url))

    def test_only_executing_lhc_tree(self):
        snapshot = {10: (1, 1), 11: (10, 2), 12: (11, 3), 20: (1, 4), 21: (20, 5)}
        with patch.object(affinity.os, 'readlink', side_effect=FileNotFoundError):
            active, found = affinity.lhc_processes([task(10), task(20, 'https://einstein.phys.uwm.edu/')], snapshot)
        self.assertEqual(found, {10, 11, 12})
        self.assertEqual(len(active), 1)

    def test_suspended_and_queued_have_no_pids(self):
        with patch.object(affinity.os, 'readlink', side_effect=FileNotFoundError):
            active, found = affinity.lhc_processes([task(10, state='SUSPENDED'), task(20, state='UNINITIALIZED')], {10: (1, 1)})
        self.assertEqual((active, found), ([], set()))

    def test_bad_rpc_output_fails_closed(self):
        with self.assertRaises(RuntimeError):
            affinity.parse_tasks('Authorization failure')
        self.assertEqual(affinity.parse_tasks('======== Tasks ========'), [])

    def test_docker_exact_name_and_live_pid(self):
        result = subprocess.CompletedProcess([], 0, '[{"Name":"/boinc__lhcathome.cern.ch_lhcathome__test_task","State":{"Running":true,"Paused":false,"Pid":45}}]', '')
        with patch.object(affinity.subprocess, 'run', return_value=result) as run:
            self.assertEqual(affinity.docker_roots([dict(task(10), plan_class='docker')]), {45})
            self.assertEqual(run.call_args.args[0][-1], 'boinc__lhcathome.cern.ch_lhcathome__test_task')

    def test_wraparound_has_four_unique_cpus_and_equal_coverage(self):
        pool = list(range(14))
        masks = [affinity.window(pool, 4, offset) for offset in (0, 4, 8, 12, 2, 6, 10)]
        self.assertEqual(masks[3], {12, 13, 0, 1})
        self.assertTrue(all(len(mask) == 4 for mask in masks))
        self.assertEqual([sum(cpu in mask for mask in masks) for cpu in pool], [2] * 14)

    def test_no_lhc_exits_without_sleep_or_affinity_changes(self):
        args = type('Args', (), dict(pool=1, cores=1, interval=10, step=1))()
        with patch.object(affinity, 'get_tasks', return_value=[task(20, 'https://einstein.phys.uwm.edu/')]), \
             patch.object(affinity, 'processes', return_value={20: (1, 1)}), \
             patch.object(affinity.os, 'sched_setaffinity') as assign, \
             patch.object(affinity.time, 'sleep') as sleep:
            affinity.manage(args)
        assign.assert_not_called()
        sleep.assert_not_called()

    def test_reused_thread_id_is_never_restored(self):
        manager = affinity.Affinity()
        manager.saved[45] = (100, {0, 1})
        with patch.object(affinity, 'process_identity', return_value=(1, 200)), \
             patch.object(affinity.os, 'sched_setaffinity') as assign:
            manager.restore()
        assign.assert_not_called()
        self.assertEqual(manager.saved, {})

    def test_live_threads_rotate_restore_and_other_process_is_untouched(self):
        code = 'import threading,time; threading.Thread(target=time.sleep,args=(60,),daemon=True).start(); print("ready",flush=True); time.sleep(60)'
        with subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True) as worker, \
             subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True) as other:
            worker.stdout.readline()
            other.stdout.readline()
            original = os.sched_getaffinity(worker.pid)
            untouched = os.sched_getaffinity(other.pid)
            manager = affinity.Affinity()
            try:
                snapshot = affinity.processes()
                one = {min(original)}
                threads, _ = manager.apply({worker.pid}, snapshot, one)
                self.assertEqual(threads, 2)
                for entry in Path(f'/proc/{worker.pid}/task').iterdir():
                    self.assertEqual(os.sched_getaffinity(int(entry.name)), one)
                manager.apply({worker.pid}, snapshot, {max(original)})
                self.assertEqual(os.sched_getaffinity(worker.pid), {max(original)})
                self.assertEqual(os.sched_getaffinity(other.pid), untouched)
                manager.restore()
                for entry in Path(f'/proc/{worker.pid}/task').iterdir():
                    self.assertEqual(os.sched_getaffinity(int(entry.name)), original)
            finally:
                manager.restore()
                worker.terminate()
                other.terminate()
                worker.wait()
                other.wait()

    def test_existing_thread_masks_are_restored_individually(self):
        manager = affinity.Affinity()
        with patch.object(affinity, 'process_identity', return_value=(1, 5)), \
             patch.object(affinity.Path, 'iterdir', return_value=[Path('41'), Path('42')]), \
             patch.object(affinity.os, 'sched_getaffinity', side_effect=[{0, 1}, {0, 1}, {2, 3}]), \
             patch.object(affinity.os, 'sched_setaffinity'):
            manager.apply({41}, {41: (1, 5)}, {0})
        self.assertEqual(manager.saved[41][1], {0, 1})
        self.assertEqual(manager.saved[42][1], {2, 3})

    def test_late_child_recovers_parent_original_mask(self):
        manager = affinity.Affinity()
        manager.saved[10] = (1, {0, 1, 2, 3})
        manager.masks.add(frozenset({0}))
        with patch.object(affinity, 'process_identity', side_effect=[(10, 2), (10, 2), (1, 1)]), \
             patch.object(affinity.Path, 'iterdir', return_value=[Path('11')]), \
             patch.object(affinity.os, 'sched_getaffinity', return_value={0}), \
             patch.object(affinity.os, 'sched_setaffinity'):
            manager.apply({11}, {11: (10, 2)}, {1})
        self.assertEqual(manager.saved[11][1], {0, 1, 2, 3})

    def test_watcher_stops_on_no_lhc_and_on_rpc_failure(self):
        script = Path(__file__).parents[1] / 'scripts/lhc_affinity_watch.sh'
        for returncode in (1, 2):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'systemctl').write_text('#!/bin/sh\necho "$*" >> "$CALLS"\nexit 0\n')
                (root / 'python3').write_text(f'#!/bin/sh\nexit {returncode}\n')
                for name in ('systemctl', 'python3'):
                    (root / name).chmod(0o755)
                result = subprocess.run(['bash', str(script)], env={**os.environ, 'PATH': directory + ':' + os.environ['PATH'], 'CALLS': str(root / 'calls')})
                self.assertEqual(result.returncode, 0 if returncode == 1 else 2)
                calls = (root / 'calls').read_text()
                self.assertIn('stop boinc-affinity.service', calls)
                self.assertNotIn('start boinc-affinity.service', calls)


if __name__ == '__main__':
    unittest.main()
