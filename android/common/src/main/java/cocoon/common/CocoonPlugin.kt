package cocoon.common

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.webkit.WebView

/**
 * Contract between the core shell and optional feature plugins.
 *
 * A plugin module implements this as a Kotlin `object` named:
 *   cocoon.<feature>.<Feature>Plugin
 * and the core discovers it reflectively (see [Plugins]) — so a missing
 * module is simply skipped, never a compile or runtime error.
 *
 * Request-code convention (to keep onActivityResult routing unambiguous):
 *   core 70..99, telemetry 100..119, guard 120..139.
 */
interface CocoonPlugin {
    /** Handle an FCM data message of the given kind. Return true if consumed. */
    fun onFcm(ctx: Context, kind: String, data: Map<String, String>): Boolean = false

    /** One-time setup on app launch: permission prompts, alarm scheduling, service starts. */
    fun onMainCreate(activity: Activity) {}

    /** Every foreground return: refresh services, send reports, update widgets. */
    fun onMainResume(activity: Activity) {}

    /** WebView is configured — register JavaScript interfaces here. */
    fun onWebViewReady(activity: Activity, web: WebView) {}

    /** Route an activity result. Return true if the request code belonged to this plugin. */
    fun onActivityResult(activity: Activity, requestCode: Int, resultCode: Int, data: Intent?): Boolean = false

    /** Runtime-permission dialog results, forwarded from the main activity. */
    fun onPermissionsResult(activity: Activity, requestCode: Int, grantResults: IntArray) {}

    /** The bridge token was (re)saved — a good moment to send any deferred reports. */
    fun onTokenSaved(ctx: Context) {}
}

object Plugins {
    private val CANDIDATES = listOf(
        "cocoon.widgets.WidgetsPlugin",
        "cocoon.guard.GuardPlugin",
        "cocoon.call.CallPlugin",
        "cocoon.telemetry.TelemetryPlugin",
    )

    val all: List<CocoonPlugin> by lazy {
        CANDIDATES.mapNotNull { name ->
            runCatching {
                Class.forName(name).getDeclaredField("INSTANCE").get(null) as CocoonPlugin
            }.getOrNull()
        }
    }

    fun fcm(ctx: Context, kind: String, data: Map<String, String>): Boolean =
        all.any { runCatching { it.onFcm(ctx, kind, data) }.getOrDefault(false) }
}
