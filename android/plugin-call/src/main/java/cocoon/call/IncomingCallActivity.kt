package cocoon.call

import android.app.Activity
import android.app.KeyguardManager
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** Full-screen incoming call: visible on the lock screen, turns the screen on,
 *  loops the ringtone. Answer opens the app home (the call widget lives there). */
class IncomingCallActivity : Activity() {

    private var player: MediaPlayer? = null

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
            (getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager)
                .requestDismissKeyguard(this, null)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(0xFF16141F.toInt())
            setPadding(60, 120, 60, 120)
        }
        root.addView(TextView(this).apply {
            text = intent.getStringExtra("title") ?: getString(R.string.call_incoming)
            textSize = 26f
            setTextColor(0xFFE8DCC8.toInt())
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = intent.getStringExtra("reason") ?: ""
            textSize = 15f
            setTextColor(0xFFC4956A.toInt())
            gravity = Gravity.CENTER
            setPadding(0, 24, 0, 80)
        })
        val btns = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        btns.addView(Button(this).apply {
            text = getString(R.string.call_answer)
            setOnClickListener {
                stopRing()
                packageManager.getLaunchIntentForPackage(packageName)?.let {
                    startActivity(it.addFlags(
                        Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP))
                }
                finish()
            }
        })
        btns.addView(Button(this).apply {
            text = getString(R.string.call_decline)
            setOnClickListener { stopRing(); finish() }
        })
        root.addView(btns)
        setContentView(root)

        // The notification has served its purpose — this full-screen page IS the call
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .cancel(CallPlugin.CALL_NOTIF_ID)

        // create(…, attrs, sessionId) returns an already-prepared player;
        // calling setAudioAttributes afterwards would throw IllegalStateException
        player = try {
            val attrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build()
            MediaPlayer.create(this, CallPlugin.ringtoneUri(this), null, attrs, 0)?.apply {
                isLooping = true
                start()
            }
        } catch (e: Exception) { null }
    }

    private fun stopRing() {
        try { player?.stop(); player?.release() } catch (e: Exception) {}
        player = null
    }

    override fun onDestroy() {
        super.onDestroy()
        stopRing()
    }
}
