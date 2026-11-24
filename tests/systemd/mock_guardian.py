#!/usr/bin/env python3

"""Harmless systemd readiness and watchdog simulator."""

import os
import socket
import time


def notify(message):
    address = os.environ["NOTIFY_SOCKET"]

    if address.startswith("@"):
        address = "\0" + address[1:]

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_DGRAM,
    ) as sock:
        sock.connect(address)
        sock.sendall(message.encode())


def main():
    print("Guardian initialization", flush=True)

    time.sleep(3)

    notify("READY=1\nSTATUS=Simulated guardian ready")

    print("Guardian READY", flush=True)

    while True:
        notify("WATCHDOG=1")
        time.sleep(1)


if __name__ == "__main__":
    main()
