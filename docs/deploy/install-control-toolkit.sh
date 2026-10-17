#!/bin/bash
# Install the permanent Control deploy toolkit from a verified staging directory.
# This script copies bytes. It does not execute the toolkit scripts or import
# their Python modules. It does not modify directories outside the destination.
set -euo pipefail

dest=/opt/hermes-control-deploy
walk_root=/
staging=
require_host=
require_user=

usage() {
  printf 'STOP: usage: install-control-toolkit.sh --staging DIR [--dest DIR] [--walk-root DIR] [--require-host NAME] [--require-user NAME]\n' >&2
  exit 2
}

stop() {
  printf 'STOP: %s\n' "$1" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case $1 in
    --staging)
      staging=${2:-}
      shift 2
      ;;
    --dest)
      dest=${2:-}
      shift 2
      ;;
    --walk-root)
      walk_root=${2:-}
      shift 2
      ;;
    --require-host)
      require_host=${2:-}
      shift 2
      ;;
    --require-user)
      require_user=${2:-}
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

[ -n "$staging" ] || usage
case $dest in
  /*) ;;
  *) stop "destination is not absolute" ;;
esac
case $walk_root in
  /*) ;;
  *) stop "walk root is not absolute" ;;
esac
if [ "$walk_root" = / ]; then
  [ "$dest" = /opt/hermes-control-deploy ] || stop "refusing a destination other than /opt/hermes-control-deploy"
fi
case $dest in
  "$walk_root" | "$walk_root"/*) ;;
  *) stop "destination is outside the walk root" ;;
esac

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo -n -- "$@"
  fi
}

script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
manifest=$script_dir/control-toolkit-manifest.sha256
[ -f "$manifest" ] || stop "manifest is missing beside the installer"
[ -L "$manifest" ] && stop "manifest path is a symlink"

declare -A expected_hash
expected_names=()
while IFS= read -r line || [ -n "$line" ]; do
  [ -n "$line" ] || continue
  case $line in
    *"  "*) ;;
    *) stop "manifest line is not hash and name" ;;
  esac
  hash=${line%%  *}
  name=${line#*  }
  if [[ ! $hash =~ ^[0-9a-f]{64}$ ]]; then
    stop "manifest hash is not 64 hex characters"
  fi
  case $name in
    */* | *$'\n'* | "" | .* ) stop "manifest name is not a bare filename" ;;
  esac
  [ -z "${expected_hash[$name]+x}" ] || stop "manifest repeats $name"
  expected_hash[$name]=$hash
  expected_names+=("$name")
done < "$manifest"
[ "${#expected_names[@]}" -eq 5 ] || stop "manifest does not list five files"

mode_for() {
  case $1 in
    c08cb1e-deploy-plan.md) printf '644\n' ;;
    c08cb1e-guest-node-witness.sh | c08cb1e-preflight.sh | c08cb1e-provisioner-witness.sh | c08cb1e_material.py) printf '755\n' ;;
    *) stop "no mode for $1" ;;
  esac
}

if [ -n "$require_user" ]; then
  [ "$(id -un)" = "$require_user" ] || stop "invoking user is not $require_user"
  root_uid=$(as_root id -u) || stop "sudo -n id -u failed"
  [ "$root_uid" = 0 ] || stop "sudo -n did not return uid 0"
fi

if [ -n "$require_host" ]; then
  fqdn=$(hostname -f) || stop "hostname -f failed"
  static=$(hostnamectl --static) || stop "hostnamectl --static failed"
  fqdn=${fqdn//$'\n'/}
  static=${static//$'\n'/}
  [ "$fqdn" = "$require_host" ] || stop "hostname -f is not the approved FQDN"
  [ "$static" = "$require_host" ] || stop "hostnamectl --static is not the approved name"
fi

[ -L "$staging" ] && stop "staging path is a symlink"
[ -d "$staging" ] || stop "staging path is not a directory"
staging_mode=$(stat -c %a -- "$staging")
staging_owner=$(stat -c %U -- "$staging")
case ${staging_mode: -2} in
  *2* | *3* | *6* | *7*) stop "staging directory is group or world writable" ;;
esac
if [ "$(id -u)" -eq 0 ]; then
  [ "$staging_owner" = root ] || stop "staging directory is not owned by root"
else
  [ "$staging_owner" = "$(id -un)" ] || [ "$staging_owner" = root ] || stop "staging directory is not owned by the invoking user"
fi

mapfile -t staged < <(ls -A1 --quoting-style=literal -- "$staging")
[ "${#staged[@]}" -eq 5 ] || stop "staging does not contain exactly the five toolkit files"
for name in "${expected_names[@]}"; do
  found=0
  for staged_name in "${staged[@]}"; do
    [ "$staged_name" = "$name" ] && found=1
  done
  [ "$found" -eq 1 ] || stop "staging is missing $name"
  path=$staging/$name
  [ -L "$path" ] && stop "staging file is a symlink: $name"
  [ -f "$path" ] || stop "staging file is not a regular file: $name"
  got=$(sha256sum -- "$path")
  got_hash=${got%%  *}
  [ "$got_hash" = "${expected_hash[$name]}" ] || stop "staging hash mismatch: $name"
done

writable_mode() {
  case ${1: -2} in
    *2* | *3* | *6* | *7*) return 0 ;;
    *) return 1 ;;
  esac
}

