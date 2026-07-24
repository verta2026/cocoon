package cocoon.telemetry

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.health.connect.client.PermissionController
import cocoon.common.CocoonPlugin

/**
 * Phone-state reporting: battery / location / screen time / Health Connect,
 * posted to /widget/phone on a 15-minute inexact alarm plus every app-open.
 * Permission prompts each ask exactly once; everything stays optional.
 */
object TelemetryPlugin : CocoonPlugin {

    private const val REQ_HC = 100
    private const val REQ_LOC = 101
    private const val REQ_BGLOC = 102

    override fun onMainCreate(activity: Activity) {
        ReportReceiver.schedule(activity)
        askPermissions(activity)
    }

    override fun onMainResume(activity: Activity) {
        Report.sendAsync(activity) // location is freshest right when the app opens
    }

    override fun onTokenSaved(ctx: Context) {
        Report.sendAsync(ctx)
    }

    override fun onWebViewReady(activity: Activity, web: WebView) {
        // The health page calls window.AndroidHealth to check/request HC access
        web.addJavascriptInterface(HealthBridge(activity), "AndroidHealth")
    }

    override fun onActivityResult(
        activity: Activity, requestCode: Int, resultCode: Int, data: Intent?
    ): Boolean {
        if (requestCode != REQ_HC) return false
        Report.sendAsync(activity) // report immediately once granted
        return true
    }

    override fun onPermissionsResult(activity: Activity, requestCode: Int, grantResults: IntArray) {
        if (requestCode == REQ_LOC &&
            grantResults.any { it == PackageManager.PERMISSION_GRANTED }) {
            Report.sendAsync(activity)
            askPermissions(activity) // foreground granted — follow up with background
        }
    }

    private fun askPermissions(activity: Activity) {
        val prefs = activity.getSharedPreferences("cocoon", Context.MODE_PRIVATE)
        val fineOk = activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) ==
                     PackageManager.PERMISSION_GRANTED
        if (!fineOk) {
            if (!prefs.getBoolean("asked_loc", false)) {
                prefs.edit().putBoolean("asked_loc", true).apply()
                activity.requestPermissions(arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION), REQ_LOC)
            }
        } else if (activity.checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION) !=
                   PackageManager.PERMISSION_GRANTED &&
                   !prefs.getBoolean("asked_bgloc", false)) {
            prefs.edit().putBoolean("asked_bgloc", true).apply()
            AlertDialog.Builder(activity)
                .setMessage(R.string.telemetry_bgloc_rationale)
                .setPositiveButton(android.R.string.ok) { _, _ ->
                    try {
                        activity.requestPermissions(
                            arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION), REQ_BGLOC)
                    } catch (e: Exception) {}
                }
                .setNegativeButton(android.R.string.cancel) { _, _ -> }
                .show()
        }
        if (Hc.available(activity) && !prefs.getBoolean("asked_hc", false)) {
            Thread {
                if (!Hc.grantedAny(activity)) activity.runOnUiThread {
                    prefs.edit().putBoolean("asked_hc", true).apply()
                    launchHealthPermission(activity)
                }
            }.start()
        }
        if (!Report.usageAllowed(activity) && !prefs.getBoolean("asked_usage", false)) {
            prefs.edit().putBoolean("asked_usage", true).apply()
            AlertDialog.Builder(activity)
                .setMessage(R.string.telemetry_usage_rationale)
                .setPositiveButton(android.R.string.ok) { _, _ ->
                    try { activity.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) }
                    catch (e: Exception) {}
                }
                .setNegativeButton(android.R.string.cancel) { _, _ -> }
                .show()
        }
    }

    /** Launch Health Connect authorization, falling back through settings pages so
     *  the "grant" action always opens something, whatever the ROM. */
    fun launchHealthPermission(activity: Activity) {
        try {
            val contract = PermissionController.createRequestPermissionResultContract()
            activity.startActivityForResult(contract.createIntent(activity, Hc.PERMS), REQ_HC)
            return
        } catch (e: Exception) {}
        try {
            activity.startActivity(Intent("androidx.health.ACTION_HEALTH_CONNECT_SETTINGS"))
            return
        } catch (e: Exception) {}
        try {
            activity.packageManager.getLaunchIntentForPackage("com.google.android.apps.healthdata")
                ?.let { activity.startActivity(it) }
        } catch (e: Exception) {}
    }

    class HealthBridge(private val activity: Activity) {
        @JavascriptInterface
        fun available(): Boolean = Hc.available(activity)
        @JavascriptInterface
        fun granted(): Boolean = Hc.grantedAny(activity)
        @JavascriptInterface
        fun request() { activity.runOnUiThread { launchHealthPermission(activity) } }
    }
}
