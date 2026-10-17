#!/bin/bash
# Guest-node VM inventory. This is a host mutation, not a read-only
# diagnostic. It does not start, stop, or destroy a guest.
#
# Every run, as root:
# - creates /var/lib/hermes-control-deploy/c08cb1e-guest-node-witness
#   if missing, then sets that directory to mode 0700
# - creates or truncates lock in that directory and takes a non-blocking flock
# - replaces qm-now.txt with VMID and status rows from `qm list`
# The first run copies qm-now.txt to qm-baseline.txt and sets mode 0600.
# Later runs compare the two files and do not replace the baseline.
# lock and qm-now.txt keep the shell redirection mode (umask). The
# directory mode keeps them private to root.
set -euo pipefail
echo "host-role=guest-node hostname=$(hostname -s)"
echo "host-mutation=yes"
echo "read-only=no"
test "$(id -u)" -eq 0
command -v qm >/dev/null
test -d /etc/pve
if [[ "$(systemctl show -p LoadState --value hermes-gateway-control.service 2>/dev/null || true)" == "loaded" ]]; then
  echo "STOP: hermes-gateway-control.service is loaded on this host" >&2
  exit 1
fi
EVIDENCE=/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness
echo "mutation-dir=$EVIDENCE mode=0700"
echo "mutation-file=$EVIDENCE/lock action=create-or-truncate"
echo "mutation-file=$EVIDENCE/qm-now.txt action=replace"
echo "mutation-file=$EVIDENCE/qm-baseline.txt action=create-once-then-compare mode=0600"
echo "guests=not-started-stopped-or-destroyed"
mkdir -p -- "$EVIDENCE"
chmod 700 -- "$EVIDENCE"
exec 9>"$EVIDENCE/lock"
flock -n 9
qm list | awk 'NR > 1 && $1 ~ /^[0-9]+$/ {
  status = ""
  for (i = 1; i <= NF; i++) if ($i ~ /^(running|stopped|paused)$/) status = $i
  if (status != "") print $1, status
}' | sort > "$EVIDENCE/qm-now.txt"
if [[ ! -s "$EVIDENCE/qm-now.txt" ]]; then
  echo "STOP: qm list produced no VMID/status rows" >&2
  exit 1
fi
if [[ ! -f "$EVIDENCE/qm-baseline.txt" ]]; then
  cp -- "$EVIDENCE/qm-now.txt" "$EVIDENCE/qm-baseline.txt"
  chmod 600 -- "$EVIDENCE/qm-baseline.txt"
  echo "baseline=created lines=$(wc -l < "$EVIDENCE/qm-baseline.txt")"
else
  cmp -s -- "$EVIDENCE/qm-now.txt" "$EVIDENCE/qm-baseline.txt"
  echo "baseline=matched lines=$(wc -l < "$EVIDENCE/qm-baseline.txt")"
fi
echo "GUEST-NODE OK"
