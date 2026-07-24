package cocoon.call

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import androidx.core.app.NotificationCompat
import cocoon.common.CocoonPlugin

/**
 * Full-screen incoming call over FCM (kind=call). The notification channel
 * carries the ringtone for the first ring; the activity loops it afterwards.
 *
 * Ringtone: drop a file at res/raw/ringtone.mp3 in this module to use your own;
 * without one the system default ringtone is used.
 */
object CallPlugin : CocoonPlugin {

    const val CH_CALL = "cocoon_call"
    const val CALL_NOTIF_ID = 7001

    fun ringtoneUri(ctx: Context): Uri {
        val id = ctx.resources.getIdentifier("ringtone", "raw", ctx.packageName)
        return if (id != 0) Uri.parse("android.resource://${ctx.packageName}/$id")
        else RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
    }

    override fun onFcm(ctx: Context, kind: String, data: Map<String, String>): Boolean {
        if (kind != "call") return false
        ensureChannel(ctx)
        val reason = data["reason"] ?: data["body"] ?: ""
        val full = Intent(ctx, IncomingCallActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            .putExtra("reason", reason)
            .putExtra("title", data["title"])
        val pi = PendingIntent.getActivity(ctx, 0, full,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(ctx, CH_CALL)
            .setSmallIcon(android.R.drawable.sym_call_incoming)
            .setContentTitle(data["title"] ?: ctx.getString(R.string.call_incoming))
            .setContentText(reason)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setFullScreenIntent(pi, true)
            .setContentIntent(pi)
            .setAutoCancel(true)
            .setOngoing(true)
            .build()
        (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .notify(CALL_NOTIF_ID, n)
        return true
    }

    private fun ensureChannel(ctx: Context) {
        val mgr = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
            .build()
        mgr.createNotificationChannel(
            NotificationChannel(CH_CALL, "Calls", NotificationManager.IMPORTANCE_HIGH).apply {
                setSound(ringtoneUri(ctx), attrs)
                enableVibration(true)
                setBypassDnd(true)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            })
    }
}
