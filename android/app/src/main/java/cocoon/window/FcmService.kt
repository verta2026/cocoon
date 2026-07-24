package cocoon.window

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.provider.AlarmClock
import androidx.core.app.NotificationCompat
import cocoon.common.Net
import cocoon.common.Plugins
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlin.concurrent.thread

/**
 * FCM entry point. Data-message contract:
 *   kind=alarm             -> set an alarm in the system clock app (core, below)
 *   kind=lock/unlock/screen/call -> offered to feature plugins via Plugins.fcm()
 *   anything else          -> high-priority notification with inline quick-reply
 * Token changes are reported to the bridge at /widget/fcm_token.
 */
class FcmService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        thread {
            Net.post(applicationContext, "/widget/fcm_token",
                org.json.JSONObject().put("token", token))
        }
    }

    override fun onMessageReceived(msg: RemoteMessage) {
        val kind = msg.data["kind"] ?: msg.data["type"] ?: "msg"
        ensureChannels()
        val mgr = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (kind == "alarm") {
            val hour = msg.data["hour"]?.toIntOrNull() ?: return
            val minutes = msg.data["minutes"]?.toIntOrNull() ?: 0
            val label = msg.data["label"] ?: msg.data["body"] ?: getString(R.string.app_name)
            val alarm = Intent(AlarmClock.ACTION_SET_ALARM).apply {
                putExtra(AlarmClock.EXTRA_HOUR, hour)
                putExtra(AlarmClock.EXTRA_MINUTES, minutes)
                putExtra(AlarmClock.EXTRA_MESSAGE, label)
                putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                putExtra(AlarmClock.EXTRA_VIBRATE, true)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            // Android 10+ blocks background activity starts: set directly when the app
            // is foreground; otherwise post a tappable notification — the tap is the
            // user interaction that lets the alarm intent through.
            val fg = try {
                val am = getSystemService(Context.ACTIVITY_SERVICE) as android.app.ActivityManager
                am.runningAppProcesses?.any {
                    it.pid == android.os.Process.myPid() &&
                    it.importance <= android.app.ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND
                } ?: false
            } catch (e: Exception) { false }
            val timeText = "${hour}:${minutes.toString().padStart(2, '0')}"
            if (fg) {
                startActivity(alarm)
                val n = NotificationCompat.Builder(this, CH_MSG)
                    .setSmallIcon(R.mipmap.ic_launcher)
                    .setContentTitle("Alarm set")
                    .setContentText("$timeText — $label")
                    .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                    .setAutoCancel(true)
                    .build()
                mgr.notify(System.currentTimeMillis().toInt(), n)
            } else {
                val setPi = PendingIntent.getActivity(this, 3, alarm,
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
                val n = NotificationCompat.Builder(this, CH_MSG)
                    .setSmallIcon(R.mipmap.ic_launcher)
                    .setContentTitle("Alarm request")
                    .setContentText("$timeText — $label (tap to set)")
                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                    .setContentIntent(setPi)
                    .setAutoCancel(true)
                    .build()
                mgr.notify(System.currentTimeMillis().toInt(), n)
            }
            return
        }
        // Feature plugins get first pick (call / lock / unlock / screen ...)
        if (Plugins.fcm(this, kind, msg.data)) return
        // Default: plain notification with inline reply
        val notifId = System.currentTimeMillis().toInt()
        val open = PendingIntent.getActivity(this, 1,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val replyInput = androidx.core.app.RemoteInput.Builder(ReplyReceiver.KEY_REPLY)
            .setLabel(getString(R.string.reply))
            .build()
        val replyIntent = Intent(ReplyReceiver.ACTION).apply {
            setClass(this@FcmService, ReplyReceiver::class.java)
            putExtra("notif_id", notifId)
        }
        val replyPi = PendingIntent.getBroadcast(this, notifId, replyIntent,
            PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val replyAction = NotificationCompat.Action.Builder(
            R.mipmap.ic_launcher, getString(R.string.reply), replyPi)
            .addRemoteInput(replyInput)
            .build()
        val n = NotificationCompat.Builder(this, CH_MSG)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(msg.data["title"] ?: getString(R.string.app_name))
            .setContentText(msg.data["body"] ?: "")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(open)
            .addAction(replyAction)
            .setAutoCancel(true)
            .build()
        mgr.notify(notifId, n)
    }

    companion object {
        const val CH_MSG = "cocoon_msg"

        fun ensureChannels(ctx: Context) {
            val mgr = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            mgr.createNotificationChannel(
                NotificationChannel(CH_MSG, "Messages", NotificationManager.IMPORTANCE_HIGH))
        }
    }

    private fun ensureChannels() = ensureChannels(this)
}
