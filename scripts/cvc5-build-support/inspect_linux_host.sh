#!/bin/sh
# Self-authored fixed read-only collector; embedded by the diagnostic launcher.
# No command/path/limit arguments, writes, network, recursive scan or fallback.
set -eu
set -o pipefail
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
LANG=C LC_ALL=C TZ=UTC
export PATH LANG LC_ALL TZ
[ "$#" -eq 0 ] || exit 125
fail() { printf 'AXHC01\terror\t%s\n' "$1" >&2; exit 125; }

filter() {
    /bin/busybox awk -v mode="$1" -v cap="$2" '
# AXIOM_FILTER_BEGIN
function bad() { failed=1; exit 125 }
function num(s,max) { return s ~ /^(0|[1-9][0-9]*)$/ && length(s)<=10 && s+0<=max }
function token(s) { return s ~ /^[a-zA-Z0-9_.-]+$/ && length(s)<=64 }
function emit(s) { output=output "AXHC01\t" mode "\t" s "\n"; if(length(output)>cap+4096) bad() }
function one() { if(lines!=1) bad() }
function path(s, a,n,i) {
    if(s !~ /^\/[a-zA-Z0-9_.:@\/-]+$/ || length(s)>2048 || s=="/") return 0;
    n=split(s,a,"/"); for(i=2;i<=n;i++) if(a[i]=="" || a[i]=="." || a[i]=="..") return 0;
    return 1
}
function mountrow( a,n,i,j,sep,point,root,fs,ro,found,klass,opt) {
    n=split($0,a," "); if(n<10 || !num(a[1],2147483647) || !num(a[2],2147483647) || a[3]!~/^[0-9]+:[0-9]+$/) bad();
    sep=0; for(i=7;i<=n;i++) if(a[i]=="-") { if(sep) bad(); sep=i }
    if(!sep || sep+3!=n) bad();
    point=a[5]; klass="";
    if(point=="/") klass="root";
    else if(point=="/sys/fs/cgroup") klass="cgroup";
    else if(mode=="mount_self" && point=="/mnt") klass="runtime";
    else if(mode=="mount_self" && point=="/host-observe/boot-id") klass="boot-id";
    else if(mode=="mount_self" && point=="/host-observe/filesystems") klass="filesystems";
    else if(mode=="mount_self" && point=="/host-observe/init-mountinfo") klass="init-mountinfo";
    else if(mode=="mount_self" && point=="/host-observe/cgroup") klass="host-cgroup";
    if(klass=="") return;
    if(seen[klass]++) bad();
    fs=a[sep+1]; if(fs!~/^(overlay|proc|cgroup2|tmpfs|virtiofs|fuse[.]orbstack|ext4|xfs|btrfs|erofs)$/) bad();
    if((klass=="cgroup" || klass=="host-cgroup") && fs!="cgroup2") bad();
    if((klass=="boot-id" || klass=="filesystems" || klass=="init-mountinfo") && fs!="proc") bad();
    if(a[4] ~ /\\/) bad(); root=a[4];
    # Never export arbitrary bind roots, sources or super options.
    if(klass=="runtime") root="redacted";
    else if(klass=="boot-id") { if(root!="/sys/kernel/random/boot_id") bad() }
    else if(klass=="filesystems") { if(root!="/filesystems") bad() }
    else if(klass=="init-mountinfo") { if(root!="/1/mountinfo") bad() }
    else if(root!="/") bad();
    ro=0; found=0; j=split(a[6],opt,",");
    for(i=1;i<=j;i++) { if(opt[i]=="ro") {ro=1;found++} else if(opt[i]=="rw") found++ }
    if(found!=1) bad();
    if(mode=="mount_self" && klass!="cgroup" && !ro) bad();
    if(mode=="mount_self" && klass!="root" && klass!="cgroup" && sep!=7) bad();
    emit(klass "\t" a[1] "\t" a[2] "\t" a[3] "\t" fs "\t" root "\t" ro)
}
function line(s) {
    $0=s; lines++; if(length($0)>65536) bad();
    if(mode=="boot") {
        if($0!~/^[0-9a-f-]+$/ || length($0)!=36 || substr($0,9,1)!="-" || substr($0,14,1)!="-" || substr($0,19,1)!="-" || substr($0,24,1)!="-") bad();
        s=$0; gsub(/-/,"",s); if(length(s)!=32) bad(); emit($0)
    } else if(mode=="filesystems") {
        if(NF<1 || NF>2 || (NF==2 && $1!="nodev") || !token($NF) || seen[$NF]++) bad(); emit($NF)
    } else if(mode=="mount_self" || mode=="mount_host") mountrow();
    else if(mode=="cgroup_path") {
        if(substr($0,1,3)!="0::" || !path(substr($0,4))) bad(); result=substr($0,4)
    } else if(mode=="uid_map" || mode=="gid_map") {
        if(NF!=3 || !num($1,4294967295) || !num($2,4294967295) || !num($3,4294967295) || $3==0 || $1+$3>4294967296 || $2+$3>4294967296 || lines>5 || (lines>1 && $1<last_end)) bad();
        last_end=$1+$3; if($1<=65532 && 65532<last_end) mapped++; emit($1 "\t" $2 "\t" $3)
    } else if(mode=="status") {
        key=$1; if(key ~ /^(Uid:|Gid:|Groups:|NoNewPrivs:|CapInh:|CapPrm:|CapEff:|CapBnd:|CapAmb:)$/) {
            if(seen[key]++) bad();
            if(key=="Uid:" || key=="Gid:") {if(NF!=5 || $2!="65532" || $3!="65532" || $4!="65532" || $5!="65532") bad()}
            else if(key=="Groups:") {if(NF!=1) bad()}
            else if(key=="NoNewPrivs:") {if(NF!=2 || $2!="1") bad()}
            else if(NF!=2 || $2!="0000000000000000") bad();
        }
    } else if(mode=="controllers" || mode=="subtree_control") {
        controller_count=NF;
        for(i=1;i<=NF;i++) { if($i!~/^(cpu|cpuset|io|memory|hugetlb|pids|rdma|misc|dmem)$/ || seen[$i]++) bad(); emit($i) }
    } else if(mode=="memory_max" || mode=="swap_max" || mode=="pids_max") {
        expected=(mode=="memory_max"?"134217728":(mode=="swap_max"?"0":"16")); if($0!=expected) bad(); emit($0)
    } else if(mode=="cpu_max") {
        if(NF!=2 || !num($1,1000000000) || !num($2,1000000000) || $1==0 || $2==0 || $1*2!=$2) bad(); emit($1 "\t" $2)
    } else if(mode=="type") { if($0!="domain") bad(); emit($0) }
    else if(mode=="events" || mode=="memory_events") {
        if(NF!=2 || seen[$1]++ || !num($2,4294967295)) bad();
        if(mode=="events") {if(($1!="populated" && $1!="frozen") || $2!=($1=="populated"?1:0)) bad()}
        else if($1!~/^(low|high|max|oom|oom_kill|oom_group_kill)$/ || $2!=0) bad(); emit($1 "\t" $2)
    } else if(mode=="namespace") {
        if($0!~/^(pid|mnt|cgroup|user|ipc|uts):\[[1-9][0-9]*\]$/ || length($0)>32) bad(); emit($0)
    } else if(mode=="uname") {
        if(NF!=3 || $1!="Linux" || $3!="aarch64" || $2!~/^[a-zA-Z0-9_.+-]+$/ || length($2)>128) bad(); emit($1 "\t" $2 "\t" $3)
    } else bad()
}
{
    # Consume decimal bytes, not awk implementation-specific NUL text semantics.
    for(z=1;z<=NF;z++) {
        if(!num($z,255)) bad(); b=$z+0;
        if(b==28) { if(ended || length(pending)) bad(); ended=1; continue }
        if(ended || ++bytes>cap || (b!=9 && b!=10 && (b<32 || b>126))) bad();
        if(b==10) { saved=$0; line(pending); $0=saved; pending="" }
        else { pending=pending sprintf("%c",b); if(length(pending)>65536) bad() }
    }
}
END {
    if(!ended || !lines || failed || length(pending)) exit 125;
    if(mode=="boot" || mode=="cgroup_path" || mode=="memory_max" || mode=="swap_max" || mode=="pids_max" || mode=="cpu_max" || mode=="type" || mode=="namespace" || mode=="uname") one();
    if(mode=="controllers" || mode=="subtree_control") {one(); if(!controller_count) emit("empty")}
    if(mode=="uid_map" || mode=="gid_map") {if(mapped!=1) exit 125}
    if(mode=="mount_self") {if(!seen["root"] || !seen["runtime"] || !seen["cgroup"] || !seen["boot-id"] || !seen["filesystems"] || !seen["init-mountinfo"] || !seen["host-cgroup"]) exit 125}
    if(mode=="mount_host") {if(!seen["root"] || !seen["cgroup"]) exit 125}
    if(mode=="status") {
        if(!seen["Uid:"] || !seen["Gid:"] || !seen["Groups:"] || !seen["NoNewPrivs:"] || !seen["CapInh:"] || !seen["CapPrm:"] || !seen["CapEff:"] || !seen["CapBnd:"] || !seen["CapAmb:"]) exit 125;
        emit("identity-checked")
    }
    if(mode=="events" && (!seen["populated"] || !seen["frozen"])) exit 125;
    if(mode=="memory_events" && (!seen["low"] || !seen["high"] || !seen["max"] || !seen["oom"] || !seen["oom_kill"] || !seen["oom_group_kill"])) exit 125;
    if(mode=="cgroup_path") print result; else printf "%s",output
}
# AXIOM_FILTER_END
'
}
# A unique terminal control record proves LF termination to the pure filter.
# head reads at most cap+1; neither raw file data nor applet errors are echoed.
bounded() {
    kind=$1 cap=$2 file=$3
    [ -f "$file" ] && [ ! -L "$file" ] || fail input-kind
    { /bin/busybox head -c "$((cap+1))" -- "$file" 2>/dev/null || exit 125
      printf '\034'
    } | /bin/busybox od -An -v -tu1 | filter "$kind" "$cap" || fail input-read-or-format
}
canonical() {
    actual=$(/bin/busybox readlink -f -- "$1" 2>/dev/null) || fail canonical-path
    [ "$actual" = "$1" ] || fail path-alias
}
procfile() {
    [ "$(/bin/busybox stat -f -c %t -- "$1" 2>/dev/null)" = 9fa0 ] || fail procfs
}
cgfile() {
    canonical "$1"
    [ "$(/bin/busybox stat -f -c %t -- "$1" 2>/dev/null)" = 63677270 ] || fail cgroupfs
}
[ "$(ulimit -n)" = 64 ] || fail nofile
for file in /proc/self/status /proc/self/mountinfo /proc/self/cgroup /proc/self/uid_map /proc/self/gid_map; do procfile "$file"; done
bounded status 65536 /proc/self/status
bounded mount_self 1048576 /proc/self/mountinfo
bounded uid_map 4096 /proc/self/uid_map
bounded gid_map 4096 /proc/self/gid_map
for file in /host-observe/boot-id /host-observe/filesystems /host-observe/init-mountinfo; do canonical "$file"; procfile "$file"; done
bounded boot 4096 /host-observe/boot-id
bounded filesystems 65536 /host-observe/filesystems
bounded mount_host 1048576 /host-observe/init-mountinfo
cgroup=$(bounded cgroup_path 4096 /proc/self/cgroup) || fail own-cgroup
base=/host-observe/cgroup
cgfile "$base"
bounded controllers 4096 "$base/cgroup.controllers"
bounded subtree_control 4096 "$base/cgroup.subtree_control"
# Never require type/events at the real root or enumerate siblings.
for pair in memory.max:memory_max memory.swap.max:swap_max pids.max:pids_max cpu.max:cpu_max cgroup.type:type cgroup.events:events memory.events:memory_events; do
    file=$base$cgroup/${pair%:*}
    cgfile "$file"
    bounded "${pair#*:}" 4096 "$file"
done
for ns in pid mnt cgroup user ipc uts; do
    { /bin/busybox readlink "/proc/self/ns/$ns" 2>/dev/null || exit 125; printf '\034'; } | /bin/busybox od -An -v -tu1 | filter namespace 4096 || fail namespace
done
{ /bin/busybox uname -srm 2>/dev/null || exit 125; printf '\034'; } | /bin/busybox od -An -v -tu1 | filter uname 4096 || fail uname
printf 'AXHC01\tend\tread-only-observation\n'
