# Step A 运行准入

**BLOCKED。** 现有工作账号有补充组权限。未找到获准的专用非 root 账号或可用的独立运行 cgroup。当前是 cgroup v2，工作会话读到 `memory.max=max`、`pids.max=34352`、`cpu.max=max 100000`。无本轮 Step A 执行授权。只读盘点日志 SHA256 为 `21023ec17d527096cd1c2effa0b1a0777d1d24349aa3b3add1781ee85c19846c`。

| 准入 | 实测状态 |
| --- | --- |
| 专用账号与输入访问 | BLOCKED。原 Phase 8G 投影是工作账号所有的 0700 目录。未验证任何专用账号可遍历并只读访问计划文件。 |
| 独立物理内存、CPU、任务数 | BLOCKED。共享会话的 cgroup 不作为验收。 |
| 模拟器和输入身份 | 已重新计算匹配。QEMU 5.2.0 提供 `cortex-a9`，三个冻结输入匹配 Phase 8G。 [身份表](QEMU_SMOKE_RESULTS.md) |
| 网络、PID namespace、输出、超时与回收 | Phase 8G 有宿主合成证据。实际专用账号、独立 cgroup 内的完整组合仍 NOT_VERIFIED。 [宿主合成证据](../phase8g/PROCESS_CLEANUP_VALIDATION.md) |
| 用户授权 | BLOCKED。需在准入验证后对下列固定范围取得明确授权。 |

## 管理员配置和验证

以下是管理员在获准后执行的配置步骤。本轮仅提供步骤。脚本、投影和产出应在 workspace 的获准目录。宿主账号数据库与 systemd 属于管理员变更范围。

1. 提供只用于本轮的系统账号和同名组。核对非零 UID、无登录 shell、无 sudo 和多余补充组。选择尚未占用的账号名，例如 `tizen-smoke`。

   ```bash
   getent passwd tizen-smoke
   # 仅在管理员确认名称未占用并获准创建时执行
   sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin tizen-smoke
   id tizen-smoke
   getent passwd tizen-smoke
   ```

