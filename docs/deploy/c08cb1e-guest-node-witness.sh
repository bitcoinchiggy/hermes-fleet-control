#!/bin/bash
# Guest-node VM inventory. The host is the one where qm and /etc/pve
# are present. Does not start, stop, or destroy a guest.
set -euo pipefail
echo "host-role=guest-node hostname=$(hostname -s)"
test "$(id -u)" -eq 0
command -v qm >/dev/null
test -d /etc/pve
if [[ "$(systemctl show -p LoadState --value hermes-gateway-control.service 2>/dev/null || true)" == "loaded" ]]; then
  echo "STOP: hermes-gateway-control.service is loaded on this host" >&2
  exit 1
fi
EVIDENCE=/var/lib/hermes-control-deploy/c08cb1e-guest-node-witness
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
