# BOINC 8.2.11 engineering note

## Status

BOINC 8.2.11 was built and validated on the secondary SableLinux EliteBook
host `vulfen`. This proves package feasibility but does not make EliteBook
binaries authoritative release inputs.

## Validated components

- BOINC 8.2.11
- BOINC upstream commit `5511380b8980935c25c3ea41df3980445419e59e`
- BOINC Manager 8.2.11
- libnotify 0.8.8
- wxWidgets 3.2.11, GTK3 Unicode configuration
- systemd service using a dedicated `boinc:boinc` account

## Important build correction

The standalone SableLinux build must retain BOINC's internal libraries.
Packaging shortcuts such as `--enable-pkg-client` or
`--enable-pkg-manager` disabled required libraries and caused final linker
failures. The successful client and Manager configurations used
`--enable-libraries`.

## Runtime layout and policy

- Programs: `/opt/boinc/8.2.11`
- Current-version link: `/opt/boinc/current`
- Runtime data: `/var/lib/boinc-client`
- Service: `boinc-client.service`
- Service remains disabled at boot
- Operator starts and stops BOINC manually through `boincctl`
- CPU allocation: 50 percent of 16 logical CPUs
- Computation allowed while the desktop is active
- Computation disabled while running on battery
- Manager runtime discovery: `/etc/boinc-client/config.properties`
- Correct Manager option for the runtime directory: `--datadir`

Asteroids@home and MilkyWay@home were attached and exercised successfully.

## Known executable hashes

- `boinc_client`: `d6c94057aac3b82ff05068e10e55603e8ad4b24f7de73f67478012076f2bc566`
- `boinccmd`: `78fccbb2b4f6d95d207c9cedc403a493c381d42c55167a6f6efc79d672b8971e`
- `boincmgr`: `7cbd7fe89ae80f14993029f6a806a80813091d60412d7bddcfc51445d716f666`

Additional hashes are preserved in the EliteBook evidence manifest.

## Canonical next step

Rebuild BOINC, libnotify, wxWidgets, and BOINC Manager independently on the
authoritative Z890 SableLinux installation. Generate normalized scripts, logs,
metadata, manifests, and validation reports there. Do not copy EliteBook
binaries into the canonical installation.
