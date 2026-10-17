#!/bin/bash
# Read-only Control-host diagnostic for c08cb1e-deploy-plan.md.
# Exit 0: diagnostic=completed and host-ready=yes.
# Exit 4: diagnostic=completed and host-ready=no. Not a pass.
# Exit 1: the diagnostic failed. Exit 2: bad usage.
# This script does not write, restart, install, fetch, or print secret values.
set -euo pipefail
if [[ $# -ne 0 ]]; then
  echo "STOP: c08cb1e-preflight.sh takes no arguments" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
py=/usr/bin/python3.12
if [[ ! -x $py ]]; then
  py=python3
fi
exec "$py" "$here/c08cb1e_material.py" preflight
