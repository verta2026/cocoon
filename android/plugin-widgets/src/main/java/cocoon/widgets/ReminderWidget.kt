package cocoon.widgets

import cocoon.common.Net
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import kotlin.concurrent.thread

class ReminderWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        thread {
            try { for (id in ids) update(context, mgr, id) } finally { pending.finish() }
        }
    }

    private fun update(context: Context, mgr: AppWidgetManager, id: Int) {
        val views = RemoteViews(context.packageName, R.layout.widget_reminder)
        views.setOnClickPendingIntent(
            R.id.reminder_root,
            PendingIntent.getActivity(context, 0, cocoon.common.appLaunchIntent(context),
                PendingIntent.FLAG_IMMUTABLE)
        )
        val j = Net.get(context, "/widget/reminder")
        views.setTextViewText(R.id.reminder_label, j?.optString("label") ?: "…")
        views.setTextViewText(R.id.reminder_at, j?.optString("at") ?: "")
        mgr.updateAppWidget(id, views)
    }
}
