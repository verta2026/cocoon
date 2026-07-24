package cocoon.guard

import cocoon.common.Net
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.view.Gravity
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class AppLockService : Service() {

    private var handler: Handler? = null
    private var handlerThread: HandlerThread? = null
    private var running = false
    private var blocklist = mutableSetOf<String>()
    private var overlayView: LinearLayout? = null
    private var wm: WindowManager? = null
    private var lastFetchMs = 0L
    private var lastFgPkg: String? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        handlerThread = HandlerThread("applock").also { it.start() }
        handler = Handler(handlerThread!!.looper)
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            running = false
            hideOverlay()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }

        if (intent?.action == ACTION_REFRESH) {
            if (!running) { stopSelf(); return START_NOT_STICKY } // 没在跑就别留僵尸
            handler?.post { fetchBlocklist() }
            return START_STICKY
        }

        val ch = NotificationChannel(CH_ID, "App lock", NotificationManager.IMPORTANCE_MIN)
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(ch)
        val notif = Notification.Builder(this, CH_ID)
            .setContentTitle(getString(R.string.guard_lock_active))
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setOngoing(true)
            .build()
        startForeground(NOTIF_ID, notif)

        running = true
        handler?.post { fetchBlocklist() }
        handler?.post(checkRunnable)
        return START_STICKY
    }

    private val checkRunnable = object : Runnable {
        override fun run() {
            if (!running) return
            checkForegroundApp()
            // Refresh blocklist every 30 seconds
            if (System.currentTimeMillis() - lastFetchMs > 30_000) {
                fetchBlocklist()
            }
            handler?.postDelayed(this, 1000)
        }
    }

    private fun checkForegroundApp() {
        if (blocklist.isEmpty()) {
            hideOverlayOnMain()
            return
        }
        if (!Report.usageAllowed(this)) return

        // queryEvents 取最近的 RESUMED 事件——queryUsageStats 的 lastTimeUsed 在很多 ROM 上滞后好几秒
        val usm = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val now = System.currentTimeMillis()
        val events = usm.queryEvents(now - 10_000, now)
        val ev = android.app.usage.UsageEvents.Event()
        var latest: String? = null
        while (events.hasNextEvent()) {
            events.getNextEvent(ev)
            if (ev.eventType == android.app.usage.UsageEvents.Event.ACTIVITY_RESUMED) {
                latest = ev.packageName
            }
        }
        // 10 秒窗口内没有 RESUMED 事件 = 前台没变，沿用上次结果（回桌面时 launcher 自己会 RESUMED）
        val fg = latest ?: lastFgPkg ?: return
        lastFgPkg = fg
        // Don't block ourselves
        if (fg == packageName) {
            hideOverlayOnMain()
            return
        }

        if (fg in blocklist) {
            showOverlayOnMain(fg)
        } else {
            hideOverlayOnMain()
        }
    }

    private fun showOverlayOnMain(pkg: String) {
        val label = try {
            packageManager.getApplicationLabel(
                packageManager.getApplicationInfo(pkg, 0)
            ).toString()
        } catch (e: Exception) { pkg.substringAfterLast('.') }

        Handler(mainLooper).post { showOverlay(label) }
    }

    private fun hideOverlayOnMain() {
        Handler(mainLooper).post { hideOverlay() }
    }

    private fun showOverlay(appName: String) {
        if (overlayView != null) {
            // Update text if already showing
            val tv = overlayView?.getChildAt(0) as? TextView
            tv?.text = getString(R.string.guard_locked_fmt, appName)
            return
        }

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#F0141110"))
        }

        val title = TextView(this).apply {
            text = getString(R.string.guard_locked_fmt, appName)
            setTextColor(Color.parseColor("#EDE4D6"))
            textSize = 20f
            gravity = Gravity.CENTER
            setPadding(48, 0, 48, 24)
        }

        val hint = TextView(this).apply {
            text = getString(R.string.guard_go_back)
            setTextColor(Color.parseColor("#C9A87F"))
            textSize = 14f
            gravity = Gravity.CENTER
        }

        layout.addView(title)
        layout.addView(hint)

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        )

        try {
            wm?.addView(layout, params)
            overlayView = layout
        } catch (e: Exception) {
            android.util.Log.e("AppLock", "overlay addView failed (permission?): ${e.message}")
        }
    }

    private fun hideOverlay() {
        overlayView?.let {
            try { wm?.removeView(it) } catch (_: Exception) {}
            overlayView = null
        }
    }

    private fun fetchBlocklist() {
        try {
            val tok = Net.token(this)
            if (tok.isEmpty()) return
            val conn = URL(
                "${Net.BASE}/widget/applock?token=${URLEncoder.encode(tok, "UTF-8")}"
            ).openConnection() as HttpURLConnection
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            val text = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            // 服务器 GET 返回字符串化数组、POST 返回真数组——两种都认，谁改一边都不断
            val obj = org.json.JSONObject(text)
            val arr = obj.optJSONArray("blocked") ?: JSONArray(obj.getString("blocked"))
            val newList = mutableSetOf<String>()
            for (i in 0 until arr.length()) newList.add(arr.getString(i))
            blocklist = newList
            lastFetchMs = System.currentTimeMillis()
        } catch (e: Exception) {
            android.util.Log.e("AppLock", "fetchBlocklist failed: ${e.message}")
        }
    }

    override fun onDestroy() {
        running = false
        hideOverlay()
        handlerThread?.quitSafely()
        super.onDestroy()
    }

    companion object {
        const val CH_ID = "app_lock"
        const val NOTIF_ID = 43
        const val ACTION_STOP = "cocoon.guard.STOP_APP_LOCK"
        const val ACTION_REFRESH = "cocoon.guard.REFRESH_APP_LOCK"

        fun start(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, AppLockService::class.java))
        }

        fun stop(ctx: Context) {
            ctx.startService(Intent(ctx, AppLockService::class.java).apply {
                action = ACTION_STOP
            })
        }

        fun refresh(ctx: Context) {
            ctx.startService(Intent(ctx, AppLockService::class.java).apply {
                action = ACTION_REFRESH
            })
        }
    }
}
