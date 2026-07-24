package cocoon.widgets

import cocoon.common.Net
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.widget.RemoteViews
import kotlin.concurrent.thread

class HeartWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        thread {
            try { for (id in ids) update(context, mgr, id) } finally { pending.finish() }
        }
    }

    private fun update(context: Context, mgr: AppWidgetManager, id: Int) {
        val views = RemoteViews(context.packageName, R.layout.widget_heart)
        views.setOnClickPendingIntent(
            R.id.heart_root,
            PendingIntent.getActivity(context, 0, cocoon.common.appLaunchIntent(context),
                PendingIntent.FLAG_IMMUTABLE)
        )
        val j = Net.get(context, "/widget/heartrate")
        val bpm = j?.optInt("bpm", -1) ?: -1
        if (bpm <= 0) {
            views.setTextViewText(R.id.heart_bpm, "…")
            views.setTextViewText(R.id.heart_sub, "offline")
        } else {
            views.setTextViewText(R.id.heart_bpm, "$bpm")
            views.setTextViewText(R.id.heart_sub,
                if (j?.optBoolean("stale") == true) "bpm (stale)" else "bpm")
            val arr = j?.optJSONArray("today")
            if (arr != null && arr.length() >= 2) {
                views.setImageViewBitmap(R.id.heart_chart, sparkline(arr.let {
                    IntArray(it.length()) { i -> it.optInt(i) }
                }))
            }
        }
        mgr.updateAppWidget(id, views)
    }

    private fun sparkline(vals: IntArray): Bitmap {
        val w = 320; val h = 72; val pad = 6f
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val lo = vals.min().toFloat(); val hi = vals.max().toFloat()
        val span = if (hi - lo < 1f) 1f else hi - lo
        val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = 0xFF7EB37C.toInt(); strokeWidth = 3f; style = Paint.Style.STROKE
        }
        val path = Path()
        for (i in vals.indices) {
            val x = pad + (w - 2 * pad) * i / (vals.size - 1)
            val y = h - pad - (h - 2 * pad) * (vals[i] - lo) / span
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        c.drawPath(path, p)
        return bmp
    }
}
