#!/usr/bin/env python3

"""Watchdog failure source for fallback dispatch testing."""

import os
import socket
import time


def notify(message):
    address = os.environ["NOTIFY_SOCKET"]

    if address.startswith("@"):
        address = chr(0) + address[1:]

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_DGRAM,
    ) as connection:
        connection.sendto(message.encode(), address)


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Do not run this fixture as root")

    notify("READY=1")

    print("PASS: Watchdog test source ready", flush=True)

    while True:
        notify("WATCHDOG=1")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
