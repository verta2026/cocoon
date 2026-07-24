package cocoon.widgets

import cocoon.common.Net
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import kotlin.concurrent.thread

// 便签墙一览：显示墙上最新一条，点"贴张便签"打开 app 到 mailbox 页写。
// 记录本身走网页（要输入法），小组件只做入口 + 最新预览。
class MailboxWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        thread {
            try { for (id in ids) update(context, mgr, id) } finally { pending.finish() }
        }
    }

    private fun update(context: Context, mgr: AppWidgetManager, id: Int) {
        val views = RemoteViews(context.packageName, R.layout.widget_mailbox)
        val open = cocoon.common.appLaunchIntent(context).putExtra("open", "/mailbox.html")
            .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pi = PendingIntent.getActivity(context, 400, open, PendingIntent.FLAG_IMMUTABLE)
        views.setOnClickPendingIntent(R.id.mail_add, pi)
        views.setOnClickPendingIntent(R.id.mail_title, pi)
        views.setOnClickPendingIntent(R.id.mail_latest, pi)
        val j = Net.get(context, "/widget/mailbox")
        val notes = j?.optJSONArray("notes")
        if (notes != null && notes.length() > 0) {
            val last = notes.optJSONObject(notes.length() - 1)
            val who = last.optString("author")
            views.setTextViewText(R.id.mail_latest, "$who: " + last.optString("text"))
            val unread = j.optInt("unread_leta", 0)
            views.setTextViewText(R.id.mail_title,
                if (unread > 0) context.getString(R.string.widget_mailbox_new, unread) else context.getString(R.string.widget_mailbox))
        } else {
            views.setTextViewText(R.id.mail_latest, context.getString(R.string.widget_mailbox_empty))
        }
        mgr.updateAppWidget(id, views)
    }
}
