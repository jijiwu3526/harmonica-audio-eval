package com.harmonica.probe;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/**
 * 手机探针的唯一界面：★ 一个按钮 + 一个日志窗。
 *
 * ★ 负责人原话：「带足够的日志接口，★ 要不问题出在哪都不知道」
 * ★ ★ ★ 而本类的职责就一件：★ 把 Python 侧的日志【实时】显示出来，
 * ★ ★ ★ 并保证它【落盘】，★ 以便 adb pull 出去。
 * ★ ★ ★ 而「只打 Log.i 是不够的」——logcat 会丢、会被刷掉。
 *
 * ★ ★ ★ ★ ★ 2026-09-26 真机排障追加：★ 这句话本类自己没做到。★★ ★
 * ★ ★ ★ ★ ★ 改版前的这个类【一行 logcat 都不打】——Java 侧没有 Log，
 * ★ ★ ★ ★ ★ 而 Python 的 print() 走 Chaquopy 的 python.stdout。
 * ★ ★ ★ ★ ★ 于是「logcat 里零 Python 迹象」这句话【什么都不能证明】：
 * ★ ★ ★ ★ ★ 它既符合「点击根本没送到 View」，★ 也符合「点击送到了、
 * ★ ★ ★ ★ ★ 但 startProbe 里立刻抛异常」——★ 而后者只会写进【屏幕上的
 * ★ ★ ★ ★ ★ TextView】，★ logcat 里一个字都没有。
 * ★ ★ ★ ★ ★ 所以那时候的排查是【在一个不发声的麦克风前面猜】。
 * ★ ★ ★ ★ ★ 现在补上：★ 生命周期、点击、Python 取模块、每一步异常
 * ★ ★ ★ ★ ★ 全部进 logcat，★ 且同时落 files/ui_state.txt。
 */
public class MainActivity extends Activity {

    private static final String TAG = "HarmonicaProbe";
    private static final int LOGCAT_TEXT_CAP = 1500;

    private TextView logView;
    private ScrollView scroller;
    private Button runButton;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private StringBuilder buffer = new StringBuilder();

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        L("onCreate 进入  pid=" + android.os.Process.myPid()
                + "  sdk=" + android.os.Build.VERSION.SDK_INT
                + "  release=" + android.os.Build.VERSION.RELEASE
                + "  model=" + android.os.Build.MODEL);

