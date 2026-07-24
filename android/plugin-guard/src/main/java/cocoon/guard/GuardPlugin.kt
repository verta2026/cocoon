package cocoon.guard

import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.provider.Settings
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.core.app.NotificationCompat
import cocoon.common.CocoonPlugin

/**
 * Remote guard features: app lock (blocklist + overlay) and screen share
 * (MediaProjection frames posted to the bridge). Both are consent-first:
 * the lock needs the overlay permission granted by hand, the screen share
 * needs the system capture dialog accepted for every session.
 */
object GuardPlugin : CocoonPlugin {

    private const val REQ_SCREEN = 120
    private const val CH_MSG = "cocoon_msg" // reuse the core message channel

    private var web: WebView? = null
    private var interval = 60000L

    override fun onFcm(ctx: Context, kind: String, data: Map<String, String>): Boolean {
        when (kind) {
            "lock" -> {
                AppLockService.start(ctx)
                AppLockService.refresh(ctx)
                return true
            }
            "unlock" -> {
                AppLockService.refresh(ctx)
                return true
            }
            "screen" -> {
                // Capture needs the user through the system dialog — open the app's
                // screen page; the tap is also what legitimizes the activity start.
                val launch = ctx.packageManager.getLaunchIntentForPackage(ctx.packageName)
                    ?.apply {
                        putExtra("open", "/screen.html?auto=1")
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                    } ?: return true
                val open = PendingIntent.getActivity(ctx, 2, launch,
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
                val n = NotificationCompat.Builder(ctx, CH_MSG)
                    .setSmallIcon(android.R.drawable.ic_menu_view)
                    .setContentTitle(ctx.getString(R.string.guard_screen_request))
                    .setContentText(data["body"] ?: ctx.getString(R.string.guard_screen_request_body))
                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                    .setContentIntent(open)
                    .setAutoCancel(true)
                    .build()
                (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                    .notify(System.currentTimeMillis().toInt(), n)
                return true
            }
        }
        return false
    }

    override fun onMainCreate(activity: Activity) {
        // Without the overlay permission the whole lock chain goes silently dead —
        // ask once, with a pointer to the right settings page.
        val prefs = activity.getSharedPreferences("cocoon", Context.MODE_PRIVATE)
        if (!Settings.canDrawOverlays(activity) && !prefs.getBoolean("asked_overlay", false)) {
            prefs.edit().putBoolean("asked_overlay", true).apply()
            AlertDialog.Builder(activity)
                .setMessage(R.string.guard_overlay_rationale)
                .setPositiveButton(android.R.string.ok) { _, _ ->
                    try {
                        activity.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                            Uri.parse("package:${activity.packageName}")))
                    } catch (e: Exception) {}
                }
                .setNegativeButton(android.R.string.cancel) { _, _ -> }
                .show()
        }
    }

    override fun onMainResume(activity: Activity) {
        // The permission may have just been granted in settings — start without a relaunch
        if (Settings.canDrawOverlays(activity)) AppLockService.start(activity)
    }

    override fun onWebViewReady(activity: Activity, web: WebView) {
        this.web = web
        web.addJavascriptInterface(ScreenShareBridge(activity), "AndroidScreenShare")
    }

    override fun onActivityResult(
        activity: Activity, requestCode: Int, resultCode: Int, data: Intent?
    ): Boolean {
        if (requestCode != REQ_SCREEN) return false
        if (resultCode == Activity.RESULT_OK && data != null) {
            val intent = Intent(activity, ScreenShareService::class.java).apply {
                putExtra(ScreenShareService.EXTRA_RESULT_CODE, resultCode)
                putExtra(ScreenShareService.EXTRA_RESULT_DATA, data)
                putExtra(ScreenShareService.EXTRA_INTERVAL, interval)
            }
            activity.startForegroundService(intent)
            web?.evaluateJavascript(
                "window.dispatchEvent(new CustomEvent('screenshare', {detail:{active:true}}))", null)
        }
        return true
    }

    class ScreenShareBridge(private val activity: Activity) {
        @JavascriptInterface
        fun start(intervalMs: Long) {
            interval = if (intervalMs < 1000) 60000L else intervalMs
            activity.runOnUiThread {
                val mpm = activity.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
                    as MediaProjectionManager
                activity.startActivityForResult(mpm.createScreenCaptureIntent(), REQ_SCREEN)
            }
        }
        @JavascriptInterface
        fun start() = start(60000L)
        @JavascriptInterface
        fun stop() { ScreenShareService.stop(activity) }
    }
}
