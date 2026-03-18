# BOINC Preference Layers

*Applies to: BOINC 8.x, multiple attached projects*

---

## The Three-Layer Hierarchy

BOINC resolves computing preferences from three sources, in descending priority:

```
local override  (global_prefs_override.xml)   ← highest priority
      │
web preferences (global_prefs.xml)            ← sourced from a project server
      │
BOINC defaults                                ← fallback
```

In practice the interaction between the first two layers is more complex than a simple
override — see below.

---

## Layer 1: Web Preferences (`global_prefs.xml`)

Each attached project can serve a `global_prefs.xml` to the client containing your
computing preferences as set on that project's website. BOINC downloads and caches this
file locally at `/var/lib/boinc-client/global_prefs.xml`.

**Critical behaviour: the source project mechanism**

BOINC does not merge web preferences from all attached projects. It uses the preferences
from whichever project was **most recently updated** as the single authoritative source.
This is referred to internally as the "source project."

Any time you click "Update" on a project in BOINC Manager, or BOINC scheduler contacts
that project, the preferences from that project become the active web preferences —
potentially overriding what you set via another project last week.

**Venues**

Web preferences support named venues: `home`, `work`, `school`. A project can serve
venue-specific overrides that apply only when BOINC detects it's at that location. Venue
detection is based on the network the machine is connected to, configured in BOINC
Manager under `Advanced → Use network location`.

Venue-specific preferences take precedence over the base web preferences from the same
project. This is a common source of surprise: you may have set sensible base preferences
on all your projects, but a single project with a `home` venue override set to
`max_ncpus_pct=100` will silently override everything when BOINC decides it's at home.

---

## Layer 2: Local Override (`global_prefs_override.xml`)

The file at `/var/lib/boinc-client/global_prefs_override.xml` contains only the
preferences you explicitly want to override locally. Any preference not present in this
file falls through to the web preferences.

This file is what BOINC Manager writes when you change preferences via the GUI
(`Options → Computing Preferences`). It is not a complete preferences file — it only
contains the keys you've explicitly set.

**The override is not total.** If your override file sets `max_ncpus_pct=80` but the
web preferences (from a recently-synced project) include a `home` venue with
`max_ncpus_pct=100`, the venue-specific web preference wins for any key not present in
the override file. Only keys explicitly present in `global_prefs_override.xml` are
guaranteed to hold.

---

## The Failure Mode: Preference Drift

The typical failure scenario:

1. You set CPU limits via BOINC Manager GUI → writes `global_prefs_override.xml`
2. BOINC runs at your preferred limits — looks correct
3. BOINC scheduler contacts Project A to report completed tasks
4. Project A serves `global_prefs.xml` with a `home` venue set to `cpu_usage_limit=100`
5. Project A becomes the source project
6. BOINC now runs at 100% CPU — your GUI settings appear to have been ignored

This is not a bug. It is the documented behaviour of the source project mechanism
combined with venue-specific overrides. The GUI settings only win for keys that are
explicitly present in the override file **and** not overridden by a venue match.

---

## The Fix: Consistent Preferences Across All Projects

The only reliable solution is to ensure all attached projects serve identical preferences
with no venue-specific overrides.

**Procedure:**

1. Log into each project's website
2. Navigate to computing preferences (usually under your account settings)
3. Set identical values on every project — pay particular attention to:
   - `max_ncpus_pct` (% of CPUs to use)
   - `cpu_usage_limit` (% CPU time per core)
   - `work_buf_min_days` / `work_buf_additional_days` (work buffer)
   - `leave_apps_in_memory` 
4. **Remove any venue-specific overrides** (`home`, `work`, `school`) from all projects
5. In BOINC Manager, click "Update" on each project to force a sync of the new preferences
6. Verify `global_prefs.xml` reflects the expected values after each sync:
   ```bash
   grep -E "max_ncpus|cpu_usage_limit" /var/lib/boinc-client/global_prefs.xml
   ```

After this, any project becoming the source project will serve the same preferences, so
scheduler syncs no longer cause drift.

---

## Settled Values on pots

These are the preferences currently in use, set consistently across all attached projects:

| Preference | Value | Rationale |
|---|---|---|
| `max_ncpus_pct` | 100 | All cores available; affinity script manages actual distribution |
| `cpu_usage_limit` | 80 | 20% headroom for system responsiveness when user active |
| `niu_cpu_usage_limit` | 80 | Same limit applied when user not in use |
| `niu_max_ncpus_pct` | 100 | All cores available when not in use |
| `suspend_cpu_usage` | 25 | Suspend BOINC if non-BOINC CPU load exceeds 25% |
| `leave_apps_in_memory` | 0 | Tasks evicted from memory on preemption |
| `work_buf_min_days` | 0.75 | ~18 hours guaranteed work buffer |
| `work_buf_additional_days` | 0.5 | Additional 12 hours opportunistic buffer |
| `cpu_scheduling_period_minutes` | 35 | How long each task runs before BOINC considers preemption |
| `ram_max_used_busy_pct` | 50 | Cap RAM use at 50% (~15 GiB) when user active |
| `ram_max_used_idle_pct` | 85 | Cap RAM use at 85% (~26 GiB) when idle |
| `disk_max_used_gb` | 100 | Hard cap on BOINC disk usage |
| `disk_min_free_gb` | 200 | Always leave 200 GiB free (NVMe has large capacity) |
| `run_if_user_active` | 1 | Run CPU tasks regardless of user activity |
| `run_gpu_if_user_active` | 1 | Run GPU tasks regardless of user activity |
| Venue overrides | none | Removed from all projects to prevent drift |

---

## Diagnostic Commands

Check which project is currently the source:
```bash
grep "source_project\|master_url" /var/lib/boinc-client/global_prefs.xml | head -5
```

Check active CPU limits:
```bash
grep -E "max_ncpus|cpu_usage_limit|venue" /var/lib/boinc-client/global_prefs.xml
```

Check local override file:
```bash
cat /var/lib/boinc-client/global_prefs_override.xml
```

Force re-read of override file without restarting BOINC:
```bash
(cd /var/lib/boinc-client && boinccmd --read_global_prefs_override)
```

---

## Notes for Other Administrators

- If BOINC appears to ignore your GUI preference changes, the most likely cause is a
  venue-specific web preference from one of your projects winning over your local
  settings. Check `global_prefs.xml` for `<venue name="home">` blocks.

- Setting preferences on only one project is not sufficient if you have multiple projects
  attached. The source project changes on every scheduler contact.

- `global_prefs_override.xml` is the safest place to enforce hard limits — but only for
  keys you explicitly write there. Don't rely on it to contain venue drift unless you've
  audited what keys are actually present.

- BOINC Manager's "Computing Preferences" GUI writes a minimal override file. If you want
  a comprehensive override that wins unconditionally, edit `global_prefs_override.xml`
  directly and include every key you care about explicitly.