        if (!Python.isStarted()) {
            // ★ 顺带把这一段的成败说清楚：★ 若它在 API 36 上抛，onCreate 会
            // ★ 连带 onCreate 整体抛出 → ActivityThread 杀掉进程。
            // ★ ★ ★ 「进程活着 + MainActivity 处于 resumed」这两个事实合起来
            // ★ ★ ★ 就等于证明了 Python.start() 在这台设备上成功返回了。
            L("Python.start() 之前 isStarted=" + Python.isStarted());
            Python.start(new AndroidPlatform(this));
            L("Python.start() 成功返回  isStarted=" + Python.isStarted());
        } else {
            L("Python 已启动，★ 跳过 start()");
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        // ★ ★ ★ 【设计留白】★ 与【系统栏留白】★ 必须分开记，★ 否则
        // ★ onApplyWindowInsets 一来就把设计值覆盖掉，★ 而那正是
        // ★ 「改大一点凑合一下」那种临时糊法的形态。★
        root.setBackgroundColor(Color.WHITE);
        final int padL = dp(24), padT = dp(32), padR = dp(24), padB = dp(24);
        root.setPadding(padL, padT, padR, padB);
        // ★ ★ ★★★ 这就是本 bug 的修法所在 ★★★ ★★
        // ★ 2026-09-26 真机实测（a83b8ad / PJD110 / API 36 / 1440x3168）：
        // ★   状态栏      frame=[0,0][1440,160]
        // ★   标题 TextView bounds=[24,32][1416,141]   ← 整条都在状态栏底下
        // ★   按钮       bounds=[24,141][1416,333]    ← 顶 141 < 160，★ 被盖 19px
        // ★ 而 taps 实测：★ 按钮正中 (720,237) 敲下去，★ logcat 里
        // ★   「★ onClick 被调用」零命中 ——★ 点击被系统栏吃掉了。
        // ★
        // ★ ★ 模拟器（emulator-5554 / Pixel_7 / API 34）为什么看不出问题：
        // ★   那台状态栏只有 136px，★ 而按钮顶 141 > 136，★ 刚好躲过去了。
        // ★   差 5 个像素 ——★ 这就是「模拟器全绿、真机全废」的全部原因。
        // ★
        // ★ 为什么用「加 padding」而不是别的方式：
        // ★   ① 声明式固定值（32px）只对【一种设备】成立，★ 换个状态栏
        // ★      高度、换个刘海、换台平板就又盖住了。★ 而 padding 是
        // ★      【问系统要真值】，★ 任何设备都对。
        // ★   ② 将来正式界面必然有列表/详情/全屏播放/横屏，★ 那时
        // ★      每个页面都要避让系统栏；★ 把它做成【一处装好、整棵树生效】
        // ★      的根容器，★ 正式界面才能直接复用。
        // ★   ③ 它保留「内容画到栏下」的现代观感（栏底还能有底色/毛玻璃），
        // ★      而不是退回「系统先垫一层」的旧模型。
        // ★
        // ★ 为什么必须配 (c) 换主题 ——★ 这是本轮实测新发现的第二层盖子：
        // ★   上面 dump 里还有一行，★ 它比状态栏更致命：
        // ★     android:id/action_bar bounds=[0,160][1440,384]
        // ★   Theme.Material.Light 带 ActionBar，★ 而它【不透明】且被系统
        // ★   直接压在内容之上。★ 所以哪怕我把 padding 加足，★ 按钮仍会
        // ★   藏在 ActionBar 底下 ——★ 只加 padding 是【治了上面、漏了下面】。
        // ★   所以主题一并换成无 ActionBar 的（见 AndroidManifest.xml）。
        // ★
        // ★ 还有一个平台级的坑（实测 dumpsys window）：
        // ★   mAttrs pfl=... EDGE_TO_EDGE_ENFORCED
        // ★ targetSdk 35 起，★ 系统【强制】edge-to-edge，★
        // ★   而 decorFitsSystemWindows(true) 在这个 flag 下【不生效】
        // ★   ——★ 所以「(a) 让系统不 overlay」这条路在 targetSdk≥35 上
        // ★   本来就是死的。★ 这是实测读出来的，★ 不是推测。
        root.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override
            public WindowInsets onApplyWindowInsets(View v, WindowInsets insets) {
                int top, bottom, left, right;
                if (Build.VERSION.SDK_INT >= 30) {
                    android.graphics.Insets bars = insets.getInsets(
                            WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                    top = bars.top; bottom = bars.bottom;
                    left = bars.left; right = bars.right;
                } else {
                    // ★ 老分支：★ minSdk 24，★ 正式界面若要覆盖老设备就靠它。
                    top = insets.getSystemWindowInsetTop();
                    bottom = insets.getSystemWindowInsetBottom();
                    left = insets.getSystemWindowInsetLeft();
                    right = insets.getSystemWindowInsetRight();
                }
                // ★ 系统栏是【叠在】内容上的，★ 所以 padding 取 max(设计值, 系统给的)，
                // ★ 而不是相加 ——★ 相加会让「本来就不盖」的设备凭空多出一块空白。
                root.setPadding(
                        Math.max(padL, left),
                        Math.max(padT, top),
                        Math.max(padR, right),
                        Math.max(padB, bottom));
                L("★ onApplyWindowInsets  系统栏=" + top + "/" + right
                        + "/" + bottom + "/" + left + "  →  root padding="
                        + Math.max(padL, left) + "/" + Math.max(padT, top)
                        + "/" + Math.max(padR, right) + "/" + Math.max(padB, bottom));
                return insets;
            }
        });

