package cocoon.widgets

import cocoon.common.Net
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.widget.RemoteViews
import android.widget.Toast
import org.json.JSONObject
import kotlin.concurrent.thread

// health 快记：桌面一按记一杯水 / 标经期。服务端认"今天"这个键，
// 按完刷新标题上的杯数。数据落云端 health.json，和网页 health 页同源。
class HealthWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        thread {
            try { for (id in ids) update(context, mgr, id) } finally { pending.finish() }
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_QUICK) {
            val act = intent.getStringExtra("act") ?: return
            val pending = goAsync()
            thread {
                try {
                    val j = Net.post(context, "/widget/health/quick", JSONObject().put("act", act))
                    val msg = j?.optString("note")?.takeIf { it.isNotBlank() } ?: "…"
                    Handler(Looper.getMainLooper()).post {
                        Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
                    }
                    val mgr = AppWidgetManager.getInstance(context)
                    for (id in mgr.getAppWidgetIds(ComponentName(context, HealthWidget::class.java)))
                        update(context, mgr, id)
                } finally { pending.finish() }
            }
        }
    }

    private fun update(context: Context, mgr: AppWidgetManager, id: Int) {
        val views = RemoteViews(context.packageName, R.layout.widget_health)
        views.setOnClickPendingIntent(R.id.health_water,
            PendingIntent.getBroadcast(context, 300,
                Intent(context, HealthWidget::class.java)
                    .setAction(ACTION_QUICK).putExtra("act", "water"),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        views.setOnClickPendingIntent(R.id.health_period,
            PendingIntent.getBroadcast(context, 301,
                Intent(context, HealthWidget::class.java)
                    .setAction(ACTION_QUICK).putExtra("act", "period"),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        views.setOnClickPendingIntent(R.id.health_title,
            PendingIntent.getActivity(context, 0, cocoon.common.appLaunchIntent(context),
                PendingIntent.FLAG_IMMUTABLE))
        val j = Net.get(context, "/widget/health")
        val data = j?.optJSONObject("data")
        val today = java.text.SimpleDateFormat("yyyy-MM-dd").apply {
            timeZone = java.util.TimeZone.getDefault()
        }.format(java.util.Date())
        val rec = data?.optJSONObject(today)
        val water = rec?.optInt("water", 0) ?: 0
        val period = if (rec?.optBoolean("period") == true) " · period" else ""
        views.setTextViewText(R.id.health_title, context.getString(R.string.widget_health_fmt, water) + period)
        mgr.updateAppWidget(id, views)
    }

    companion object {
        const val ACTION_QUICK = "cocoon.widgets.HEALTH_QUICK"
    }
}
