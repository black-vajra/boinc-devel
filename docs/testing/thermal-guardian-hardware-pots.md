# Pots Thermal Guardian Hardware Baseline

Date: 2026-11-23

## Hardware

Motherboard: Gigabyte Z890 AORUS ELITE X ICE
CPU: Intel Core Ultra 5 245K
GPU: AMD Radeon RX 9060 XT
GPU PCI address: 0000:03:00.0

## NVMe devices

PNY CS2150 1TB:
PCI address: 0000:04:00.0
Composite temperature: 44 C
Auxiliary sensor 1: 44 C

Samsung MZVL81T0HELB-00BTW:
PCI address: 0000:82:00.0
Composite temperature: 47 C
Auxiliary sensor 1: 69 C
Auxiliary sensor 2: 47 C

The Samsung auxiliary sensor consistently reports
substantially higher temperatures than its composite
sensor.

This is an established operating characteristic and
is not presently considered evidence of overheating.

Both NVMe devices report:
- Zero critical warnings
- Zero media errors
- Zero error log entries
- Zero warning temperature time
- Zero critical temperature time
- Zero thermal management transitions
- 100 percent available spare

Initial protection policy:
- Composite warning: 65 C
- Composite emergency: 75 C
- Composite immediate shutdown: 80 C
- Auxiliary sensors: observation and logging only

Auxiliary sensor limits remain unverified.

## GPU power control

Default power cap: 160 W
Minimum adjustable cap: 112 W
Maximum adjustable cap: 182 W
Planned initial power cap: 120 W

## Hardware watchdog

No watchdog device exposed.
RuntimeWatchdogUSec=0
RebootWatchdogUSec=10min
KExecWatchdogUSec=0

No watchdog configuration changes planned.

## Limitations

Motherboard VRM and PSU temperatures are not
currently exposed through identified sensors.

Software thermal monitoring cannot guarantee
protection against electrical faults, PSU overload,
or complete kernel lockup.
