# Permanent Control deploy toolkit installation

Preparation only. This page does not install the toolkit, contact
`hermes-control`, run preflight, or authorize Gate B. The copy-ready
Control VM commands below stay prohibited until a separate live-host
authorization names them.

The toolkit is a root-owned copy of the five `docs/deploy/` files from
git revision `30e64213d353a487fb84d84443449461b7a76944`. It is not the
running Control gateway checkout under `/opt/hermes-fleet-control/`.
This procedure does not change that checkout, its unit, or any other
application directory.

Installer: `docs/deploy/install-control-toolkit.sh`. It copies bytes.
It does not execute the toolkit scripts and does not import their
Python modules. Privileged steps are separate `sudo -n` invocations.
Do not use `sudo -i` or `su`.

## 1. Target

| Item | Value |
| --- | --- |
| Host FQDN | `hermes-control` (`hostname -f` and `hostnamectl --static`) |
| Login | `hermes@hermes-control` |
| Root | `sudo -n` from that login. `sudo -n id -u` is `0` |
| Toolkit root | `/opt/hermes-control-deploy` |
| Helper directory | `/opt/hermes-control-deploy/docs/deploy` |
| Helper parent | `/opt/hermes-control-deploy` |

`hostname -f` may consult DNS or `/etc/hosts`. A failure or any other
name is a STOP.

The operator has confirmed that this helper set was not found under
`/opt` or `/home/hermes`. Do not treat that as proof it is absent
everywhere. This procedure only creates or updates
`/opt/hermes-control-deploy`. It does not search for or delete other
copies.

## 2. Integrity manifest

These SHA-256 values are the file bytes at
`30e64213d353a487fb84d84443449461b7a76944`. The same lines are in
`docs/deploy/control-toolkit-manifest.sha256`. Two spaces separate
each hash from the bare filename.

```text
01f942746d15854cff87820339e0c34629d7c528fcc2c4fea19c16fe639c874e  c08cb1e-deploy-plan.md
5e7fe33d1496fcc905d7821083de79269502d91425fc3b11e94e258847b0a245  c08cb1e-guest-node-witness.sh
78634901d4e7c3335adf8f5c231503ddbc9322b13313178b0088f971e863cff7  c08cb1e-preflight.sh
fdfc8e27eb20cf9a038e8d60c6ea0c1f0c36195f5a0f55e5e00e332bfe42e854  c08cb1e-provisioner-witness.sh
2f54b671e58120178bfa7c84ee2d3d86c0e2df236911866b246450c9abaad60d  c08cb1e_material.py
```

Installed modes, owner `root:root`:

| Path | Mode |
| --- | --- |
| `/opt/hermes-control-deploy` | `755` |
| `/opt/hermes-control-deploy/docs` | `755` |
| `/opt/hermes-control-deploy/docs/deploy` | `755` |
| `c08cb1e-deploy-plan.md` | `644` |
| the four scripts, including `c08cb1e_material.py` | `755` |

Exact `755` on the scripts matches git mode `100755`. `700` and `750`
are not left in place when the bytes match; the installer chmods that
one file. A directory that is not mode `755`, or any path that is
group-writable or world-writable, is a STOP. The installer does not
chmod or chown `/`, `/opt`, or `/opt/hermes-fleet-control`.

## 3. Workstation, before any Control VM command

Run this on the operator workstation that already has this repository.
Do not clone or fetch on the Control VM. Do not use a credential in a
URL.

```bash
repo=$(pwd)
git rev-parse HEAD
git rev-parse 30e64213d353a487fb84d84443449461b7a76944
git diff --exit-code 30e64213d353a487fb84d84443449461b7a76944 -- docs/deploy/c08cb1e-deploy-plan.md docs/deploy/c08cb1e-guest-node-witness.sh docs/deploy/c08cb1e-preflight.sh docs/deploy/c08cb1e-provisioner-witness.sh docs/deploy/c08cb1e_material.py
```

`git diff` must be empty. `HEAD` is the toolkit commit that contains
this runbook. Record it. `$repo` must be that checkout.

```bash
work=$(mktemp -d)
chmod 700 "$work"
git -C "$repo" archive --format=tar 30e64213d353a487fb84d84443449461b7a76944 docs/deploy | tar -x -C "$work"
cd "$work/docs/deploy"
sha256sum -c "$repo/docs/deploy/control-toolkit-manifest.sha256"
sha256sum "$repo/docs/deploy/install-control-toolkit.sh" "$repo/docs/deploy/control-toolkit-manifest.sha256"
```

`sha256sum -c` must print `OK` for all five files. Record the installer
and manifest hashes. STOP if either command fails. Do not run the
extracted shell scripts.

The archive is the approved revision, not a branch tip and not a
downloaded archive from an unverified URL.

## 4. Transfer, separate live-host authorization

The Control VM is not assumed to have GitHub access. Transfer is plain
SSH as `hermes` to `hermes-control`. The operator's already trusted
host key is the trust assumption. Do not put a token in the command.
Do not transfer anything except the five verified files, the installer,
and the manifest.

On the Control VM, from the `hermes` shell, before the copy:

