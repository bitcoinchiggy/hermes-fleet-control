# Control onboarding validation

Pasted observation. This page does not contact a host, create a worker,
send a retirement request, or change a service.

## Observed run

Temporary Fleet declaration commit
`3b347236158cc65600b7d0697dcbdac58b915024` was active for the run.
Stable Fleet does not declare `control-onboard-check`.

One Control `onboard_worker` call accepted `control-onboard-check`.
The onboarding id was `onb_babe424e1dd049f19dd0a80bd9bcc476`. The
reconciliation id was `rec_7cc6bce10e384798aa63799a9d5cc8c0`. Acceptance
was `2026-10-15T18:14:19Z`. The same journal completed automatically at
`2026-10-15T18:29:36Z`. No second onboard call was used to finish it.

The worker was Blue VM 1037, public key
`c2696ef2302c41c1dc288ffbac9ff82622df299c80a62d55d3c2ee1b2c0dd34b`,
generation 1 alias `control-onboard-check-g1`.

Delegation `dlg_e70c005e56f7226911b578b0666c86a3` returned the exact
marker `FLEET-CONTROL-ONBOARD-CHECK-20261015-01`. The task text was
`Reply exactly: FLEET-CONTROL-ONBOARD-CHECK-20261015-01`. The Control
journal showed one completed originating-DM delivery in 10 seconds.
The result arrived as a separate DM message. No automatic
onboarding-completion notification was implemented. Reply-thread
placement of that result is not implemented either. Both are follow-up
work, not part of the retirement helper.

Installing the Control checkout did not install Node dependencies.
`npm ci --ignore-scripts --no-audit --no-fund` in that checkout's
`fleet-mcp` directory made the tools available. The temporary Control
drop-in had to use a name that sorts after `fleet-delegation.conf`.

Both services were restored. Stable Fleet remains
`b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb`. Stable Control remains
`dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a`. VM 1037 was deliberately
kept for a later retirement test. Its identity, complete onboarding
journal, and generation 1 alias remain. No retirement request was
sent. Existing agents, inventory, journals, and tombstones were
preserved.

## Proposed retirement validation

This section is not authorization to run. Stable Fleet still does not
declare this worker, so the reviewed declaration commit
`3b347236158cc65600b7d0697dcbdac58b915024` has to be the provisioner's
effective `FLEET_PROVISIONER_GIT_REF` again before `retire_worker` is
called. A call against stable `main` is not a valid trial of this name.

Before any change, capture the running provisioner's effective
repository, git ref, state directory, and `ExecStart` from the process
environment, not only from unit files. Save `git status --porcelain`.
The baseline includes the preserved untracked `tls-backend.new.crt`.
Later porcelain must match that capture. Leave that file in place.
Fetch the declaration commit into the existing checkout and keep
`refs/heads/main` at the stable Fleet revision. The process stays on
that checkout. A temporary `ExecStart` prefixes
`/usr/bin/env FLEET_PROVISIONER_GIT_REF=3b347236158cc65600b7d0697dcbdac58b915024`
to the captured command. After restart, the process environment must
show that ref.

Install the reviewed retirement revision beside stable Control
`dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a`. In that checkout only, run
`python3 install-control-runtime --python /usr/bin/python3.12` after
confirming the binary. That creates `runtime/venv` in the new checkout
and prints `<checkout>/runtime/venv/bin/python`. Do not point the
gateway at the stable checkout or at a Hermes agent virtualenv, and do
not set `FLEET_CONTROL_PYTHON` to either of those. Then, in that
checkout's `fleet-mcp` directory, run
`npm ci --ignore-scripts --no-audit --no-fund`. That installs
`package-lock.json`. Do not run `npm install`. Identify the active MCP
`command`, `args`, and `cwd` from the profile `config.yaml` loaded by
the running gateway, and `HERMES_FLEET_CONTROL_ROOT` from the process
when it is set. Change only those path values. Add one drop-in whose
name sorts after `fleet-delegation.conf`, for example
`fleet-retirement.conf`. Do not edit `fleet-delegation.conf`. Capture
`DropInPaths` before adding it. Leave the profile, credentials,
delegation journals, and onboarding reservations in place.

Preflight with that checkout's `fleet-status` against the host trust
store. `researcher` must return a public document.
`control-onboard-check` must show the same VM 1037, public key,
onboarding id, and generation 1 alias, with `retained` false. Record
`observed.node` from that document. It has to be present; the
reservation binds that node with the name, VM, provenance, public key,
and onboarding id. Stop if the client reports `fleet_unreachable`.

Call `retire_worker` once with only the name. The body is `{}`. Do not
pass `confirm_retained`. Use named `worker_status` afterward. One
provisioner deprovision is enough. The result must keep the onboarding
id and public key, retire that journal, leave its tombstone, remove
the VM and both aliases, and remove coordination membership. Control's
onboarding reservation and the delegation journal stay. A later
`retire_worker` call reports status and does not send again.

`retry` is not part of the first attempt. It does not send again while
the attempt is reserved or ambiguous. It sends only after a refused
retryable outcome and only when that same node, VM, provenance, public
key, and onboarding id are still present. An absent or tombstone view
reports completion and does not send.

Rollback changes only the validation settings. Remove the new drop-in
and leave `fleet-delegation.conf` as captured. Restore the captured
MCP `command`, `args`, `cwd`, and `HERMES_FLEET_CONTROL_ROOT` strings.
Restore the captured provisioner `ExecStart`. If
`FLEET_PROVISIONER_GIT_REF` was absent before the prefix, require it
to be absent again. Restart only the provisioner and the one Control
gateway. Porcelain, including `tls-backend.new.crt`, matches the
baseline. Stable Fleet and stable Control match the revisions above.
Template 1000, existing agents, retained backups, and the preflight
inventory stay. The new tombstone, the retired onboarding journal, the
Control onboarding reservation, and the delegation journal stay.
