# Hermes Fleet handoff — 2026-10-16

Written from Cloud Agent run `bc-8a301a9b-4d01-4691-9e15-00f380949cef` before work moves to the Cursor environment **Hermes-Fleet-Agent-Buzz-Knowledge**. That environment is expected to contain `bitcoinchiggy/buzz`, `bitcoinchiggy/hermes-agent`, `bitcoinchiggy/hermes-fleet`, `bitcoinchiggy/hermes-fleet-control`, and `greatergoodco/knowledge`. This workspace did not contain `greatergoodco/knowledge`. Its role, default branch, and SHA are **unverified**.

This file does not authorize a deploy, a merge, a host contact, or another validation run. Live host state below is pasted observation, not a fresh check.

## 1. Per repo

Checked out state when this handoff was written. No unique unpushed commits in any of the four repos. Local `main` refs in Control and Buzz are stale pointers; do not “fix” them by moving a checkout unless asked.

| Repo | Checked-out ref | SHA | Pushed? |
|---|---|---|---|
| `bitcoinchiggy/hermes-fleet-control` | was `cursor/control-retire-worker-9cef`; this file is `cursor/handoff-export-9cef` | retirement head `5868856f569edfa9c46361ec0944997f8fd42dd4`, already an ancestor of `origin/main` `c08cb1ebd073ee7946f49005dd45071366eeb688` | retirement branch yes; this handoff branch is the commit that adds this file |
| `bitcoinchiggy/hermes-fleet` | `cursor/control-onboard-check-9cef` | `3b347236158cc65600b7d0697dcbdac58b915024` | yes, matches `origin/cursor/control-onboard-check-9cef` |
| `bitcoinchiggy/hermes-agent` | `cursor/fleet-coordination-channel-9cef` | `46762a638c4639fbd3dd3ba963141f1f6ac22666` | yes, matches its origin branch |
| `bitcoinchiggy/buzz` | detached `HEAD` | `12d37f5e2e21303bf42e1249afd25c08b67564c1` | yes; this SHA is `origin/main` |

Default-branch tips fetched 2026-10-16:

| Repo | Default branch | SHA | Subject |
|---|---|---|---|
| hermes-fleet-control | `main` | `c08cb1ebd073ee7946f49005dd45071366eeb688` | Merge pull request #7 |
| hermes-fleet | `main` | `b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb` | Merge pull request #91 |
| hermes-agent | `main` | `b3e4fb8aa89a8b839245392e2d896688c384a27d` | plugin-catalog pin; not the deployed fork |
| hermes-agent | `fleet` (deployed pin) | `e29f306cdbc7728f297d218be6ecda511bcf450a` | Route Fleet intake and coordination config through their owners |
| buzz | `main` | `12d37f5e2e21303bf42e1249afd25c08b67564c1` | Merge pull request #3 |

`origin/main` of Control has parents `06a124f1ebda71bd6341ec5fbd7b872f3318ad03` and `5868856f569edfa9c46361ec0944997f8fd42dd4`. Its tree equals `5868856`. Committer time `2026-10-16T11:05:38-07:00`. GitHub `mergedAt` for PR #7 is `2026-10-16T18:05:39Z`.

Stale local pointers, not unique work:

- Control local `main` is `bd560a230f355662289ceb905d00251535134476`, 13 behind `origin/main`.
- Buzz local `main` is `f2559a8c`, 4 behind `origin/main`.
- Fleet local `cursor/exec-status-exited-numeric-9cef` tracks `origin/main` and is behind 50.
- Hermes local `cursor/fleet-hermes-integration-9cef` at `ef0dcd277cf88f3f9055fe181472ac6b28683e77` shows upstream `[gone]`. That commit is already an ancestor of `origin/fleet`. Worktrees `/tmp/hermes-integration` (same commit, clean) and `/tmp/hermes-parent-ef0dcd27` (detached, clean) are the same commit.

## 2. Work status

### Merged

