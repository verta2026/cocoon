package cocoon.widgets

import cocoon.common.Net
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import org.json.JSONObject
import kotlin.concurrent.thread

class StatusWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        thread {
            try { for (id in ids) update(context, mgr, id) } finally { pending.finish() }
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        when (intent.action) {
            ACTION_POKE -> {
                val pending = goAsync()
                thread {
                    try {
                        Net.post(context, "/widget/poke", JSONObject())
                        refreshAll(context)
                    } finally { pending.finish() }
                }
            }
            ACTION_REFRESH -> {
                val pending = goAsync()
                thread {
                    try { refreshAll(context) } finally { pending.finish() }
                }
            }
        }
    }

    private fun refreshAll(context: Context) {
        val mgr = AppWidgetManager.getInstance(context)
        val ids = mgr.getAppWidgetIds(ComponentName(context, StatusWidget::class.java))
        for (id in ids) update(context, mgr, id)
    }

    private fun update(context: Context, mgr: AppWidgetManager, id: Int) {
        val views = RemoteViews(context.packageName, R.layout.widget_status)
        views.setOnClickPendingIntent(
            R.id.widget_root,
            PendingIntent.getActivity(context, 0, cocoon.common.appLaunchIntent(context),
                PendingIntent.FLAG_IMMUTABLE)
        )
        views.setOnClickPendingIntent(
            R.id.widget_state,
            PendingIntent.getBroadcast(context, 2,
                Intent(context, StatusWidget::class.java).setAction(ACTION_REFRESH),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        )
        views.setOnClickPendingIntent(
            R.id.widget_poke,
            PendingIntent.getBroadcast(context, 1,
                Intent(context, StatusWidget::class.java).setAction(ACTION_POKE),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        )
        // 同步执行：调用方（onUpdate/onReceive）已在 goAsync 保护的线程里
        if (Net.token(context).isEmpty()) {
            views.setTextViewText(R.id.widget_state, context.getString(R.string.widget_login_hint))
            views.setTextViewText(R.id.widget_note, "")
        } else {
            val j = Net.get(context, "/widget/state")
            views.setTextViewText(R.id.widget_state, stateLabel(j?.optString("state")))
            views.setTextViewText(R.id.widget_note, j?.optString("note") ?: "…")
        }
        mgr.updateAppWidget(id, views)
    }

    private fun stateLabel(s: String?): String = when (s) {
        "online" -> "Online"
        "thinking" -> "Thinking"
        "working" -> "Working"
        "sleeping" -> "Napping"
        null, "", "unknown" -> "…"
        else -> s
    }

    companion object {
        const val ACTION_POKE = "cocoon.widgets.POKE"
        const val ACTION_REFRESH = "cocoon.widgets.REFRESH_STATUS"
    }
}
