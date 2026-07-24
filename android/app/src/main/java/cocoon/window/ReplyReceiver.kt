package cocoon.window

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.RemoteInput
import cocoon.common.Net
import org.json.JSONObject
import kotlin.concurrent.thread

class ReplyReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val text = RemoteInput.getResultsFromIntent(intent)
            ?.getCharSequence(KEY_REPLY)?.toString() ?: return
        val notifId = intent.getIntExtra("notif_id", 0)
        val mgr = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val updating = NotificationCompat.Builder(ctx, FcmService.CH_MSG)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentText(ctx.getString(R.string.reply_sending))
            .build()
        mgr.notify(notifId, updating)
        // goAsync: without it the process may be reclaimed as soon as onReceive
        // returns, losing the reply mid-flight
        val pending = goAsync()
        thread {
            try {
                val ok = Net.post(ctx, "/widget/reply",
                    JSONObject().put("text", text))
                val result = NotificationCompat.Builder(ctx, FcmService.CH_MSG)
                    .setSmallIcon(R.mipmap.ic_launcher)
                    .setContentText(if (ok != null)
                        ctx.getString(R.string.reply_sent, text)
                    else ctx.getString(R.string.reply_failed))
                    .setAutoCancel(true)
                    .build()
                mgr.notify(notifId, result)
            } finally { pending.finish() }
        }
    }

    companion object {
        const val KEY_REPLY = "quick_reply"
        const val ACTION = "cocoon.window.QUICK_REPLY"
    }
}
