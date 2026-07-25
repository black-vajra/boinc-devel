# EliteBook BOINC validation — July 18–19, 2026

## Test host

- Hostname: `vulfen`
- Hardware: HP EliteBook 645 G9
- CPU: AMD Ryzen 7 PRO 5875U, 16 logical CPUs
- Operating system: Sable Linux 1.0
- Kernel: `6.16.1-sable-compat2`
- Role: secondary hardware validation

## Result

BOINC 8.2.11 and BOINC Manager were built from source and installed under
versioned `/opt` prefixes. The daemon ran as the unprivileged `boinc` account.
The service remained disabled at boot and was controlled manually.

Validated functions included daemon startup and shutdown, `boinccmd`, local GUI
RPC authentication, GTK3 BOINC Manager operation, Asteroids@home execution,
MilkyWay@home attachment and scheduling, and eight-of-sixteen logical CPU
allocation.

During eight simultaneous Asteroids tasks the desktop remained responsive while
Firefox played YouTube audio through PipeWire. Memory pressure and storage use
were low. The hottest generic ACPI sensor reported about 83 C; the short sample
showed no obvious severe frequency collapse.

## Engineering findings

1. Client and Manager builds both require BOINC internal libraries.
2. `--enable-pkg-client` and `--enable-pkg-manager` were unsuitable here.
3. wxWidgets staged absolute symlinks must be checked after final promotion.
4. BOINC Manager uses `--datadir`, not `--clientdir`.
5. New group membership requires a new login session.
6. The Docker notice was generic and Asteroids@home did not require Docker.
7. The validated operating policy is manual start and stop.

## Evidence policy

Stored evidence excludes BOINC account keys, `gui_rpc_auth.cfg`, client state,
downloaded workloads, source trees, and compiled binaries. The EliteBook
material is evidence only; canonical reproduction belongs on the Z890.
