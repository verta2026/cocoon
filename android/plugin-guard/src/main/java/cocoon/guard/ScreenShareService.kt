package cocoon.guard

import cocoon.common.Net
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.util.DisplayMetrics
import android.view.WindowManager
import android.app.PendingIntent
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class ScreenShareService : Service() {

    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var handler: Handler? = null
    private var handlerThread: HandlerThread? = null
    @Volatile private var capturing = false
    private var intervalMs = 60000L
    private var firstFrameDone = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        handlerThread = HandlerThread("screenshare").also { it.start() }
        handler = Handler(handlerThread!!.looper)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopCapture()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }

        val ch = NotificationChannel(CH_ID, "Screen share", NotificationManager.IMPORTANCE_LOW)
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(ch)
        val stopIntent = Intent(this, ScreenShareService::class.java).apply { action = ACTION_STOP }
        val stopPi = PendingIntent.getService(this, 0, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notif = Notification.Builder(this, CH_ID)
            .setContentTitle(getString(R.string.guard_screen_active))
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(
                null, getString(R.string.guard_stop_share), stopPi).build())
            .build()
        startForeground(NOTIF_ID, notif,
            android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)

        // RESULT_OK == -1，哨兵默认值必须避开它（v0.5.0 起同屏启动即死的真根）
        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, android.app.Activity.RESULT_CANCELED)
            ?: android.app.Activity.RESULT_CANCELED
        val resultData: Intent? = if (android.os.Build.VERSION.SDK_INT >= 33) {
            intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        intervalMs = intent?.getLongExtra(EXTRA_INTERVAL, 60000L) ?: 60000L

        if (resultCode != android.app.Activity.RESULT_OK || resultData == null) {
            android.util.Log.e("ScreenShare", "resultCode=$resultCode resultData=$resultData — stopping")
            stopSelf()
            return START_NOT_STICKY
        }
        android.util.Log.i("ScreenShare", "got projection result, starting capture")

        val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        projection = mpm.getMediaProjection(resultCode, resultData)
        // Android 14 起 createVirtualDisplay 之前必须先注册回调，否则 SecurityException
        projection?.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                android.util.Log.i("ScreenShare", "projection stopped by system/user")
                stopCapture()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }, handler)

        startCapture()
        // projection 授权数据不可重放，被杀后重启只会立死一次，不如不重启
        return START_NOT_STICKY
    }

    private fun startCapture() {
        val wm = getSystemService(WINDOW_SERVICE) as WindowManager
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        wm.defaultDisplay.getRealMetrics(metrics)

        // Capture at reduced resolution for bandwidth
        val scale = 0.5f
        val w = (metrics.widthPixels * scale).toInt()
        val h = (metrics.heightPixels * scale).toInt()
        val dpi = (metrics.densityDpi * scale).toInt()

        imageReader = ImageReader.newInstance(w, h, PixelFormat.RGBA_8888, 2)

        virtualDisplay = projection?.createVirtualDisplay(
            "cocoon-screen", w, h, dpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader!!.surface, null, handler
        )

        capturing = true
        firstFrameDone = false
        handler?.post(captureRunnable)
    }

    private val captureRunnable = object : Runnable {
        override fun run() {
            if (!capturing) return
            captureFrame()
            // 首帧 ImageReader 往往还没出画面，短重试直到抓到，别干等一个整 interval
            val delay = if (firstFrameDone) intervalMs else 2000L
            handler?.postDelayed(this, delay)
        }
    }

    private fun captureFrame() {
        val image: Image? = try { imageReader?.acquireLatestImage() } catch (e: Exception) {
            android.util.Log.e("ScreenShare", "acquireLatestImage failed", e)
            null
        }
        if (image == null) {
            android.util.Log.w("ScreenShare", "no image available from ImageReader")
            return
        }

        try {
            val plane = image.planes[0]
            val buffer = plane.buffer
            val pixelStride = plane.pixelStride
            val rowStride = plane.rowStride
            val rowPadding = rowStride - pixelStride * image.width

            val bitmap = Bitmap.createBitmap(
                image.width + rowPadding / pixelStride,
                image.height,
                Bitmap.Config.ARGB_8888
            )
            bitmap.copyPixelsFromBuffer(buffer)

            // Crop to actual width (remove row padding)
            val cropped = if (rowPadding > 0) {
                Bitmap.createBitmap(bitmap, 0, 0, image.width, image.height).also {
                    if (it !== bitmap) bitmap.recycle()
                }
            } else bitmap

            val baos = ByteArrayOutputStream()
            cropped.compress(Bitmap.CompressFormat.JPEG, 60, baos)
            cropped.recycle()

            val bytes = baos.toByteArray()
            firstFrameDone = true
            uploadFrame(bytes)
        } finally {
            image.close()
        }
    }

    private fun uploadFrame(jpeg: ByteArray) {
        try {
            val tok = Net.token(this)
            if (tok.isEmpty()) {
                android.util.Log.w("ScreenShare", "token is empty, skipping upload")
                return
            }
            val sep = "?"
            val conn = URL(
                "${Net.BASE}/widget/screen${sep}token=${URLEncoder.encode(tok, "UTF-8")}"
            ).openConnection() as HttpURLConnection
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "image/jpeg")
            conn.outputStream.use { it.write(jpeg) }
            conn.inputStream.bufferedReader().readText()
            conn.disconnect()
        } catch (e: Exception) {
            android.util.Log.e("ScreenShare", "upload failed: ${e.message}", e)
        }
    }

    private fun stopCapture() {
        capturing = false
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader?.close()
        imageReader = null
        projection?.stop()
        projection = null
    }

    override fun onDestroy() {
        stopCapture()
        handlerThread?.quitSafely()
        super.onDestroy()
    }

    companion object {
        const val CH_ID = "screen_share"
        const val NOTIF_ID = 42
        const val ACTION_STOP = "cocoon.guard.STOP_SCREEN_SHARE"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val EXTRA_INTERVAL = "interval_ms"

        fun stop(ctx: Context) {
            ctx.startService(Intent(ctx, ScreenShareService::class.java).apply {
                action = ACTION_STOP
            })
        }
    }
}
