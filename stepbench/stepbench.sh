#!/usr/bin/env bash
# Step-time microbenchmark: splits "a CI step" into the costs that nested
# virtualisation, CPU overcommit and network egress each hit differently.
# Prints one JSON object per line: {"t": name, "v": value, "u": unit}.
# Usage: stepbench.sh <label> [workdir]
set -u
LABEL=${1:-unknown}
WORK=${2:-${RUNNER_TEMP:-/tmp}/stepbench}
rm -rf "$WORK"; mkdir -p "$WORK"; cd "$WORK"
GO_URL=https://dl.google.com/go/go1.24.6.linux-amd64.tar.gz
PY_URL=https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.2.6.tar.gz

j() { printf '{"label":"%s","t":"%s","v":%s,"u":"%s"}\n' "$LABEL" "$1" "$2" "$3"; }
now() { date +%s.%N; }
el() { awk -v a="$1" -v b="$(now)" 'BEGIN{printf "%.3f", b-a}'; }
steal() { awk '/^cpu /{print $9}' /proc/stat; }

flags=$(grep -m1 '^flags' /proc/cpuinfo)
has() { [[ " $flags " == *" $1 "* ]] && echo 1 || echo 0; }
printf '{"label":"%s","t":"env","model":"%s","nproc":%s,"mem_mb":%s,"clocksource":"%s","avx2":%s,"avx512f":%s,"sha_ni":%s,"aes":%s,"hypervisor":%s,"kernel":"%s"}\n' \
  "$LABEL" "$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)" "$(nproc)" \
  "$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)" \
  "$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null)" \
  "$(has avx2)" "$(has avx512f)" "$(has sha_ni)" "$(has aes)" "$(has hypervisor)" "$(uname -r)"

S0=$(steal); T0=$(now)

# 1. timer calls: vDSO clock is ~20 ns; a VM that lost kvm-clock/tsc pays a syscall or a VM exit
j clock_ns "$(python3 -c '
import time
n=2_000_000; t=time.perf_counter()
for _ in range(n): time.time()
print(round((time.perf_counter()-t)/n*1e9,1))')" ns_per_call

# 2. syscall cost (getppid is a real syscall)
j syscall_ns "$(python3 -c '
import os,time
n=1_000_000; t=time.perf_counter()
for _ in range(n): os.getppid()
print(round((time.perf_counter()-t)/n*1e9,1))')" ns_per_call

# 3. fork+exec: test runners, configure scripts, git and shells live on this
t=$(now); for _ in $(seq 2000); do /bin/true; done; j fork_exec_2000 "$(el "$t")" s

# 4. pure single-thread CPU (an interpreter loop, like pytest's own overhead)
j py_cpu "$(python3 -c '
import time
t=time.perf_counter()
def f(n):
    s=0
    for i in range(n): s+=i*i%7
    return s
f(30_000_000)
print(round(time.perf_counter()-t,3))')" s

# 5. crypto single and 4 threads (also shows whether SHA/AES extensions reach the guest)
sha1=$(openssl speed -seconds 5 -bytes 16384 sha256 2>/dev/null | awk '/^sha256/{print $NF}' | tr -d k)
j sha256_1t "${sha1:-0}" kB_per_s
sha4=$(openssl speed -multi 4 -seconds 5 -bytes 16384 sha256 2>/dev/null | awk '/^sha256/{print $NF}' | tr -d k)
j sha256_4t "${sha4:-0}" kB_per_s
aes=$(openssl speed -seconds 5 -bytes 16384 -evp aes-256-gcm 2>/dev/null | awk '/^AES-256-GCM/{print $NF}' | tr -d k)
j aes_gcm_1t "${aes:-0}" kB_per_s

# 6. memory: first-touch page faults (EPT/two-level paging cost) and bandwidth
j pagefault_2g "$(python3 -c '
import mmap,time
n=2<<30; t=time.perf_counter()
m=mmap.mmap(-1,n)
for o in range(0,n,4096): m[o]=1
print(round(time.perf_counter()-t,3))')" s
t=$(now); dd if=/dev/zero of=/dev/null bs=1M count=20000 status=none; j memcpy_20g "$(el "$t")" s

# 7. disk: many small files (node_modules / site-packages shape), then sequential write
t=$(now)
python3 - <<'PY'
import os
for d in range(300):
    p=f"tree/d{d}"; os.makedirs(p)
    for f in range(100):
        with open(f"{p}/f{f}.js","wb") as h: h.write(b"x"*4096)
PY
tar cf tree.tar tree && rm -rf tree && tar xf tree.tar && rm -rf tree tree.tar
j smallfiles_30k "$(el "$t")" s
t=$(now); dd if=/dev/zero of=big bs=1M count=2048 conv=fdatasync status=none; j seqwrite_2g "$(el "$t")" s; rm -f big

# 8. network: a big object from Google's CDN and a PyPI sdist
t=$(now); curl -fsSL -o go.tgz "$GO_URL"; j dl_go_tarball "$(el "$t")" s
j dl_go_bytes "$(stat -c %s go.tgz)" bytes
t=$(now); curl -fsSL -o np.tgz "$PY_URL"; j dl_pypi_sdist "$(el "$t")" s

# 9. a real compile: Go std with a cold build cache on 4 workers
t=$(now); tar xzf go.tgz; j untar_go "$(el "$t")" s
export GOROOT=$PWD/go GOCACHE=$PWD/gocache GOFLAGS=-p=4 GOTOOLCHAIN=local
t=$(now); ./go/bin/go build -a std >/dev/null 2>&1; j go_build_std "$(el "$t")" s

j total "$(el "$T0")" s
S1=$(steal); j steal_ticks "$((S1-S0))" ticks
cd /; rm -rf "$WORK"
