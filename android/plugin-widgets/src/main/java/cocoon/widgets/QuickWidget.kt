package cocoon.widgets

import cocoon.common.Net
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.widget.RemoteViews
import android.widget.Toast
import org.json.JSONObject
import kotlin.concurrent.thread

class QuickWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        for (id in ids) update(context, mgr, id)
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_SEND) {
            val kind = intent.getStringExtra("kind") ?: return
            val pending = goAsync()
            thread {
                try {
                    val j = Net.post(context, "/widget/poke", JSONObject().put("kind", kind))
                    val msg = j?.optString("note")?.takeIf { it.isNotBlank() } ?: "…"
                    Handler(Looper.getMainLooper()).post {
                        Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
                    }
                } finally { pending.finish() }
            }
        }
    }

    private fun update(context: Context, mgr: AppWidgetManager, id: Int) {
        val views = RemoteViews(context.packageName, R.layout.widget_quick)
        val pairs = listOf(
            R.id.quick_kiss to "kiss",
            R.id.quick_miss to "miss",
            R.id.quick_hug to "hug",
            R.id.quick_harvest to "harvest",
        )
        for ((i, p) in pairs.withIndex()) {
            views.setOnClickPendingIntent(p.first,
                PendingIntent.getBroadcast(context, 200 + i,
                    Intent(context, QuickWidget::class.java)
                        .setAction(ACTION_SEND).putExtra("kind", p.second),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        }
        mgr.updateAppWidget(id, views)
    }

    companion object {
        const val ACTION_SEND = "cocoon.widgets.QUICK_SEND"
    }
}