2. 在 workspace 内选择新的 `INPUT` 目录，由管理员管理，授予测试账号所在组读取和遍历，给所需上级目录最小遍历权限。仅复制审核通过的普通投影文件。冻结源文件保留原字节、原权限。执行使用的副本需要普通执行位，QEMU 5.2.0 上游的 ELF 启动逻辑会拒绝没有任何执行位的文件，Phase 8G 的只读审查副本为 0444。新副本继续只读绑定且字节摘要一致，禁止 setuid/setgid 与 file capabilities。 [QEMU 5.2.0 加载实现](https://raw.githubusercontent.com/qemu/qemu/v5.2.0/linux-user/linuxload.c)

   ```bash
   # INPUT 为新的授权目录，PROJECTION 为已核对的 Phase 8G 投影
   sudo install -d -o root -g tizen-smoke -m 0750 "$INPUT" \
     "$INPUT/runner" "$INPUT/lib" "$INPUT/usr" "$INPUT/usr/lib"
   sudo install -o root -g tizen-smoke -m 0550 "$PROJECTION/runner/probe" "$INPUT/runner/probe"
   sudo install -o root -g tizen-smoke -m 0440 "$PROJECTION/lib/ld-linux.so.3" "$INPUT/lib/ld-linux.so.3"
   sudo install -o root -g tizen-smoke -m 0440 "$PROJECTION/lib/libc.so.6" "$INPUT/lib/libc.so.6"
   sudo -u tizen-smoke -- sha256sum "$INPUT/runner/probe" "$INPUT/lib/ld-linux.so.3" "$INPUT/lib/libc.so.6"
   sudo -u tizen-smoke -- test -x "$INPUT/runner/probe"
   sudo -u tizen-smoke -- test ! -w "$INPUT/runner/probe"
   stat -c '%a %F' "$INPUT/runner/probe" "$INPUT/lib/ld-linux.so.3" "$INPUT/lib/libc.so.6"
   getcap "$INPUT/runner/probe" "$INPUT/lib/ld-linux.so.3" "$INPUT/lib/libc.so.6"
   ```

   在全部挂载文件、目录及上级的只读/不可替换边界上检查同样的所有权和有效权限。摘要须与[身份表](QEMU_SMOKE_RESULTS.md)逐项匹配。

3. 在系统级 systemd 以专用 slice 和瞬态服务先运行**已审核的静态 x86-64 沙箱替代探针**。配置 slice 在观察完成前保留，独占本次尝试。控制器与证据观察员留在该 slice 外。以下 `HOST_ONLY_PREFLIGHT` 是管理员审阅并以只读方式放在 workspace 的宿主启动脚本。只包含第 4 步的沙箱复查与宿主 fixture，执行前可安排有界等待，便于观察服务身份。它不调用 ARM 程序。

   ```bash
   sudo systemctl start tizensmoke.slice
   sudo systemctl set-property --runtime tizensmoke.slice \
     MemoryMax=256M MemorySwapMax=0 CPUQuota=100% TasksMax=32
   sudo systemd-run --wait --pipe --unit=tizen-smoke-preflight --slice=tizensmoke.slice \
     --property=User=tizen-smoke --property=Group=tizen-smoke \
     --property=NoNewPrivileges=yes --property=PrivateNetwork=yes \
     --property=KillMode=control-group --property=RuntimeMaxSec=15s \
     --property=TimeoutStopSec=2s --property=LimitCORE=0 \
     /usr/bin/prlimit --cpu=10 --as=8589934592 --nofile=64 --fsize=1048576 -- "$HOST_ONLY_PREFLIGHT"
   ```

   从另外的终端或管理员观察员读取有效限制和服务归属。路径与 inode 必须在运行前后绑定到同一专用 slice。若读取不到已固定身份，不能判空。通过 `cgroup.events` 观察从 `populated 1` 到 `populated 0`，确认停机后无剩余任务，最后由管理员收回授权的专用单元。 [systemd 资源控制](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html) · [systemd-run](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)

   ```bash
   CG="$(systemctl show -p ControlGroup --value tizensmoke.slice)"
   test "$CG" = /tizensmoke.slice || exit 1
   stat -Lc '%d:%i' "/sys/fs/cgroup$CG"
   cat "/sys/fs/cgroup$CG"/{memory.max,memory.swap.max,pids.max,cpu.max,cgroup.events}
   systemctl show tizen-smoke-preflight.service -p User -p ControlGroup -p MainPID -p ExecMainStatus
   ```

4. 宿主替代程序使用计划中的真实输入绑定和 Bubblewrap 参数，最后只运行宿主 fixture。验证网络 namespace 与宿主不同且除 loopback 外无接口，PID namespace 独立，权限为非 root、capabilities 为零、`NoNewPrivs=1`。确认 `--unshare-all --unshare-user --disable-userns --die-with-parent --new-session --cap-drop ALL --clearenv` 生效。沙箱只含四个获准输入、私有 `/proc` 和 16 MiB 的私有 tmpfs。通过宿主 fixture 的定向反例验证组合 stdout/stderr 上限 1 MiB、文件上限 1 MiB、墙钟 15 秒与 2 秒升级终止、故意超量/超时和独立会话中的子进程均正确回收。检查 sandbox 产物只读，专用账号无写入输入或 cgroup 的权限。 [回收证明](RUNTIME_CLEANUP_GATE.md)

获准 Step A 的范围仅包括冻结 `vd-A-C`、固定 `qemu-arm-static -cpu cortex-a9 -L /`、VD `/lib/ld-linux.so.3` 与 `/lib/libc.so.6`。无参数、stdin 关闭、无公网。沙箱仅写私有 16 MiB 临时目录，外层监督器仅写 workspace 内本轮新证据目录。进程、输出和磁盘证据限制按上述验收。用户须对这一次运行明确授权。
