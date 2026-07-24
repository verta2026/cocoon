package cocoon.window

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.ValueCallback
import android.webkit.CookieManager
import android.webkit.JsPromptResult
import android.webkit.JsResult
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import cocoon.common.BuildConfig
import cocoon.common.Net
import cocoon.common.Plugins

class MainActivity : Activity() {

    private lateinit var web: WebView
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var pendingPermRequest: PermissionRequest? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        setContentView(web)
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            mediaPlaybackRequiresUserGesture = false
        }
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true)
        Plugins.all.forEach { it.onWebViewReady(this, web) }
        web.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                applyOrientation(url)
            }
            override fun doUpdateVisitedHistory(view: WebView?, url: String?, isReload: Boolean) {
                super.doUpdateVisitedHistory(view, url, isReload)
                applyOrientation(url)
            }
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // Self-heal the native-side token from the webapp's localStorage:
                // a reinstall clears SharedPreferences, and without this every native
                // report silently stops (empty token = Net drops all requests).
                view?.evaluateJavascript(
                    "(localStorage.getItem('${BuildConfig.STORAGE_NS}_token')||localStorage.getItem('token')||'')"
                ) { raw ->
                    val t = raw?.trim('"')?.takeIf { it.isNotBlank() && it != "null" }
                        ?: return@evaluateJavascript
                    if (t != Net.token(this@MainActivity)) {
                        Net.saveToken(this@MainActivity, t)
                        Plugins.all.forEach { p -> p.onTokenSaved(this@MainActivity) }
                    }
                }
            }
        }
        // The chat page asks for the token via window.prompt — WebView swallows JS
        // dialogs unless implemented, which would make login impossible.
        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest?) {
                request ?: return
                // A page asking for the mic needs the app itself to hold RECORD_AUDIO
                // first, otherwise granting the web request is a no-op.
                val needMic = request.resources.contains(
                    PermissionRequest.RESOURCE_AUDIO_CAPTURE) &&
                    checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
                        PackageManager.PERMISSION_GRANTED
                if (needMic) {
                    pendingPermRequest = request
                    requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQ_MIC)
                } else {
                    request.grant(request.resources)
                }
            }

            override fun onJsPrompt(
                view: WebView?, url: String?, message: String?,
                defaultValue: String?, result: JsPromptResult?
            ): Boolean {
                val input = EditText(this@MainActivity)
                input.setText(defaultValue ?: "")
                AlertDialog.Builder(this@MainActivity)
                    .setMessage(message ?: "")
                    .setView(input)
                    .setPositiveButton(android.R.string.ok) { _, _ ->
                        val v = input.text.toString()
                        // The token prompt from the chat page — keep a native copy for plugins
                        if ((message ?: "").contains("token", ignoreCase = true) && v.isNotBlank()) {
                            Net.saveToken(this@MainActivity, v)
                        }
                        result?.confirm(v)
                    }
                    .setNegativeButton(android.R.string.cancel) { _, _ -> result?.cancel() }
                    .setOnCancelListener { result?.cancel() }
                    .show()
                return true
            }
            override fun onJsAlert(view: WebView?, url: String?, message: String?, result: JsResult?): Boolean {
                AlertDialog.Builder(this@MainActivity).setMessage(message ?: "")
                    .setPositiveButton(android.R.string.ok) { _, _ -> result?.confirm() }
                    .setOnCancelListener { result?.cancel() }.show()
                return true
            }
            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                // Settle any previous callback first to avoid a stuck chooser
                fileCallback?.onReceiveValue(null)
                fileCallback = filePathCallback
                val intent = fileChooserParams?.createIntent()
                    ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE); type = "*/*"
                    }
                if (fileChooserParams?.mode == FileChooserParams.MODE_OPEN_MULTIPLE) {
                    intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                }
                return try {
                    startActivityForResult(intent, REQ_FILE)
                    true
                } catch (e: Exception) {
                    fileCallback?.onReceiveValue(null)
                    fileCallback = null
                    false
                }
            }

            override fun onJsConfirm(view: WebView?, url: String?, message: String?, result: JsResult?): Boolean {
                AlertDialog.Builder(this@MainActivity).setMessage(message ?: "")
                    .setPositiveButton(android.R.string.ok) { _, _ -> result?.confirm() }
                    .setNegativeButton(android.R.string.cancel) { _, _ -> result?.cancel() }
                    .setOnCancelListener { result?.cancel() }.show()
                return true
            }
        }
        val openPath = intent?.getStringExtra("open")
        if (savedInstanceState == null) web.loadUrl(if (openPath != null) HOME.trimEnd('/') + openPath else HOME)
        else web.restoreState(savedInstanceState)
        askNotificationPermission()
        Plugins.all.forEach { it.onMainCreate(this) }
        // FCM: create the message channel and report the device token to the bridge.
        // Wrapped in try — without google-services.json Firebase simply isn't initialized.
        try { FcmService.ensureChannels(this) } catch (e: Exception) {}
        try {
            com.google.firebase.messaging.FirebaseMessaging.getInstance().token
                .addOnSuccessListener { t ->
                    kotlin.concurrent.thread {
                        Net.post(this, "/widget/fcm_token", org.json.JSONObject().put("token", t))
                    }
                }
        } catch (e: Exception) {}
    }

    /** Notification permission (Android 13+) is core: FCM messages need it. Asked once. */
    private fun askNotificationPermission() {
        val prefs = getSharedPreferences("cocoon", MODE_PRIVATE)
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED &&
            !prefs.getBoolean("asked_notif", false)) {
            prefs.edit().putBoolean("asked_notif", true).apply()
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIF)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_MIC) {
            val req = pendingPermRequest
            pendingPermRequest = null
            if (grantResults.any { it == PackageManager.PERMISSION_GRANTED }) {
                req?.grant(req.resources)
            } else {
                req?.deny()
            }
        }
        Plugins.all.forEach { it.onPermissionsResult(this, requestCode, grantResults) }
    }

    /** Pages that want landscape + immersive mode (deployment config; JS can't rotate a WebView). */
    private val landscapePages = BuildConfig.LANDSCAPE_PAGES
        .split(",").map { it.trim() }.filter { it.isNotEmpty() }
    private fun applyOrientation(url: String?) {
        // Never touch orientation while the file chooser is up: a forced rotation can
        // recreate the activity and drop fileCallback, losing the user's selection.
        if (fileCallback != null) return
        val isLandscape = url != null && landscapePages.any { url.contains(it) }
        val target = if (isLandscape) {
            ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        } else {
            ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        }
        if (requestedOrientation != target) requestedOrientation = target
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = if (isLandscape) {
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        } else {
            View.SYSTEM_UI_FLAG_VISIBLE
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onResume() {
        super.onResume()
        Plugins.all.forEach { it.onMainResume(this) }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ_FILE) {
            val cb = fileCallback
            fileCallback = null
            // Always answer the callback (even with null) — otherwise the WebView
            // never opens a file chooser again.
            var results = WebChromeClient.FileChooserParams.parseResult(resultCode, data)
            // Some OEM galleries return results parseResult can't read; recover
            // the uris manually from clipData/data, covering single and multi select.
            if ((results == null || results.isEmpty()) &&
                resultCode == Activity.RESULT_OK && data != null) {
                val uris = ArrayList<Uri>()
                data.clipData?.let { cd ->
                    for (i in 0 until cd.itemCount) cd.getItemAt(i)?.uri?.let { uris.add(it) }
                }
                if (uris.isEmpty()) data.data?.let { uris.add(it) }
                if (uris.isNotEmpty()) results = uris.toTypedArray()
            }
            cb?.onReceiveValue(results)
            return
        }
        Plugins.all.any { it.onActivityResult(this, requestCode, resultCode, data) }
    }

    override fun onPause() {
        super.onPause()
        CookieManager.getInstance().flush()
    }

    companion object {
        val HOME = BuildConfig.HOME_URL
        const val REQ_FILE = 71
        const val REQ_NOTIF = 84
        const val REQ_MIC = 85
    }
}
