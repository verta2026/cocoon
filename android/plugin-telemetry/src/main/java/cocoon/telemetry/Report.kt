package cocoon.telemetry

// 手机状态原生上报：电量 / 位置 / 屏幕使用时间 → POST /widget/phone。
// 每样各自探权限，缺哪样跳哪样——不因为一个权限没给就整包不发。
// Tasker App Changed 那条 hack 的接班人。

import android.Manifest
import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.BatteryManager
import android.os.Process
import cocoon.common.Net
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar
import kotlin.concurrent.thread

object Report {

    fun sendAsync(ctx: Context) {
        val app = ctx.applicationContext
        thread { send(app) }
    }

    fun send(ctx: Context) {
        val body = JSONObject()
        battery(ctx)?.let { body.put("battery", it) }
        location(ctx)?.let { body.put("loc", it) }
        usage(ctx)?.let { body.put("screen", it) }
        Hc.collect(ctx)?.let { body.put("hc", it) }
        if (body.length() > 0) Net.post(ctx, "/widget/phone", body)
    }

    private fun battery(ctx: Context): JSONObject? = try {
        val i = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = i?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = i?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val status = i?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        if (level < 0 || scale <= 0) null else JSONObject()
            .put("pct", level * 100 / scale)
            .put("charging", status == BatteryManager.BATTERY_STATUS_CHARGING ||
                             status == BatteryManager.BATTERY_STATUS_FULL)
    } catch (e: Exception) { null }

    // lastKnownLocation 够用：别的 app 常在定位，捡现成的不额外耗电。
    // age_min 带上——旧坐标要能被识别出旧
    private fun location(ctx: Context): JSONObject? {
        val fine = ctx.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) ==
                   PackageManager.PERMISSION_GRANTED
        val coarse = ctx.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) ==
                     PackageManager.PERMISSION_GRANTED
        if (!fine && !coarse) return null
        return try {
            val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            var best: android.location.Location? = null
            for (p in lm.allProviders) {
                val l = try { lm.getLastKnownLocation(p) } catch (e: SecurityException) { null }
                    ?: continue
                if (best == null || l.time > best!!.time) best = l
            }
            best?.let {
                JSONObject()
                    .put("lat", Math.round(it.latitude * 1e5) / 1e5)
                    .put("lon", Math.round(it.longitude * 1e5) / 1e5)
                    .put("acc", it.accuracy.toInt())
                    .put("age_min", ((System.currentTimeMillis() - it.time) / 60000).toInt())
            }
        } catch (e: Exception) { null }
    }

    fun usageAllowed(ctx: Context): Boolean {
        val ops = ctx.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        return ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(), ctx.packageName) == AppOpsManager.MODE_ALLOWED
    }

    private fun usage(ctx: Context): JSONObject? {
        if (!usageAllowed(ctx)) return null
        return try {
            val usm = ctx.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            val dayStart = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
            }.timeInMillis
            val stats = usm.queryUsageStats(
                UsageStatsManager.INTERVAL_DAILY, dayStart, System.currentTimeMillis())
                ?: return null
            val agg = HashMap<String, Long>()
            for (s in stats) if (s.totalTimeInForeground > 0)
                agg.merge(s.packageName, s.totalTimeInForeground) { a, b -> a + b }
            if (agg.isEmpty()) return null
            val pm = ctx.packageManager
            val top = JSONArray()
            agg.entries.sortedByDescending { it.value }.take(8).forEach { e ->
                val label = try {
                    pm.getApplicationLabel(pm.getApplicationInfo(e.key, 0)).toString()
                } catch (ex: Exception) { e.key.substringAfterLast('.') }
                top.put(JSONObject().put("app", label).put("min", e.value / 60000))
            }
            JSONObject()
                .put("total_min", agg.values.sum() / 60000)
                .put("top", top)
        } catch (e: Exception) { null }
    }
}
