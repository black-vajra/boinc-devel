#!/usr/bin/env python3

"""Thermal Guardian Desktop emergency interface.

This interface has no authority to shut down the system.
It reports operator decisions to the calling process.
"""

import argparse
import math
import subprocess
import sys
import time
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QHBoxLayout,
)

EXIT_SHUTDOWN = 10
EXIT_OVERRIDE = 20
EXIT_TIMEOUT = 30

DEFAULT_ALARM = (
    Path(__file__).resolve().parent.parent
    / "assets/sounds/thermal-emergency.wav"
)


class EmergencyDialog(QDialog):

    def __init__(self, args):
        super().__init__()

        self.args = args
        self.alarm = None
        self.deadline = time.monotonic() + args.seconds

        self.setWindowTitle("SYSTEM THERMAL EMERGENCY")
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowStaysOnTopHint
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
        )

        self.setMinimumSize(660, 390)

        self.setStyleSheet("""
            QDialog {
                background-color: #171717;
                color: white;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                padding: 15px;
                font-size: 15px;
                font-weight: bold;
                border-radius: 5px;
            }
            QProgressBar {
                border: 1px solid #555555;
                background-color: #333333;
                text-align: center;
                color: white;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #d32020;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("SYSTEM THERMAL EMERGENCY")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: #ff4444;
            font-size: 27px;
            font-weight: bold;
        """)
        layout.addWidget(title)

        if not args.live:
            test = QLabel("SIMULATION ONLY — NO ACTUAL SHUTDOWN")
            test.setAlignment(Qt.AlignCenter)
            test.setStyleSheet("color: #ffcc00; font-weight: bold;")
            layout.addWidget(test)

        details = QLabel(
            f"Sensor: {args.sensor}\n"
            f"Current temperature: {args.temperature:.1f} °C\n"
            f"Emergency threshold: {args.threshold:.1f} °C"
        )
        details.setTextFormat(Qt.PlainText)
        details.setAlignment(Qt.AlignCenter)
        details.setStyleSheet("font-size: 18px;")
        layout.addWidget(details)

        self.countdown = QLabel()
        self.countdown.setAlignment(Qt.AlignCenter)
        self.countdown.setStyleSheet("""
            color: #ff4444;
            font-size: 48px;
            font-weight: bold;
        """)
        layout.addWidget(self.countdown)

        self.progress = QProgressBar()
        self.progress.setRange(0, args.seconds * 1000)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        question = QLabel("Continue emergency shutdown?")
        question.setAlignment(Qt.AlignCenter)
        question.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(question)

        buttons = QHBoxLayout()

        yes = QPushButton("YES — SHUT DOWN NOW")
        yes.setStyleSheet("""
            background-color: #a51e1e;
            color: white;
        """)
        yes.setAutoDefault(False)
        yes.setDefault(False)
        yes.setFocusPolicy(Qt.NoFocus)
        yes.clicked.connect(
            lambda: self.finish(EXIT_SHUTDOWN)
        )

        no = QPushButton("NO — MANUAL INTERVENTION")
        no.setStyleSheet("""
            background-color: #444444;
            color: white;
        """)
        no.setAutoDefault(False)
        no.setDefault(False)
        no.setFocusPolicy(Qt.NoFocus)
        no.clicked.connect(
            lambda: self.finish(EXIT_OVERRIDE)
        )

        buttons.addWidget(yes)
        buttons.addWidget(no)
        layout.addLayout(buttons)

        footer = QLabel(
            "No response will result in automatic shutdown."
        )
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #bbbbbb; font-size: 13px;")
        layout.addWidget(footer)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(50)

        self.update_countdown()
        self.start_alarm()

    def start_alarm(self):
        try:
            self.alarm = subprocess.Popen(
                ["/usr/bin/paplay", str(self.args.alarm)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            print("WARN: Emergency alarm unavailable", file=sys.stderr)

    def stop_alarm(self):
        if self.alarm and self.alarm.poll() is None:
            self.alarm.terminate()

    def update_countdown(self):
        remaining = max(0, self.deadline - time.monotonic())

        self.countdown.setText(
            f"SHUTDOWN IN {math.ceil(remaining)}"
        )

        self.progress.setValue(int(remaining * 1000))

        if remaining <= 0:
            self.finish(EXIT_TIMEOUT)

    def finish(self, result):
        self.timer.stop()
        self.stop_alarm()
        self.done(result)

    def reject(self):
        # Escape must not cancel an emergency.
        pass

    def closeEvent(self, event):
        # Closing the window must not cancel an emergency.
        event.ignore()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--sensor", default="GPU junction")
    parser.add_argument("--temperature", type=float, default=101.0)
    parser.add_argument("--threshold", type=float, default=100.0)
    parser.add_argument("--seconds", type=int, default=7)
    parser.add_argument("--alarm", type=Path, default=DEFAULT_ALARM)

    parser.add_argument(
        "--live",
        action="store_true",
        help="Remove simulation banner; does not enable shutdown.",
    )

    args = parser.parse_args()

    if not 1 <= args.seconds <= 60:
        parser.error("Countdown must be between 1 and 60 seconds")

    app = QApplication(sys.argv[:1])
    dialog = EmergencyDialog(args)

    try:
        return dialog.exec_()
    finally:
        dialog.stop_alarm()


if __name__ == "__main__":
    sys.exit(main())