- Control onboarding, PR #6, merge `06a124f1ebda71bd6341ec5fbd7b872f3318ad03` at `2026-10-15T22:55:42Z`. Branch tip remains `5e8e72b347052e8b76c4fb9cb8ab49475af8c5d2`.
- Control retirement, PR #7, merge `c08cb1ebd073ee7946f49005dd45071366eeb688`. Production code is `63099c4a1f38063d2c0068fa40b94baf74bfb092`. The only change from that commit to `5868856` is `docs/control-onboard-validation.md`.
- Fleet worker onboarding, PR #91, `b7f4a114ee2ef35b4ff0f1a2abd15efb248576fb`, merged `2026-10-14T04:03:35Z`. It does not declare `control-onboard-check`.
- Buzz recorded-owner read, PR #3, current `origin/main`.
- Hermes Fleet coordination intake on branch `fleet` at `e29f306cdbc7728f297d218be6ecda511bcf450a`. Unpatched `7817bf522af3caf54b30ae59f16157469d7638fc` does not call the intake.

### Pushed, unmerged

Open draft PRs in section 3. Many older `cursor/*-9cef` branches are also on the Fleet remote. They are historical review branches, not a second copy of uncommitted work. Empty `git log --branches --not --remotes` on all four repos.

### Local only — do not push

`/tmp/hermes-clean` is a detached Hermes worktree at `7817bf522af3caf54b30ae59f16157469d7638fc` with a staged index of 13 files: `gateway/buzz_recovery_quarantine.py`, `gateway/delivery_ledger.py`, `gateway/fleet_delegation.py`, `gateway/platforms/base.py`, `gateway/platforms/event.py`, `gateway/run_shutdown.py`, `gateway/run_startup.py`, `gateway/run_turn.py`, `plugins/platforms/buzz/adapter.py`, `tests/gateway/test_delivery_ledger.py`, `tests/gateway/test_fleet_delegation_handoff.py`, `tests/gateway/test_worker_reply_attribution.py`, `tools/mcp_tool_handlers.py`. Against `origin/fleet` that index mostly deletes later coordination and quarantine code. Publishing it would look like a branch that removes shipped work. Leave it unpushed.

No secrets were found in that index. A earlier `sk-` string hit was the substring inside `task-{chat_id}`.

### Fixture-tested vs live-tested

- Control unit tests were last reported as `python3 -m unittest discover -s tests -p 'test_*.py'` — 145 passed at `63099c4`. Not re-run on this handoff turn. The merged tree matches `5868856`, which changes only the validation doc, so the count should still apply. **Unverified** today.
- `node --check` on `fleet-mcp/index.js` and `python-bin.js` passed at the retirement implementation head. Not re-run today. **Unverified** today.
- Fleet PR #93 is expected to fail two canonical inventory tests in `tests/test_fleet_provisioner.py` (`CanonicalRepoDeclarationTests`). That failure is intentional. A full Fleet suite count at `b7f4a11` was not re-measured.
- Live onboarding and retirement of `control-onboard-check` are pasted in `docs/control-onboard-validation.md`. They are not an independent host check from this agent. VM 1037 is gone. Do not recreate it.

### Implemented vs proposed

Implemented in git, and exercised once as a pasted live run:

- MCP server name `hermes-fleet-control` in `fleet-mcp/index.js`. Tools: `worker_status`, `ensure_worker`, `onboard_worker`, `retire_worker`, `delegate_worker`.
- Helpers: `fleet-status`, `fleet-ensure`, `fleet-onboard`, `fleet-retire`, `fleet-delegate`, `fleet-delegation-intake`, `fleet-delegation-show`. Operator-only `fleet-allow-inbound` is not an MCP tool.
- Onboard: reservation before one `POST`; later calls `GET` only; no identity generation; no automatic delegate. `ensure` does not open an onboarding journal. A journal that exists requires status `complete` before delegation. Workers with no onboarding journal keep the older delegation checks. Public refusals include `onboarding_retired`, `tombstone_present`, `existing_worker`. Never automatically retry an ambiguous mutation.
- Retire: bind name, node, vmid, git SHA, public key hex, and onboarding id. Missing or malformed identity is `retire_identity_unbound` before POST. Default does not authorize retained workers. `confirm_retained` and `retry` both true is `retire_request_invalid` and does not POST. `retry: true` posts only after a refused retryable outcome for the same identity (`reconciliation_in_progress`, `rename_in_progress`, `coordination_retirement_refused`, `fleet_unauthorized`). `retained_worker` is not retryable. Reserved or ambiguous while still live raises `retire_ambiguous` and does not POST again. Terminal absent or tombstone reports completion with no second POST. Control does not itself remove coordination membership. Retirement does not delete onboarding reservations, delegation journals, provisioner journals, or tombstones.

Proposed, not implemented:

