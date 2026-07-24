package cocoon.widgets

import android.app.Activity
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Intent
import cocoon.common.CocoonPlugin

/** Home-screen widgets. The providers are declared in this module's manifest;
 *  the only cross-cutting concern is refreshing them whenever the app opens. */
object WidgetsPlugin : CocoonPlugin {

    override fun onMainResume(activity: Activity) {
        val mgr = AppWidgetManager.getInstance(activity)
        for (cls in listOf(StatusWidget::class.java, HeartWidget::class.java,
                           ReminderWidget::class.java, TasksWidget::class.java,
                           QuickWidget::class.java, HealthWidget::class.java,
                           MailboxWidget::class.java)) {
            val ids = mgr.getAppWidgetIds(ComponentName(activity, cls))
            if (ids.isNotEmpty()) {
                activity.sendBroadcast(Intent(activity, cls)
                    .setAction(AppWidgetManager.ACTION_APPWIDGET_UPDATE)
                    .putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids))
            }
        }
    }
}
