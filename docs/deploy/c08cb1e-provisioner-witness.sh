#!/bin/bash
# Provisioner witness. Reads the deployed state-dir loader, then
# onboarding/ and tombstones/ only. Does not print file bodies.
set -euo pipefail
if [[ $# -ne 0 ]]; then
  echo "STOP: c08cb1e-provisioner-witness.sh takes no arguments" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
py=/usr/bin/python3.12
if [[ ! -x $py ]]; then
  echo "STOP: /usr/bin/python3.12 is missing" >&2
  exit 1
fi
exec "$py" "$here/c08cb1e_material.py" provisioner-witness
