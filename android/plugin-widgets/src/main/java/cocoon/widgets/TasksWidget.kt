package cocoon.widgets

import cocoon.common.Net
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import org.json.JSONObject
import kotlin.concurrent.thread

class TasksWidget : AppWidgetProvider() {

    private val rowIds = intArrayOf(R.id.task_row0, R.id.task_row1, R.id.task_row2, R.id.task_row3)
    private val textIds = intArrayOf(R.id.task_text0, R.id.task_text1, R.id.task_text2, R.id.task_text3)
    private val boxIds = intArrayOf(R.id.task_box0, R.id.task_box1, R.id.task_box2, R.id.task_box3)

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        thread {
            try { for (id in ids) update(context, mgr, id) } finally { pending.finish() }
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_DONE) {
            val idx = intent.getIntExtra("index", -1)
            if (idx >= 0) {
                val pending = goAsync()
                thread {
                    try {
                        Net.post(context, "/widget/tasks/done", JSONObject().put("index", idx))
                        val mgr = AppWidgetManager.getInstance(context)
                        for (id in mgr.getAppWidgetIds(ComponentName(context, TasksWidget::class.java)))
                            update(context, mgr, id)
                    } finally { pending.finish() }
                }
            }
        }
    }

    private fun update(context: Context, mgr: AppWidgetManager, id: Int) {
        val views = RemoteViews(context.packageName, R.layout.widget_tasks)
        views.setOnClickPendingIntent(
            R.id.tasks_title,
            PendingIntent.getActivity(context, 0, cocoon.common.appLaunchIntent(context),
                PendingIntent.FLAG_IMMUTABLE)
        )
        val j = Net.get(context, "/widget/tasks")
        val items = j?.optJSONArray("items")
        for (r in 0 until 4) {
            if (items != null && r < items.length()) {
                val it = items.optJSONObject(r)
                val done = it.optBoolean("done")
                views.setViewVisibility(rowIds[r], View.VISIBLE)
                views.setTextViewText(textIds[r], it.optString("text"))
                views.setImageViewResource(boxIds[r],
                    if (done) R.drawable.checkbox_done else R.drawable.checkbox_empty)
                views.setTextColor(textIds[r],
                    if (done) 0xFF9B8672.toInt() else 0xFF4A382A.toInt())
                views.setOnClickPendingIntent(rowIds[r],
                    PendingIntent.getBroadcast(context, 100 + r,
                        Intent(context, TasksWidget::class.java)
                            .setAction(ACTION_DONE).putExtra("index", it.optInt("index")),
                        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            } else {
                views.setViewVisibility(rowIds[r], View.GONE)
            }
        }
        if (items == null || items.length() == 0) {
            views.setViewVisibility(rowIds[0], View.VISIBLE)
            views.setTextViewText(textIds[0], context.getString(R.string.widget_tasks_empty))
        }
        mgr.updateAppWidget(id, views)
    }

    companion object {
        const val ACTION_DONE = "cocoon.widgets.TASK_DONE"
    }
}
