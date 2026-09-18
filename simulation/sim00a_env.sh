#!/usr/bin/env bash
# 为构建与依赖检查创建独立环境，不改变调用终端的ROS/Conda选择。
set -euo pipefail
if [[ $# -eq 0 ]]; then
    printf '%s\n' '用法：bash simulation/sim00a_env.sh <命令> [参数...]' >&2
    exit 2
fi
ufm_project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec /usr/bin/env -i \
    HOME="$HOME" USER="${USER:-$(id -un)}" LOGNAME="${LOGNAME:-$(id -un)}" \
    LANG=C.UTF-8 PATH=/usr/bin:/bin:/usr/sbin:/sbin \
    /bin/bash --noprofile --norc -c \
    'set -e; source "$1"; shift; exec "$@"' \
    ufm-sim00a "$ufm_project_root/configs/sim00a_environment.bash" "$@"