```bash
id -un
mkdir -m 0700 /home/hermes/hermes-control-deploy-staging
mkdir -m 0700 /home/hermes/hermes-control-deploy-staging/files
```

`id -un` must print `hermes`. The staging directories must be regular
directories, mode `700`, owned by `hermes`.

On the workstation, from `"$work/docs/deploy"`:

```bash
scp -p c08cb1e-deploy-plan.md c08cb1e-guest-node-witness.sh c08cb1e-preflight.sh c08cb1e-provisioner-witness.sh c08cb1e_material.py hermes@hermes-control:/home/hermes/hermes-control-deploy-staging/files/
scp -p "$repo/docs/deploy/install-control-toolkit.sh" "$repo/docs/deploy/control-toolkit-manifest.sha256" hermes@hermes-control:/home/hermes/hermes-control-deploy-staging/
```

These `scp` commands are not part of this preparation run.

## 5. Control VM installation

Operator shell: `hermes` on `hermes-control`. Each privileged command
is `sudo -n`. `sudo` may append an authentication log and may update
`/run/sudo/ts`. That is not Control deployment state. `sudo -n` uses
`env_reset`: it does not keep the caller's `PYTHONPATH`, `HOME`, or
other variables. The installer does not need those variables. `install
-m` and `mkdir -m` set modes explicitly, so the sudo umask does not
weaken them. `secure_path` does not matter because the installer calls
`mkdir`, `install`, `chown`, `chmod`, `stat`, `sha256sum`, and `ls`
by name after `PATH` is set below.

Confirm identity and host before any write under `/opt`:

```bash
id -un
sudo -n id -u
env PATH=/usr/sbin:/usr/bin:/sbin:/bin hostname -f
env PATH=/usr/sbin:/usr/bin:/sbin:/bin hostnamectl --static
```

Required results: `hermes`, `0`, `hermes-control`, `hermes-control`.
Any other result is a STOP.

Verify the transferred bytes before the installer runs:

```bash
cd /home/hermes/hermes-control-deploy-staging
sha256sum install-control-toolkit.sh control-toolkit-manifest.sha256
cd /home/hermes/hermes-control-deploy-staging/files
sha256sum -c /home/hermes/hermes-control-deploy-staging/control-toolkit-manifest.sha256
```

The installer and manifest hashes must match the workstation record.
All five `sha256sum -c` lines must be `OK`. STOP otherwise. Do not
execute the staged scripts.

Install:

```bash
env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C bash /home/hermes/hermes-control-deploy-staging/install-control-toolkit.sh --staging /home/hermes/hermes-control-deploy-staging/files --require-host hermes-control --require-user hermes
```

The installer checks the invoking user, `sudo -n id -u`, both host
names, the staging directory, and all five hashes again. It then
inspects every ancestor from `/opt` through `/`. It creates only
`/opt/hermes-control-deploy`, `docs`, and `docs/deploy` when those
paths are missing. It refuses a destination other than
`/opt/hermes-control-deploy`. It writes a file only when that path is
absent. An existing regular file is chmod'd or chown'd only after its
hash matches. `toolkit=ready` is printed only after a second hash,
owner, and mode check of all five installed files.

## 6. Expected result

```text
toolkit=ready
toolkit-action=created
toolkit-dest=/opt/hermes-control-deploy/docs/deploy
toolkit-class=state-changing
```

`toolkit-action` is `created` on a new directory, `completed` when
matching files were already present and missing files were added,
`modes-repaired` when every file was already present and only owner
or mode changed, and `unchanged` when a repeat run writes nothing.
All four are success only together with `toolkit=ready` and five
`toolkit-file=` lines whose hashes match section 2.

A repeat run that prints `toolkit-action=unchanged` does not replace
the files.

This result is state-changing. It is not read-only preflight and it
is not Gate B.

## 7. STOP conditions and recovery

STOP, and do not treat the directory as a trusted toolkit, when any
of these are true:

- `id -un` is not `hermes`, or `sudo -n id -u` is not `0`.
- `hostname -f` or `hostnamectl --static` is not exactly `hermes-control`.
- The installer or manifest hash differs from the workstation record.
- A staged file is missing, extra, a symlink, or the wrong hash.
- The staging directory is a symlink or is group-writable or world-writable.
- An ancestor of `/opt/hermes-control-deploy`, including `/opt` and `/`, is a symlink, is not owned by `root`, or is group-writable or world-writable.
- The toolkit path is a symlink, is not a directory, is not owned by `root`, or is not mode `755`.
- The toolkit directory contains any name other than the five files, including another `.py` or `__pycache__`.
- An installed file is a symlink or its hash does not match section 2.

Recovery:

- A STOP during staging or ancestor checks leaves `/opt` unchanged. Fix the staging copy or stop. Do not chmod `/opt`.
- A symlink is not removed by the installer. Removing it is a separate command. Do not follow it.
- An unexpected file is left in place. Move it aside only with a separate command that names that one file. Do not use a recursive delete.
- A hash mismatch on an installed file is left in place. The installer will not overwrite it. Replace that file only after a separate decision, then rerun section 5.
- A partial tree whose existing files match section 2, with no extra names, is completed by rerunning section 5. `toolkit=ready` is withheld until all five verify. A crash before that line is not a successful install.
- Do not run `chmod -R` or `chown -R`.

