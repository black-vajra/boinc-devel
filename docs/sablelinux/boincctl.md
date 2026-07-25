# BOINC Manual Control

SableLinux runs BOINC as a manually controlled systemd service.

The service is deliberately disabled at boot. Operators start and stop it
with the repository-managed `boincctl` command rather than enabling
`boinc-client.service`.

## Installed Components

- Client: `/opt/boinc/current/bin/boinc`
- Command client: `/opt/boinc/current/bin/boinccmd`
- Data directory: `/var/lib/boinc-client`
- Service: `boinc-client.service`
- Control command: `/usr/local/bin/boincctl`
- Repository source: `scripts/boinc/boincctl`

## Normal Operation

Start BOINC and wait for authenticated GUI-RPC readiness:

    boincctl start

View service state, client state, attached projects, tasks, and recent logs:

    boincctl view

Show concise service and policy status:

    boincctl status

Follow the live BOINC journal:

    boincctl logs

Stop BOINC cleanly:

    boincctl stop

Restart BOINC:

    boincctl restart

## Readiness Behavior

BOINC 8.2.11 requires approximately 14 seconds on the canonical Z890 host
before the local GUI-RPC listener becomes available at:

    127.0.0.1:31416

`boincctl start` waits up to 60 seconds for this listener before reporting
success or failure.

The GUI-RPC credential is stored in:

    /var/lib/boinc-client/gui_rpc_auth.cfg

The control script reads the credential as the `boinc` service account and
does not display it.

## Canonical Resource Policy

The canonical global preferences currently restrict BOINC to:

- 50 percent of available logical CPUs
- 7 of 14 logical CPUs on the Z890 host
- CPU execution while the user is active
- GPU execution while the user is active

The AMD Radeon RX 9060 XT is detected through the canonical ROCm/OpenCL
installation.

## Project Sequence

Asteroids@home is the initial validation and production project for the
canonical Z890 BOINC installation.

LHC@home is intentionally deferred until the remaining virtual-machine,
container, dependency, and affinity-management preparation has been
completed and validated.

Project attachment credentials and account keys must not be committed to
the repository.

## Boot Policy

The service must remain disabled:

    systemctl is-enabled boinc-client.service

Expected result:

    disabled

`boincctl` treats an enabled service as noncompliant with the manual-only
operating policy.

## Validation

The control script was validated on the canonical Z890 SableLinux system
on 2026-07-19.

Validated operations:

- stopped-state inspection
- controlled service start
- GUI-RPC readiness detection
- authenticated `boinccmd` access
- CPU and GPU state inspection
- project and task inspection
- journal inspection
- controlled service shutdown
- boot-policy preservation
- process and port cleanup

The archived validation report is:

    docs/testing/boincctl-install-validation-2026-07-19.txt