inspect_ancestor() {
  local path=$1
  [ -L "$path" ] && stop "ancestor is a symlink: $path"
  [ -d "$path" ] || stop "ancestor is not a directory: $path"
  local owner mode
  owner=$(stat -c %U -- "$path")
  mode=$(stat -c %a -- "$path")
  [ "$owner" = root ] || stop "ancestor is not owned by root: $path"
  if writable_mode "$mode"; then
    stop "ancestor is group or world writable: $path"
  fi
}

parent=$dest
while [ "$parent" != "$walk_root" ]; do
  parent=$(dirname -- "$parent")
  [ "$parent" != "$dest" ] || stop "could not walk to the walk root"
  inspect_ancestor "$parent"
  [ "$parent" = / ] && [ "$walk_root" = / ] && break
done

ensure_dir() {
  local path=$1
  if [ -L "$path" ]; then
    stop "toolkit path is a symlink: $path"
  fi
  if [ -e "$path" ]; then
    [ -d "$path" ] || stop "toolkit path is not a directory: $path"
    local owner mode
    owner=$(as_root stat -c %U -- "$path")
    mode=$(as_root stat -c %a -- "$path")
    [ "$owner" = root ] || stop "toolkit directory is not owned by root: $path"
    [ "$mode" = 755 ] || stop "toolkit directory mode is not 755: $path"
    return 0
  fi
  as_root mkdir -m 0755 -- "$path" || stop "mkdir failed: $path"
  as_root chown root:root -- "$path" || stop "chown failed: $path"
}

deploy=$dest/docs/deploy
if [ -e "$dest" ] || [ -L "$dest" ]; then
  ensure_dir "$dest"
fi
if [ -e "$dest/docs" ] || [ -L "$dest/docs" ]; then
  ensure_dir "$dest/docs"
fi
if [ -L "$deploy" ]; then
  stop "toolkit path is a symlink: $deploy"
fi

declare -A present=()
present_count=0
if [ -d "$deploy" ] && [ ! -L "$deploy" ]; then
  ensure_dir "$deploy"
  mapfile -t existing < <(as_root ls -A1 --quoting-style=literal -- "$deploy")
  for name in "${existing[@]}"; do
    known=0
    for expected in "${expected_names[@]}"; do
      [ "$name" = "$expected" ] && known=1
    done
    [ "$known" -eq 1 ] || stop "unexpected file in toolkit directory: $name"
    path=$deploy/$name
    [ -L "$path" ] && stop "toolkit file is a symlink: $name"
    [ -f "$path" ] || stop "toolkit file is not a regular file: $name"
    got=$(as_root sha256sum -- "$path")
    got_hash=${got%%  *}
    [ "$got_hash" = "${expected_hash[$name]}" ] || stop "installed hash mismatch: $name"
    present[$name]=1
    present_count=$((present_count + 1))
  done
fi

ensure_dir "$dest"
ensure_dir "$dest/docs"
ensure_dir "$deploy"

action=unchanged
for name in "${expected_names[@]}"; do
  src=$staging/$name
  dst=$deploy/$name
  mode=$(mode_for "$name")
  if [ -L "$dst" ]; then
    stop "toolkit file is a symlink: $name"
  fi
  if [ -e "$dst" ]; then
    owner=$(as_root stat -c %U -- "$dst")
    group=$(as_root stat -c %G -- "$dst")
    cur=$(as_root stat -c %a -- "$dst")
    if [ "$owner" != root ] || [ "$group" != root ]; then
      as_root chown root:root -- "$dst" || stop "chown failed: $name"
      if [ "$action" = unchanged ]; then
        action=modes-repaired
      fi
    fi
    if [ "$cur" != "$mode" ]; then
      as_root chmod "$mode" -- "$dst" || stop "chmod failed: $name"
      if [ "$action" = unchanged ]; then
        action=modes-repaired
      fi
    fi
  else
    as_root install -o root -g root -m "$mode" -- "$src" "$dst" || stop "install failed: $name"
    if [ "${present[$name]+x}" = 1 ]; then
      stop "file appeared during install: $name"
    fi
    if [ "$action" = unchanged ] || [ "$action" = modes-repaired ]; then
      if [ "$present_count" -eq 0 ]; then
        action=created
      else
        action=completed
      fi
    fi
  fi
done

mapfile -t final_names < <(as_root ls -A1 --quoting-style=literal -- "$deploy")
[ "${#final_names[@]}" -eq 5 ] || stop "toolkit directory does not contain exactly five files"
lines=()
for name in "${expected_names[@]}"; do
  path=$deploy/$name
  [ -L "$path" ] && stop "toolkit file is a symlink: $name"
  got=$(as_root sha256sum -- "$path")
  got_hash=${got%%  *}
  [ "$got_hash" = "${expected_hash[$name]}" ] || stop "final hash mismatch: $name"
  owner=$(as_root stat -c %U:%G -- "$path")
  mode=$(as_root stat -c %a -- "$path")
  [ "$owner" = root:root ] || stop "final owner is not root:root: $name"
  [ "$mode" = "$(mode_for "$name")" ] || stop "final mode mismatch: $name"
  lines+=("$(printf 'toolkit-file=%s owner=%s mode=%s sha256=%s' "$name" "$owner" "$mode" "$got_hash")")
done
printf 'toolkit=ready\n'
printf 'toolkit-action=%s\n' "$action"
printf 'toolkit-dest=%s\n' "$deploy"
printf 'toolkit-class=state-changing\n'
printf '%s\n' "${lines[@]}"
