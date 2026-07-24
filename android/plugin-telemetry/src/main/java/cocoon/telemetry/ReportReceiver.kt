package cocoon.telemetry

// 后台上报节拍：15 分钟一次的不精确闹钟（OPPO 杀后台，精确闹钟也活不长，
// 不如省电换活得久）。开机重挂闹钟，app 打开时 MainActivity.onResume 另有即时上报。

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import kotlin.concurrent.thread

class ReportReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            schedule(context)
            return
        }
        // exported=true（BOOT 需要），只认自己的 action——不给第三方显式 intent 触发上报的口子
        if (intent.action != ACTION) return
        val pending = goAsync()
        val app = context.applicationContext
        thread {
            try { Report.send(app) } finally { pending.finish() }
        }
    }

    companion object {
        private const val ACTION = "cocoon.telemetry.REPORT"

        fun schedule(ctx: Context) {
            val am = ctx.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val pi = PendingIntent.getBroadcast(
                ctx, 0,
                Intent(ctx, ReportReceiver::class.java).setAction(ACTION),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            am.setInexactRepeating(
                AlarmManager.ELAPSED_REALTIME,
                SystemClock.elapsedRealtime() + AlarmManager.INTERVAL_FIFTEEN_MINUTES,
                AlarmManager.INTERVAL_FIFTEEN_MINUTES, pi)
        }
    }
}