        TextView title = new TextView(this);
        title.setText("口琴内核 · 手机探针");
        title.setTextSize(18);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setPadding(0, 0, 0, 12);
        root.addView(title);

        runButton = new Button(this);
        runButton.setText("运行探针（阶段 0→3）");
        runButton.setOnClickListener(v -> {
            // ★ 记下 onClick 真的被调用了。★ 这一行是「点击到底送没送到」
            // ★ 唯一无法伪造的证据——★ 有了它，logcat 静默就只可能是
            // ★ 「点击没送到」，★ 而不再是两种可能。
            L("★ onClick 被调用  按钮 enabled=" + v.isEnabled()
                    + " clickable=" + v.isClickable());
            startProbe();
        });
        root.addView(runButton);

        scroller = new ScrollView(this);
        logView = new TextView(this);
        logView.setTextSize(10);
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setTextIsSelectable(true);   // ★ 允许长按复制，★ 用户能直接截图发回
        logView.setPadding(8, 12, 8, 12);
        logView.setBackgroundColor(0xFFF4F4F4);
        scroller.addView(logView);
        root.addView(scroller, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);
        append("点上面的按钮开始。\n"
                + "阶段 0 解释器 / 1 重依赖 / 2 ingest / 3 十二个端口\n"
                + "拉日志：adb exec-out run-as com.harmonica.probe cat files/run.log\n");
        diag("onCreate 结束");
    }

    @Override
    protected void onResume() {
        super.onResume();
        // ★ 界面每次回到前台都把当前状态吐一遍。★ 这解决了「只能靠截图
        // ★ 判断有没有点过」的老问题——★ 截图会被降采样，★ 而 logcat 不会。
        diag("onResume");
    }

    private void L(String s) {
        Log.i(TAG, s);
    }

    /**
     * dp → px。
     *
     * ★ 为什么现在才加：★ 改之前 root 的 padding 是【写死的 px】（24/32/24/24），
     * ★ 而那在 640dpi（density=2.0）的真机上只有 12dp/16dp ——★ 视觉上几乎
     * ★ 等于没有留白，★ 换台 density 不同的设备还会再变一次。
     * ★ 这正属于「只对一台机器成立」的那类写法，★ 而 insets 修好之后
     * ★ 留白就要真的承担排版责任了，★ 所以一并换成 dp。
     */
    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    /**
     * 一次把「按钮状态 + 窗口状态 + run.log + 屏幕上的文字」写进
     * logcat 与 files/ui_state.txt。
     *
     * ★ logcat 有单条长度上限，★ 所以 logcat 里那段屏幕文字截断到
     * ★ LOGCAT_TEXT_CAP；★ 落盘那份【不截断】。
     */
    private void diag(String reason) {
        StringBuilder sb = new StringBuilder();
        sb.append("=== diag ").append(reason).append(" ===\n");
        sb.append("pid=").append(android.os.Process.myPid())
          .append("  sdk=").append(android.os.Build.VERSION.SDK_INT).append("\n");
        if (runButton != null) {
            Rect r = new Rect();
            runButton.getGlobalVisibleRect(r);
            sb.append("button text=\"").append(runButton.getText()).append("\"\n")
              .append("  enabled=").append(runButton.isEnabled())
              .append(" clickable=").append(runButton.isClickable())
              .append(" focused=").append(runButton.isFocused())
              .append(" hasWindowFocus=").append(runButton.hasWindowFocus())
              .append(" visibility=").append(runButton.getVisibility())
              .append(" globalVisibleRect=[").append(r.left).append(",").append(r.top)
              .append("][").append(r.right).append(",").append(r.bottom).append("]\n");
        } else {
            sb.append("button = (尚未创建)\n");
        }
        if (getWindow() != null) {
            android.view.View decor = getWindow().getDecorView();
            sb.append("decor hasWindowFocus=").append(decor.hasWindowFocus())
              .append("  shown=").append(decor.isShown())
              .append("  decorSize=").append(decor.getWidth()).append("x").append(decor.getHeight())
              .append("\n");
        }
        java.io.File f = new java.io.File(getFilesDir(), "run.log");
        sb.append("run.log exists=").append(f.exists())
          .append("  len=").append(f.exists() ? f.length() : -1L).append("\n");
        String text = logView == null ? "(logView 为 null)" : logView.getText().toString();
        String cap = text.length() > LOGCAT_TEXT_CAP
                ? text.substring(0, LOGCAT_TEXT_CAP) + "…（截断，完整看 ui_state.txt）"
                : text;
        sb.append("--- 屏幕文字（logcat 版）---\n").append(cap)
          .append("\n--- 屏幕文字（完整）---\n").append(text)
          .append("\n--- 屏幕文字 结束 ---\n");

        String out = sb.toString();
        // ★ logcat 版给截断的，★ 落盘版给完整的——★ 免得把判定依据截没了。
        Log.i(TAG, "DIAG " + reason + "\n"
                + out.substring(0, Math.min(out.length(), 3000)));
        try (java.io.Writer w = new java.io.OutputStreamWriter(
                new java.io.FileOutputStream(new java.io.File(getFilesDir(), "ui_state.txt"), true),
                "UTF-8")) {
            w.write(out);
            w.write("\n");
        } catch (Throwable t) {
            Log.e(TAG, "★ diag 落盘失败：" + t);
        }
    }

    private void append(String s) {
        synchronized (buffer) {
            buffer.append(s);
            final String snapshot = buffer.toString();
            ui.post(() -> {
                logView.setText(snapshot);
                scroller.fullScroll(ScrollView.FOCUS_DOWN);
            });
        }
    }

    private void startProbe() {
        // ★ 这一行【不是】条件分支：★ 全文件只有 startProbe 自己会禁用按钮，
        // ★ 而恢复在下面的 finally。★ 所以按钮只有在【探针正在跑】时才不可点，
        // ★ 界面上刚打开时一定是 enabled=true。
        runButton.setEnabled(false);
        L("startProbe 进入  按钮已置灰（★ 只有跑探针期间才这样）");
        append("\n──────── 开始 ────────\n");
        // ★ 探针在后台线程跑，★ 否则 build_surface 十几秒会把界面卡死，
        // ★ 而那正是「看不出在等什么」的一种。
        new Thread(() -> {
            try {
                Python py = Python.getInstance();
                L("Python.getInstance() 成功  isStarted=" + Python.isStarted());
                PyObject mod = py.getModule("probe");
                L("★ getModule(\"probe\") 成功  ★ 探针模块确实在，★ 要开始跑了");
                // ★ run() 内部自己管日志与异常，★ 这里只负责把异常兜住，
                // ★ 免得 Java 侧只看到一个 null。
                mod.callAttr("run");
                L("★ probe.run() 正常返回");
            } catch (Throwable t) {
                L("★ Java 侧收到异常：" + t);
                append("★ Java 侧收到异常：\n" + t + "\n");
                StringWriterDump(t);
            } finally {
                try {
                    Python.getInstance().getModule("probe").callAttr("flush_log");
                    L("flush_log 成功");
                } catch (Throwable ignored) {
                    // ★ 落盘失败也不能让界面留着「跑完了」★ 那会误导
                    L("★ 日志落盘失败：" + ignored);
                    append("★ 日志落盘失败（★ 界面显示的仍然是真的）\n");
                }
                ui.post(() -> {
                    runButton.setEnabled(true);
                    append("──────── 结束 ────────\n");
                    L("★ 探针线程收尾  按钮已恢复 enabled=true");
                    diag("探针结束");
                });
            }
        }, "probe-thread").start();
    }

    private void StringWriterDump(Throwable t) {
        java.io.StringWriter sw = new java.io.StringWriter();
        t.printStackTrace(new java.io.PrintWriter(sw));
        L("★ 异常堆栈：\n" + sw);
        append(sw.toString());
    }
}
