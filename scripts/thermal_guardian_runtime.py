#!/usr/bin/env python3

"""Thermal Guardian 1.0 integrated development runtime.

Real sensor monitoring.
Authenticated emergency communication.
Independent deadline enforcement.
Desktop operator interface.
Simulated shutdown actions only.
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import threading

from pathlib import Path

from thermal_guardian_secure_executor import run as executor
from thermal_guardian_independent import run as guardian
from thermal_guardian_registration import DeadlineRegistration
from thermal_guardian_recovery import RecoveryState
from thermal_guardian_ipc import authorize_peer

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
PYTHON = sys.executable


def listener(path):
    sock = socket.socket(
        socket.AF_UNIX, socket.SOCK_SEQPACKET
    )
    sock.setsockopt(
        socket.SOL_SOCKET, socket.SO_PASSCRED, 1
    )
    sock.bind(str(path))
    sock.listen(1)
    sock.settimeout(15)
    return sock


def connect(path):
    sock = socket.socket(
        socket.AF_UNIX, socket.SOCK_SEQPACKET
    )
    sock.setsockopt(
        socket.SOL_SOCKET, socket.SO_PASSCRED, 1
    )
    sock.settimeout(3)

    expires = time.monotonic() + 10

    while True:
        try:
            sock.connect(str(path))
            return sock
        except (FileNotFoundError, ConnectionRefusedError):
            if time.monotonic() >= expires:
                sock.close()
                raise
            time.sleep(0.05)

def read_pid_file(path, timeout=5):
    expires = time.monotonic() + timeout

    while True:
        try:
            raw = path.read_text().strip()

            if raw:
                pid = int(raw)

                if pid <= 0:
                    raise ValueError(f"Invalid PID in {path}")

                os.kill(pid, 0)
                return pid

        except FileNotFoundError:
            pass

        except ProcessLookupError:
            raise RuntimeError(
                f"Process recorded in {path} no longer exists"
            )

        if time.monotonic() >= expires:
            raise TimeoutError(
                f"Timed out waiting for valid PID: {path}"
            )

        time.sleep(0.01)


def simulated_action(directory, source, reason):
    record = {
        "simulated": True,
        "source": source,
        "reason": reason,
        "at": time.monotonic(),
    }

    # Atomically publish one simulated action record.
    temporary = directory / f"action-{os.getpid()}.tmp"
    temporary.write_text(json.dumps(record, indent=2))

    try:
        os.link(temporary, directory / "action.json")
        print("SIMULATED SHUTDOWN:", record, flush=True)
    except FileExistsError:
        print("Duplicate simulated action suppressed", flush=True)
    finally:
        temporary.unlink(missing_ok=True)


def guardian_main(directory, executor_pid):
    with listener(directory / "guardian.sock") as server:
        connection, _ = server.accept()

        with connection:
            return guardian(
                connection,
                expected_uid=os.getuid(),
                expected_pid=executor_pid,
                state_path=directory / "deadline.json",
                action=lambda record: simulated_action(
                    directory,
                    "independent guardian",
                    record["state"],
                ) or 0,
            )


def desktop(directory, sock, no_gui):
    window = None
    token = None

    sock.settimeout(0.1)

    try:
        while not (directory / "action.json").exists():

            try:
                raw = sock.recv(4096)

                if not raw:
                    break

                event = json.loads(raw)

                if event.get("kind") != "EMERGENCY_SESSION":
                    continue

                token = event["token"]
                deadline = event["deadline"]
                state = event["state"]

                print(
                    f"EMERGENCY: {state}; "
                    f"deadline={deadline:.6f}",
                    flush=True,
                )

                if window is not None and window.poll() is None:
                    window.terminate()
                    window.wait(timeout=2)

                window = None

                if not no_gui:
                    command = [
                        PYTHON,
                        str(SCRIPTS / "thermal_guardian_ui.py"),
                        "--sensor", "Thermal Guardian",
                        "--temperature", "101",
                        "--threshold", "100",
                        "--seconds",
                        str(30 if state == "OVERRIDE" else 7),
                        "--deadline", str(deadline),
                        "--alarm",
                        str(ROOT / "assets/sounds/thermal-emergency.wav"),
                    ]

                    if state == "OVERRIDE":
                        command.append("--override")

                    window = subprocess.Popen(command)

            except socket.timeout:
                pass

            if window is not None:
                code = window.poll()

                if code is not None:
                    window = None

                    if code in (10, 20):
                        sock.send(json.dumps({
                            "kind": "OPERATOR",
                            "value": "YES" if code == 10 else "NO",
                            "token": token,
                        }).encode())

    except OSError:
        pass

    finally:
        if window is not None and window.poll() is None:
            window.terminate()
            try:
                window.wait(timeout=2)
            except subprocess.TimeoutExpired:
                window.kill()
                window.wait()


def executor_main(directory, supervisor_pid, no_gui):
    with connect(directory / "guardian.sock") as registration:

        guardian_pid = read_pid_file(
            directory / "guardian-pid"
        )

        register = DeadlineRegistration(
            registration, os.getuid(), guardian_pid
        )

        with listener(directory / "executor.sock") as server:

            thermal, _ = server.accept()

            operator_rx, operator_tx = socket.socketpair(
                socket.AF_UNIX, socket.SOCK_SEQPACKET
            )

            operator_rx.setsockopt(
                socket.SOL_SOCKET, socket.SO_PASSCRED, 1
            )

            with thermal, operator_rx, operator_tx:

                ui = threading.Thread(
                    target=desktop,
                    args=(directory, operator_tx, no_gui),
                    daemon=True,
                )

                ui.start()

                def action(decision):
                    simulated_action(
                        directory, "executor", decision.reason
                    )

                result = executor(
                    thermal,
                    operator_rx,
                    thermal_uid=os.getuid(),
                    thermal_pid=supervisor_pid,
                    operator_uid=os.getuid(),
                    operator_pid=os.getpid(),
                    action=action,
                    deadline_registration=register,
                    notify_address=os.environ["NOTIFY_SOCKET"],
                )

                ui.join(timeout=2)
                return result


def supervisor_main(directory, config):
    import thermal_guardian_supervisor as supervisor

    original_sample = supervisor.sample

    def sample(settings):
        snapshot = original_sample(settings)

        if (
            (directory / "trigger").exists()
            and snapshot["level"] != "CRITICAL"
        ):
            reading = next(
                item for item in snapshot["temperatures"]
                if item.get("policy") is not None
            )

            policy = next(
                item for item in settings["sensors"]
                if item["name"] == reading["policy"]
            )

            reading["temperature"] = policy["emergency"] + 1
            reading["level"] = "EMERGENCY"
            snapshot["level"] = "EMERGENCY"

        return snapshot

    supervisor.sample = sample

    expires = time.monotonic() + 15

    executor_socket = directory / "executor.sock"
    executor_pid_file = directory / "executor-pid"

    while not (
        executor_socket.exists()
        and executor_pid_file.is_file()
    ):
        if time.monotonic() >= expires:
            raise RuntimeError(
                "Executor registration startup timeout"
            )

        time.sleep(0.01)

    sys.argv = [
        "thermal_guardian_supervisor.py",
        "--config", str(config),
        "--state-dir", str(directory),
        "--executor-socket", str(directory / "executor.sock"),
        "--executor-pid",
        (directory / "executor-pid").read_text(),
    ]

    return supervisor.main()


def publish_pid(path, pid):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(f"{pid}\n")
    os.replace(temporary, path)


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Development runtime must not run as root")

    os.umask(0o077)

    parser = argparse.ArgumentParser()
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--simulate-emergency", action="store_true")
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()

    directory = Path(tempfile.mkdtemp(prefix="tg-runtime-"))

    print("=== THERMAL GUARDIAN 1.0 ===", flush=True)
    print("Shutdown authority: DISABLED", flush=True)
    print(f"Evidence: {directory}", flush=True)

    config = ROOT / "examples/thermal-guardian-pots.json"

    recovery = RecoveryState(
        directory / "operating-state.json"
    )

    recovery.authorize_recovery(
        "Isolated development runtime"
    )

    processes = []

    with socket.socket(
        socket.AF_UNIX, socket.SOCK_DGRAM
    ) as notifications:

        address = str(directory / "notify.sock")
        notifications.bind(address)
        notifications.settimeout(0.5)

        environment = os.environ.copy()
        environment["NOTIFY_SOCKET"] = address
        environment["PYTHONPATH"] = str(SCRIPTS)

        def launch(code, *arguments):
            process = subprocess.Popen([
                PYTHON, "-u", "-c", code,
                *map(str, arguments),
            ], env=environment)

            processes.append(process)
            return process

        try:
            # Start each protective role as a separate process.
            supervisor = launch(
                "import sys; from pathlib import Path; "
                "from thermal_guardian_runtime import supervisor_main; "
                "raise SystemExit(supervisor_main("
                "Path(sys.argv[1]), Path(sys.argv[2])))",
                directory, config,
            )

            executor_process = launch(
                "import sys; from pathlib import Path; "
                "from thermal_guardian_runtime import executor_main; "
                "raise SystemExit(executor_main("
                "Path(sys.argv[1]), int(sys.argv[2]), "
                "sys.argv[3]=='True'))",
                directory, supervisor.pid, args.no_gui,
            )

            publish_pid(
                directory / "executor-pid",
                executor_process.pid,
            )

            guardian_process = launch(
                "import sys; from pathlib import Path; "
                "from thermal_guardian_runtime import guardian_main; "
                "raise SystemExit(guardian_main("
                "Path(sys.argv[1]), int(sys.argv[2])))",
                directory, executor_process.pid,
            )

            publish_pid(
                directory / "guardian-pid",
                guardian_process.pid,
            )

            ready = 0
            startup_deadline = time.monotonic() + 20

            while ready < 2:
                if time.monotonic() >= startup_deadline:
                    raise RuntimeError("Runtime readiness timeout")

                if any(p.poll() is not None for p in processes):
                    raise RuntimeError("Protective process exited")

                try:
                    message = notifications.recv(4096).decode()
                except socket.timeout:
                    continue

                if "READY=1" in message:
                    ready += 1

            if recovery.status() != "ARMED":
                raise RuntimeError("Recovery interlock not armed")

            print("PASS: Connected runtime ready", flush=True)

            if args.simulate_emergency:
                print("Injecting isolated simulated emergency", flush=True)
                (directory / "trigger").touch()

            expires = time.monotonic() + args.duration

            while time.monotonic() < expires:

                if (directory / "action.json").exists():
                    # The marker alone does not prove that the supervisor
                    # received the authenticated completion packet.
                    completion_deadline = time.monotonic() + 3
                    while (
                        supervisor.poll() is None
                        and time.monotonic() < completion_deadline
                    ):
                        time.sleep(0.02)

                    if supervisor.poll() != 0:
                        raise RuntimeError(
                            "Action recorded but supervisor did not "
                            "confirm executor completion"
                        )

                    executor_deadline = time.monotonic() + 2
                    while (
                        executor_process.poll() is None
                        and time.monotonic() < executor_deadline
                    ):
                        time.sleep(0.02)

                    if executor_process.returncode != 0:
                        raise RuntimeError(
                            "Executor did not exit successfully after "
                            "completion acknowledgement"
                        )

                    print(
                        "PASS: Authenticated supervisor completion",
                        flush=True,
                    )
                    print("PASS: Emergency action recorded", flush=True)
                    print(
                        (directory / "action.json").read_text(),
                        flush=True,
                    )
                    return 0

                if any(p.poll() is not None for p in processes):
                    raise RuntimeError("Protective process exited")

                time.sleep(0.1)

            if args.simulate_emergency:
                raise RuntimeError("Expected emergency action missing")

            print("PASS: Normal monitoring interval completed")
            return 0

        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()

            for process in processes:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

            print(
                f"Final recovery state: {recovery.status()}",
                flush=True,
            )

            print(f"Evidence retained: {directory}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