## 8. Gate B handoff

Do not run Gate B from this page. A successful install is the helper
copy Gate B's case A expects, at these paths:

- `HELPER_DIR=/opt/hermes-control-deploy/docs/deploy`
- `HELPER_PARENT=/opt/hermes-control-deploy`

The readiness sheet at `5cc58ddf535642de4ef0201abc38df11dbf31d66` on
`cursor/control-deploy-readiness-9cef` still says the operator shell
is root and the helper path is unresolved. This page does not edit
that sheet. A later edit of that sheet should record these
adjustments. Until that edit, a Gate B approval has to name them
explicitly.

1. Approved Control FQDN: `hermes-control`. Run both of these before any other host-specific check. `hostname -f` may consult DNS or `/etc/hosts`. A failure or a mismatch is a STOP.

```bash
env PATH=/usr/sbin:/usr/bin:/sbin:/bin hostname -f
env PATH=/usr/sbin:/usr/bin:/sbin:/bin hostnamectl --static
```

2. The operator shell is `hermes`, with `sudo -n` for root checks. Do not open a root shell. `sudo -n` may write an auth log and a timestamp file. It does not keep caller environment variables, so `env -i` stays inside the root command.

3. R2:

```bash
sudo -n sh -c 'ls -ld "/opt/hermes-control-deploy/docs/deploy" "/opt/hermes-control-deploy" && cd "/opt/hermes-control-deploy/docs/deploy" && ls -la'
```

4. R3:

```bash
sudo -n sh -c 'cd "/opt/hermes-control-deploy/docs/deploy" && stat -c "%U:%G %a %F %n" c08cb1e-deploy-plan.md c08cb1e-guest-node-witness.sh c08cb1e-preflight.sh c08cb1e-provisioner-witness.sh c08cb1e_material.py'
```

5. R4:

```bash
sudo -n sh -c 'cd "/opt/hermes-control-deploy/docs/deploy" && sha256sum c08cb1e-preflight.sh c08cb1e_material.py'
```

6. R5. `HELPER_DIR` is absolute, so the leading-`/` check passes. The walk still stops at `/`.

```bash
sudo -n sh -c 'd="/opt/hermes-control-deploy/docs/deploy"; case "$d" in /*) ;; *) echo STOP-not-absolute; exit 1;; esac; while :; do ls -ld "$d"; stat -c "%U:%G %a %F %n" "$d"; n=$(dirname "$d"); [ "$n" = "$d" ] && break; d=$n; done'
```

Directories are mode `755`, so a non-root deploying user can traverse them. A missing execute bit is a STOP. Do not chmod them to force a pass.

7. R6 when the deploying user is root:

```bash
sudo -n sh -c 'id -u; id -un; h=$(getent passwd "$(id -un)" | cut -d: -f6); echo "home=$h"; echo "HOME=$HOME"'
```

8. R7, unchanged except `sudo -n`:

```bash
sudo -n -u hermes sh -c 'id -un; XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user show -p LoadState --value hermes-gateway-control.service'
```

9. R8 root form. `PYTHONSAFEPATH=1`, `PYTHONDONTWRITEBYTECODE=1`, and `env -i` are unchanged. The sanitized environment is applied inside the root shell:

```bash
sudo -n sh -c 'cd "/opt/hermes-control-deploy" && env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 docs/deploy/c08cb1e-preflight.sh'
```

10. Optional O1 and O2, if a later approval names them:

```bash
sudo -n stat -c '%U:%G %a %F' /var/lib/hermes-control-deploy
```

```bash
sudo -n ls -l /home/hermes/.config/systemd/user/hermes-gateway-control.service /home/hermes/.config/systemd/user/hermes-gateway-control.service.d
```

The default-deny rule is unchanged: during Gate B, every command not
individually listed and approved in the Gate B command inventory is
prohibited. The install commands in this page are not that inventory.
`toolkit=ready` does not approve preflight, a witness, a deployment,
or a rollback.

Gate B still requires its own approval record, Fleet-idle assertion,
R6 `HOME` check, hermes user-manager visibility, and the STOP
conditions in the readiness sheet. Those are not satisfied by this
install.

## 9. Security properties

- Source bytes come from `git archive` of `30e64213d353a487fb84d84443449461b7a76944` on the workstation. The VM does not fetch them.
- Hashes are checked before install and again on the installed files. `toolkit=ready` follows the second check.
- Symlinks at the staging path, the destination, an ancestor, or a toolkit file are a STOP. The installer does not follow them.
- Staging must not be group-writable or world-writable, so another account cannot swap a file after the hash.
- No recursive chmod or chown. `/opt` and the gateway checkout are only inspected.
- A wrong installed hash is not overwritten.
- The installer never executes `c08cb1e-preflight.sh`, the witnesses, or `c08cb1e_material.py`.
- No new credential is stored. SSH uses the existing `hermes` login.
- `sudo -n` can write log and timestamp files. It does not change the gateway unit.
