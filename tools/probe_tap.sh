#!/usr/bin/env bash
# ★ 真机/模拟器通用的「点按钮并取证据」脚本。
#
# ★ 为什么要有这个：★ 上一次排查把 tap 坐标写死、且用错的正则去解析
# ★ uiautomator 的 enabled 字段，★ 于是两个结论都是猜的。
# ★ 这里把三件事做对：
#   ① 每次都重新 dump 并按 XML 属性解析 bounds/enabled/clickable，★ 不写死坐标；
#   ② 先 WAKEUP + 确认屏幕是 on 且无 lockscreen，★ 再 dump；
#   ③ tap 前后各取一次 logcat，★ 而 onClick 一旦被调用必然有标记。
set -uo pipefail

SERIAL="${1:?用法: probe_tap.sh <serial>}"
PKG=com.harmonica.probe
ACT=.MainActivity
TAG=HarmonicaProbe

d() { echo "[$(date +%H:%M:%S)] $*"; }

# ── 0. 设备在不在 ────────────────────────────────────────────────
if ! adb -s "$SERIAL" get-state >/dev/null 2>&1; then
  echo "★ 判据未取得：设备 $SERIAL 不在线"; exit 1
fi
d "设备 $SERIAL 在线：$(adb -s "$SERIAL" shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
d "  API=$(adb -s "$SERIAL" shell getprop ro.build.version.sdk | tr -d '\r')"
d "  屏幕 power=$(adb -s "$SERIAL" shell dumpsys power 2>/dev/null | grep -oE 'mWakefulness=[A-Za-z]+' | head -1)"

# ── 1. 唤醒 + 解锁兜底（★ 真机尤其需要） ─────────────────────────
adb -s "$SERIAL" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
sleep 1
# 息屏状态下 dump 出来的常常是锁屏界面，★ 那样 bounds 全部作废
LOCKED=$(adb -s "$SERIAL" shell dumpsys window 2>/dev/null | grep -oE 'mDreamingLockscreen=[a-z]+' | head -1)
d "  锁屏状态 $LOCKED"
if [ "$LOCKED" = "mDreamingLockscreen=true" ]; then
  d "  ★ 检测到锁屏，★ 先 KEYCODE_MENU 划开"
  adb -s "$SERIAL" shell input keyevent KEYCODE_MENU >/dev/null 2>&1; sleep 1
  adb -s "$SERIAL" shell wm dismiss-keyguard >/dev/null 2>&1 || true; sleep 1
fi

# ── 2. 保证 Activity 在前台 ──────────────────────────────────────
FOREG=$(adb -s "$SERIAL" shell dumpsys activity activities 2>/dev/null | grep -oE "topResumedActivity=[^ ]*" | head -1)
d "  $FOREG"
if [[ "$FOREG" != *"$PKG"* ]]; then
  d "  ★ 不在前台，★ 重新拉起"
  adb -s "$SERIAL" shell am start -W -n "$PKG/$ACT" 2>&1 | tail -3
  sleep 3
fi

# ── 3. 重新 dump 并【按 XML 属性】解析（★ 不用正则） ──────────────
dump_button() {
  adb -s "$SERIAL" shell uiautomator dump /sdcard/uiaut.xml >/dev/null 2>&1
  adb -s "$SERIAL" exec-out cat /sdcard/uiaut.xml 2>/dev/null > /tmp/uiaut_$$.xml
  python3 - "$1" <<'PY'
import sys, re, xml.etree.ElementTree as ET
tag = sys.argv[1]
try:
    root = ET.parse('/tmp/uiaut_%d.xml' % __import__('os').getppid()).getroot()
except Exception:
    import os
    # 上面 getppid 未必是脚本 pid，★ 所以直接用 glob 找最新
    import glob
    cands = sorted(glob.glob('/tmp/uiaut_*.xml'), key=os.path.getmtime)
    if not cands:
        print('DUMPFAIL'); sys.exit(1)
    root = ET.parse(cands[-1]).getroot()
for n in root.iter('node'):
    if n.get('class','').endswith('Button') and '运行探针' in n.get('text',''):
        b = n.get('bounds','')
        m = re.match(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', b)
        if not m:
            print('BOUNDSFAIL '+b); sys.exit(1)
        x1,y1,x2,y2 = map(int, m.groups())
        print("%s %d %d %d %s %s %s %s" % (
            tag, (x1+x2)//2, (y1+y2)//2, x2-x1,
            n.get('enabled'), n.get('clickable'), n.get('package'), b))
        sys.exit(0)
print('NOTFOUND')
PY
}

d "── dump（tap 前）"
LINE=$(dump_button PRE)
d "  解析结果: $LINE"
read -r T CX CY W EN CK PKGAT BND <<<"$LINE"
if [ "$T" != "PRE" ] || [ -z "${CX:-}" ]; then
  echo "★ 判据未取得：没找到按钮（$LINE）"; exit 1
fi
d "  bounds=$BND  中心=($CX,$CY)  宽=$W  enabled=$EN clickable=$CK"
if [ "$EN" != "true" ]; then
  d "  ★ 按钮是 disabled！★ 这一条就是结论，★ 不用再 tap"
fi

# ── 4. tap 前后 logcat 切片 ─────────────────────────────────────
adb -s "$SERIAL" logcat -c >/dev/null 2>&1
TS=$(date +%s)
d "── tap ($CX,$CY)"
adb -s "$SERIAL" shell input tap "$CX" "$CY"
sleep 2
d "── tap 后 2s 的 $TAG 日志"
adb -s "$SERIAL" logcat -d -s "$TAG" 2>/dev/null | head -40
if adb -s "$SERIAL" logcat -d -s "$TAG" 2>/dev/null | grep -q "onClick 被调用"; then
  d "★★ onClick 确实被调用了 ★★ —— 按钮不是问题"
else
  d "★★ logcat 里没有 onClick 标记 ★★ —— 点击没送到 View"
fi

# ── 5. 等 run.log ───────────────────────────────────────────────
d "── 等 run.log（最多 ${2:-300}s）"
LIMIT=${2:-300}
for i in $(seq 1 $((LIMIT/5))); do
  sleep 5
  if adb -s "$SERIAL" exec-out run-as "$PKG" cat files/run.log 2>/dev/null | grep -q "端口产出"; then
    d "★ run.log 出来了（约 $((i*5))s）"; break
  fi
  if [ $((i % 6)) -eq 0 ]; then d "  ...$((i*5))s 还没有"; fi
done
d "── 最终 $TAG 日志"
adb -s "$SERIAL" logcat -d -s "$TAG" 2>/dev/null | tail -25
d "── python.stdout 行数：$(adb -s "$SERIAL" logcat -d 2>/dev/null | grep -c python.stdout)"
