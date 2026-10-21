#!/bin/sh
cd /port-test || exit 80
./watchdog 10 /bin/cc -v
./watchdog 90 /bin/cc -O2 probe.m -lNeXT_s -o native-probe > native-build.txt 2>&1
native_build=$?
cat native-build.txt
echo NATIVE-BUILD "$native_build"
pid=''
for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
 pid=`./watchdog 5 /bin/ps -ax | awk '/[(]Workspace[)]|\/Workspace| Workspace/ {print $1;exit}'`
 if test -n "$pid"; then break; fi
 sleep 1
done
if test -z "$pid"; then echo DESKTOP-MISSING; exit 81; fi
failed=0
for compiler in native cross; do
 if test -x "$compiler-probe"; then
  ./watchdog 60 ./desktop-exec "$pid" @root "/port-test/$compiler-probe" "$compiler-AppKit-control" > "$compiler-run.txt" 2>&1
  result=$?
  echo PROBE-EXIT "$compiler" "$result"
  cat "$compiler-run.txt"
  if test "$result" != 0; then failed=1; fi
  grep 'resize returned' "$compiler-run.txt" >/dev/null || failed=1
  grep 'complete draws=[1-9]' "$compiler-run.txt" >/dev/null || failed=1
 else failed=1; fi
done
if test "$failed" = 0; then echo PORTS-SUITE 0; fi
exit "$failed"
