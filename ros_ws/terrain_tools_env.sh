#!/usr/bin/env bash
set -euo pipefail
ufm_terrain_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec bash "$ufm_terrain_root/ros_ws/sim01_env.sh" /bin/bash --noprofile --norc -c \
    'mkdir -p "$UFM_ROOT/.runtime/terrain-cache"; export MPLCONFIGDIR="$UFM_ROOT/.runtime/terrain-cache"; export PYTHONPATH="$UFM_ROOT/.runtime/terrain-tools:$UFM_ROOT/application:$PYTHONPATH"; exec "$@"' ufm-terrain "$@"
