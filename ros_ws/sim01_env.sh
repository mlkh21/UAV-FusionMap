#!/usr/bin/env bash
# SIM-01源码运行环境，独立激活Radar-Diffusion及Noetic。
set -euo pipefail
if [[ $# -eq 0 ]]; then
    printf '%s\n' '用法：bash ros_ws/sim01_env.sh <命令> [参数...]' >&2
    exit 2
fi
ufm_project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec /usr/bin/env -i \
    HOME="$HOME" USER="${USER:-$(id -un)}" LOGNAME="${LOGNAME:-$(id -un)}" \
    LANG=C.UTF-8 PATH=/usr/bin:/bin:/usr/sbin:/sbin \
    /bin/bash --noprofile --norc -c \
    'set -e; ufm_config="$1"; shift; ufm_task_args=("$@"); set --; source "$ufm_config"; exec "${ufm_task_args[@]}"' \
    ufm-sim01 "$ufm_project_root/configs/sim01_environment.bash" "$@"