- Automatic completion notifications.
- Placing the delegation result in the originating thread. The live result arrived as a separate DM. `relay_accepted` is relay acceptance, not worker execution or task completion. Journal `completed` means the model is not run again; it does not prove the human received the message. Another turn’s success does not complete the handoff.

Merged in git, deployment **unverified** and not authorized by this handoff:

- Control `c08cb1e` (onboarding + retirement). The last pasted live Control checkout, after the retirement test and before PRs #6 and #7 merged, was `dcb3f950b142ef0a4dbd355ca7426b0172aa7d7a`, PID 452497, active, zero restarts.
- Fleet was restored to `b7f4a11`, PID 1092874, active, zero restarts, in that same pasted note. Those PIDs were not rechecked.

## 3. Open PRs

| PR | Keep unmerged? | What it needs |
|---|---|---|
| [hermes-fleet #93](https://github.com/bitcoinchiggy/hermes-fleet/pull/93) draft, `cursor/control-onboard-check-9cef` @ `3b347236158cc65600b7d0697dcbdac58b915024` | Yes | Disposable declaration only (`workers/control-onboard-check.yaml`, role researcher, `retained: false`). Two canonical inventory tests fail on purpose. The worker was already onboarded and retired. Merging would add a disposable name to stable inventory. |
| [hermes-fleet #92](https://github.com/bitcoinchiggy/hermes-fleet/pull/92) draft, `cursor/auto-onboard-test-9cef` @ `9d138cf5260eb03902922aad1914dfc6766a5029`, base `cursor/worker-onboarding-9cef` | Yes | Pasted `onboard-retire-test` observation and a temporary declaration. Base branch is already merged via #91. Do not merge into `main`. |
| [hermes-fleet #87](https://github.com/bitcoinchiggy/hermes-fleet/pull/87) draft, `cursor/revision-test-validation-9cef` @ `5310ea73f6049fa86b13f85240e60e7f7bb393e6` | Yes | Record of `revision-test-2`. Not a standing worker change. |
| [hermes-fleet #25](https://github.com/bitcoinchiggy/hermes-fleet/pull/25) draft, `cursor/vlan1-mgmt-caddy-dns-410c` @ `8760468e05e2fd15d090544cb6c619a300d2c9f2` | Undecided | VLAN 1 / Caddy DNS docs. Not part of Control onboarding. No merge decision in this chat. |
| [buzz #2](https://github.com/bitcoinchiggy/buzz/pull/2) draft @ `a7d0aa9d3e814211ae77657e23169c2ae008ee28` | Undecided | Cloud Agent setup notes. Not part of Control work. |
| [buzz #4](https://github.com/bitcoinchiggy/buzz/pull/4) draft @ `c41464103f01dc13a45bbf460cc6aa0eb458f668` | Undecided | Cloud Agent toolchain and relay setup notes. Not reviewed for merge here. |

Control has no open PRs. Hermes-agent has no open PRs. Do not open another retirement PR. `5868856` is already in `main`.

## 4. Open questions, bugs, causes

### Confirmed

- `relay_accepted` and journal `completed` do not mean the human has the message.
- Completion notifications and originating-thread placement are absent. The onboard-check result arrived as a separate DM.
- Unpatched Hermes `7817bf522af3caf54b30ae59f16157469d7638fc` does not call `fleet-delegation-intake`.
- GitHub access is split across connections. Do not collapse this into “GitHub works” or “GitHub is missing.”
  - Cursor `ManagePullRequest` created Control PR #6 as author `bitcoinchiggy`, and later identical creates returned HTTP 422 `{"resource":"Issue","code":"custom","message":"must be a collaborator"}` with no `field` and no GitHub request id. Latest identical retirement create: event `49a4afff-c8ec-11f1-ba43-82e1a43c1b77` at `2026-10-15T23:00:59.844Z`. A follow-up list found no PR. That 422 does not prove who was authenticated and does not prove `bitcoinchiggy` lacks access.
  - The GitHub App installation token (`gh` user `cursor`, GraphQL viewer `cursor[bot]`, git username `x-access-token`) pushed branches, listed and read PRs, marked PR #6 ready via GraphQL `markPullRequestReadyForReview` at `2026-10-15T22:55:29.401Z`, and merged PR #6 at `2026-10-15T22:55:42Z` (`merged_by` `cursor[bot]`). The same token’s `createPullRequest` / `POST /repos/bitcoinchiggy/hermes-fleet-control/pulls` returned 403 `Resource not accessible by integration`. REST ready-for-review on PR #6 returned 404 before the GraphQL success.
  - Repo `permissions` booleans (admin/maintain/pull/push/triage false, `role_name` null, `viewerPermission` null) contradict demonstrated reads, pushes, ready, and merge. `X-Accepted-Github-Permissions: pull_requests=write` on a failed create means the route requires that permission, not that the token has it.
  - Direct SSH has no keys (`Permission denied (publickey)`). Git SSH URLs are rewritten to HTTPS before connecting. No signed-in GitHub browser session was present (Chrome profile had no cookie DB; logged-out public Control page; private Fleet fetch 404).
- PR #7 was created and merged outside this agent. This agent did not create or merge it. Grok owned that review. Head `5868856` matches `main`’s tree.
- This Cloud Agent environment (`6ad7bacf-c051-11f1-bb68-864e54d14197`) reported `no_finished_builds` and `defaultImageFallback: true`. Draft build ids were started and then unreadable: `list-environment-builds` returned that this run’s principal cannot read builds for that environment; logs for `bld-20261016-229d1549-0706-44ef-8953-ac24e15a299b` returned not found (or not a build of this run’s environment and principal). A new environment created in the dashboard was not attached to this running agent.

### Hypothesis only

- The Cursor create 422 is GitHub validating a hidden Issue field (assignee or reviewer) that the agent schema cannot set, or an intermittent validation on a path that also succeeds. Left unresolved on purpose. Do not repeat that create.
- Fleet PR #93’s body edit at `2026-10-15T16:55:43Z` (GraphQL editor login `cursor`, author `bitcoinchiggy`, no `gh pr edit` in that minute) may be Cursor’s automatic body wrap. Not established.

### Known product gaps

- No automatic “your worker is ready” message.
- Delegation results are not placed back in the originating thread.
- Coordination-membership removal during deprovision is a different mechanism from Buzz relay membership. ADR 007: deprovision does not DELETE relay membership. Do not conflate them.

## 5. Environment setup

### This chat’s computer

Personal dashboard environment `6ad7bacf-c051-11f1-bb68-864e54d14197`, version `e319b83d-c056-11f1-bb68-864e54d14197`. Repos were already at `/agent/repos/{buzz,hermes-agent,hermes-fleet,hermes-fleet-control}`. Egress was unrestricted. There is no `.cursor/environment.json` in these repos; config is database-managed and was not exposed to this principal. Install was skipped (`defaultImageFallback: true`). No ports were served by this handoff. No host was contacted.

The newest draft build on that old environment (`bld-20261016-229d1549-0706-44ef-8953-ac24e15a299b`) only checks that four repo directories exist. Do not activate it. Activation would save that check over the hidden setup. The direct dashboard URL pattern `…/cloud-agents/builds/<buildId>` 404’d. The environment page is `https://cursor.com/dashboard/cloud-agents/environments/e/6ad7bacf-c051-11f1-bb68-864e54d14197`.

The next agent should be started in **Hermes-Fleet-Agent-Buzz-Knowledge**, not by expecting this chat’s machine to change.

### Control checks (local, no host)

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
cd fleet-mcp && npm ci --ignore-scripts --no-audit --no-fund && node --check index.js && node --check python-bin.js
```

Runtime install, only inside the checkout that should run, and only when a reviewed install is authorized:

```bash
python3 install-control-runtime --python /usr/bin/python3.12
```

That prints `<checkout>/runtime/venv/bin/python`. Locked: `cryptography==50.0.2`, `PyYAML==6.0.2`, `cffi==2.1.1`, `pycparser==3.0`. Do not use the Hermes agent virtualenv. Do not set `FLEET_CONTROL_PYTHON` to the system Hermes `python3` or to that agent venv.

### Production layout (sample and docs, not a live probe)

- Sample unit `hermes-fleet/deploy/hermes-fleet-provisioner.service`. Do not enable it from git.
- Checkout path in the sample: `/opt/hermes-fleet`. `EnvironmentFile=/etc/hermes-fleet/api.env`. Port `8443`. `FLEET_PROVISIONER_GIT_REF` default `refs/heads/main`. The provisioner reads `workers/<name>.yaml` with `git show` at the resolved SHA and does not fetch.
- `EnvironmentFile=` can override `Environment=`. A temporary git-ref override must be a guarded `ExecStart` prefix, not an assumption that `Environment=` wins.
- Non-loopback listen uses `FLEET_PROVISIONER_TLS_CERT` and `FLEET_PROVISIONER_TLS_KEY`. TLS uses the host trust store. No `curl -k`.
- A Control drop-in that points MCP at a new checkout must sort after `fleet-delegation.conf` (example name `fleet-retirement.conf`). Do not edit `fleet-delegation.conf`.
- `HERMES_FLEET_MCP_SERVER` is the server name. The script path is `mcp_servers.<name>` in Hermes config. `HERMES_FLEET_CONTROL_ROOT` is where the intake binary lives.
- Journals, when no absolute override is set: `<profiles root>/<profile>/fleet-onboarding`, `fleet-retirements`, `fleet-delegations`. README cites `/home/hermes/.hermes/profiles/<profile>/fleet-delegations/unavailable-holds`. Mode 0600 files, 0700 directories.
- Routes: `GET /v1/workers`, `GET /v1/workers/{name}`, `PUT /v1/workers/{name}/ensure` with `{}`, `POST /v1/workers/{name}/onboard` with `{}`, `POST /v1/workers/{name}/deprovision` with `{}` or exactly `{"confirm_retained": true}`.

## 6. Secret and credential names

Names only. Values were not copied into this file.

| Name | Where it is expected | Used by this handoff? |
|---|---|---|
| GitHub App installation token (category `ghs_`) | `~/.config/gh/hosts.yml` and git `insteadOf` rewrites of `https://github.com/`, `git@github.com:`, and GitHub SSH URLs on this cloud VM | Yes, for fetch, push, and read-only `gh`. This VM must not be snapshotted. |
| `BUZZ_PRIVATE_KEY` | Hermes profile env, not git. Buzz child receives it with `PATH`, `BUZZ_RELAY_URL`, optional `BUZZ_AUTH_TAG`, and safe locale variables | Not read |
| `BUZZ_RELAY_URL`, `BUZZ_AUTH_TAG` | Same profile env | Not read |
| `BUZZ_FLEET_MEMBERSHIP_TOKEN`, `BUZZ_FLEET_MEMBERSHIP_API_URL` | `/etc/hermes-fleet/api.env` on the provisioner host only | Not read |
| `BUZZ_ALLOWED_USERS` | The one profile bound to the active gateway; `fleet-allow-inbound` rewrites only this and keeps existing human keys | Not read |
| `FLEET_PROVISIONER_CALLER_TOKEN` | `/etc/hermes-fleet/api.env` (mode 0600). Sent as the Fleet Authorization header, not to the Buzz child | Not read |
| `FLEET_PROVISIONER_STATE_DIR` | Same file. Sample value in `deploy/api.env.example` is `/var/lib/hermes-fleet`. Required; do not guess from a directory on disk | Not read |
| `PVE_API_URL`, `PVE_TOKEN_ID`, `PVE_TOKEN_SECRET`, optional `PVE_NODE`, optional `PVE_CA_CERT` | `/etc/hermes-fleet/proxmox.env`. Override path `HERMES_PROXMOX_ENV` | Not read |
| `LITELLM_MASTER_KEY` | `/etc/hermes-fleet/litellm.env`. Override path `HERMES_LITELLM_ENV`. Do not put it in `api.env` | Not read |
| `FLEET_PROVISIONER_TLS_CERT`, `FLEET_PROVISIONER_TLS_KEY` | `/etc/hermes-fleet/tls.crt` and `tls.key` when listen is not loopback | Not read |
| Caddy DNS token file | `/etc/caddy/cloudflare.env` (ADR 005). Exact variable names inside that file were not opened | Not read |
| Buzz CLI GitHub token file | Docs/tests name `/etc/hermes-fleet/buzz-cli-github.token` | Not read |
| `FLEET_ONBOARD_JOURNAL_DIR`, `FLEET_RETIRE_JOURNAL_DIR`, `FLEET_DELEGATION_JOURNAL_DIR` | Optional absolute overrides. Otherwise the profile directories in section 5 | Not set |
| `FLEET_CONTROL_PYTHON`, `FLEET_CONTROL_HERMES_PROFILE`, `FLEET_CONTROL_PROFILES_ROOT`, `FLEET_CONTROL_BUZZ_BIN`, `HERMES_FLEET_CONTROL_ROOT`, `HERMES_FLEET_CONTROL_INTEGRATION`, `HERMES_FLEET_MCP_SERVER` | Control/Hermes process environment | Not set on a host |
| `FLEET_PROVISIONER_URL`, `FLEET_PROVISIONER_REPO`, `FLEET_PROVISIONER_GIT_REF`, `FLEET_PROVISIONER_ENV_FILE`, `FLEET_PROVISIONER_LISTEN_HOST`, `FLEET_PROVISIONER_LISTEN_PORT`, `FLEET_PROVISIONER_LISTEN_NETWORK` | Provisioner process / sample unit | Not set on a host |

Directory `/etc/hermes-fleet/` is `root:root`, mode `0700`, on the provisioner. Nothing under it belongs in git.

## 7. Decisions, conventions, and prohibitions

Decisions already recorded in `hermes-fleet/decisions/`:

- ADR 002: INFRA control plane is separate from AI execution.
- ADR 005: git is source of truth; secrets stay off git.
- ADR 007: Buzz relay membership depends on the `bitcoinchiggy/buzz` fork. Deprovision does not DELETE that membership.

Agreed in this work:

- Hermes pin stays `e29f306cdbc7728f297d218be6ecda511bcf450a` on branch `fleet` until a later message changes it.
- Prefer Nostr events over new HTTP endpoints on Buzz. Fleet/Control operations stay on the provisioner routes and the MCP tools above.
- One user action is one POST. A later call reads status. Ambiguous mutations are not retried.
- `ensure_worker` is not onboarding. Onboarding does not delegate.
- Retire binds node as well as VM, provenance, public key, and onboarding id.
- Disposable worker names are not stable inventory: `control-onboard-check`, `auto-onboard-test`, `onboard-retire-test`, `lifecycle-test`, `revision-test`, `revision-test-2`, `onboarding-test`.
- Operator and Researcher stay. Template 1000 stays.
- Commits use `git commit -s` and `Co-authored-by: bitcoinchiggy <bitcoinchiggy@users.noreply.github.com>`. No force-push.
- Do not infer a GitHub actor from commit authorship or from the account shown in Cursor Settings. HTTP 422 `must be a collaborator` is not proof the authenticated account lacks access. Do not ask to reconnect or change permissions unless evidence names the connection and the missing requirement.
- Cursor `update_pr` with `draft: true` fails on GitHub; omit `draft` to leave a draft unchanged. `draft: false` marks ready. The tool has no merge action and no assignee/reviewer fields.
- Public event-feed actor `bitcoinchiggy` on a merged PR is not the merge caller when `merged_by` is `cursor[bot]`.

Do not:

- Merge, deploy, contact a host, mint or revoke keys, restore live keys, restart the provisioner, resend a delegation, send a message, create a worker, or rerun injection unless a later message explicitly authorizes that specific action.
- Modify live configuration, existing workers, template 1000, backups, or tombstones.
- Remove proof VMs that still exist. Do not recreate deleted proof assets 1003, 1004, 1008, or VM 1037.
- Push `/tmp/hermes-clean` or edit `cursor/control-retire-worker-9cef` (already merged).
- Edit `fleet-delegation.conf`. Use a later-sorting drop-in when a reviewed checkout switch is authorized.
- Disable TLS verification.
- Snapshot this cloud VM or bake the installation token into an environment image.
- Treat a green unit test as a live deploy check.

## 8. Recommended next steps

1. Start the fresh agent in **Hermes-Fleet-Agent-Buzz-Knowledge** and confirm `greatergoodco/knowledge` is actually checked out. Its contents are **unverified** here.
2. Read this file, Control `README.md`, `docs/control-onboard-validation.md`, and Fleet ADRs 002, 005, and 007 before changing behavior.
3. Leave Fleet PRs #93, #92, and #87 unmerged. Leave #25, Buzz #2, and Buzz #4 until someone decides they are in scope.
4. Do not deploy Control `c08cb1e`. The last pasted running Control revision is the pre-merge checkout `dcb3f95`. Whether that PID is still the process is **unverified**.
5. When product work resumes, the unimplemented gap is completion notification plus originating-thread placement. `relay_accepted` and journal `completed` stay narrower than “the human has the message.”
6. Keep the Hermes pin at `e29f306` on `fleet` until a message changes it. Do not ship the `/tmp/hermes-clean` index.
7. Do not repeat the Cursor retirement `create_pr` that returned 422 at `2026-10-15T23:00:59.844Z`, and do not open a second retirement PR.
