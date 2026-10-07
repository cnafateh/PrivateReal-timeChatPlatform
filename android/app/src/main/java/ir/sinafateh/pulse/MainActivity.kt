package ir.sinafateh.pulse

import android.Manifest
import android.app.Activity
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.graphics.Color
import android.view.ViewGroup
import android.view.WindowInsets
import android.widget.FrameLayout
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.PermissionRequest
import android.webkit.SslErrorHandler
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.net.http.SslError
import android.provider.Settings
import android.app.AlertDialog
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import org.json.JSONObject
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private val foregroundHandler = Handler(Looper.getMainLooper())
    private val foregroundCheck = object : Runnable {
        override fun run() {
            WorkManager.getInstance(this@MainActivity).enqueueUniqueWork(
                "foreground-unread-check", ExistingWorkPolicy.KEEP,
                OneTimeWorkRequestBuilder<UnreadWorker>().build())
            foregroundHandler.postDelayed(this, 15_000)
        }
    }
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var microphoneRequest: PermissionRequest? = null
    private var microphoneReply: JavaScriptReplyProxy? = null
    private var foreground = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this)
        val container = FrameLayout(this).apply {
            setBackgroundColor(Color.rgb(18, 22, 32))
            addView(webView, FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            if (Build.VERSION.SDK_INT >= 35) {
                setOnApplyWindowInsetsListener { view, insets ->
                    val bars = insets.getInsets(
                        WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime())
                    view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
                    insets
                }
            }
        }
        setContentView(container)
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false)
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(webView, "PulseBridge", setOf("https://$HOST")) {
                _, message, origin, isMainFrame, reply ->
                if (!isMainFrame || origin.scheme != "https" || origin.host != HOST) return@addWebMessageListener
                val payload = try { JSONObject(message.data ?: "") } catch (_: Exception) { return@addWebMessageListener }
                when (payload.optString("type")) {
                    "notifications" -> try {
                        NotificationHandler.process(this, payload.getJSONObject("payload"))
                    } catch (_: Exception) { }
                    "microphone" -> {
                        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                            reply.postMessage("granted")
                        } else {
                            microphoneReply?.postMessage("denied")
                            microphoneReply = reply
                            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), AUDIO_REQUEST)
                        }
                    }
                }
            }
        }
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = true
            javaScriptCanOpenWindowsAutomatically = false
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            mediaPlaybackRequiresUserGesture = false
            if (Build.VERSION.SDK_INT >= 26) safeBrowsingEnabled = true
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                if (uri.scheme == "https" && uri.host == HOST) return false
                if (request.isForMainFrame) {
                    if (uri.scheme in listOf("https", "http", "mailto", "tel")) {
                        try { startActivity(Intent(Intent.ACTION_VIEW, uri)) } catch (_: Exception) { }
                    }
                    return true
                }
                return false
            }

            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
            }

            override fun onPageFinished(view: WebView, url: String) {
                if (foreground) NotificationHandler.setActiveConversation(url)
                CookieManager.getInstance().flush()
                if (url.startsWith(HOME_URL + "login/")) {
                    getSharedPreferences("unread", Context.MODE_PRIVATE).edit()
                        .remove("last_message_id").remove("user_id").remove("session_cookie").apply()
                } else if (url == HOME_URL) {
                    rememberSessionCookie()
                    WorkManager.getInstance(this@MainActivity).enqueue(
                        OneTimeWorkRequestBuilder<UnreadWorker>().build())
                } else if (url.startsWith(HOME_URL)) {
                    rememberSessionCookie()
                }
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams,
            ): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                return try {
                    startActivityForResult(params.createIntent(), FILE_REQUEST)
                    true
                } catch (_: Exception) {
                    fileCallback = null
                    callback.onReceiveValue(null)
                    false
                }
            }

            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread {
                    if (request.origin.scheme != "https" || request.origin.host != HOST ||
                        !request.resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                        request.deny()
                    } else if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
                    } else {
                        microphoneRequest = request
                        requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), AUDIO_REQUEST)
                    }
                }
            }

            override fun onPermissionRequestCanceled(request: PermissionRequest) {
                if (microphoneRequest == request) microphoneRequest = null
            }
        }
        webView.setDownloadListener(DownloadListener { url, userAgent, disposition, mimeType, _ ->
            val uri = Uri.parse(url)
            if (uri.scheme != "https" || uri.host != HOST) return@DownloadListener
            val request = DownloadManager.Request(uri)
                .setMimeType(mimeType)
                .setTitle(URLUtil.guessFileName(url, disposition, mimeType))
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,
                    URLUtil.guessFileName(url, disposition, mimeType))
            request.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url) ?: "")
            request.addRequestHeader("User-Agent", userAgent)
            (getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
        })

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), NOTIFICATION_REQUEST)
        }
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
        val work = PeriodicWorkRequestBuilder<UnreadWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints).build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "unread-messages", ExistingPeriodicWorkPolicy.UPDATE, work)

        if (savedInstanceState == null) webView.loadUrl(safeUrl(intent?.data))
        else webView.restoreState(savedInstanceState)
    }

    private fun safeUrl(uri: Uri?): String =
        if (uri?.scheme == "https" && uri.host == HOST) uri.toString() else HOME_URL

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        webView.loadUrl(safeUrl(intent.data))
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == FILE_REQUEST) {
            fileCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
            fileCallback = null
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == AUDIO_REQUEST) {
            val granted = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
            microphoneReply?.postMessage(if (granted) "granted" else "denied")
            microphoneReply = null
            val request = microphoneRequest
            microphoneRequest = null
            if (granted) {
                request?.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
            } else request?.deny()
        } else if (requestCode == NOTIFICATION_REQUEST) {
            if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
                WorkManager.getInstance(this).enqueue(OneTimeWorkRequestBuilder<UnreadWorker>().build())
            } else {
                val prefs = getSharedPreferences("unread", Context.MODE_PRIVATE)
                if (!prefs.getBoolean("notification_help_shown", false)) {
                    prefs.edit().putBoolean("notification_help_shown", true).apply()
                    AlertDialog.Builder(this)
                        .setMessage("Allow notifications for Pulse in Android settings to receive message alerts.")
                        .setPositiveButton("Open settings") { _, _ ->
                            startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                                .putExtra(Settings.EXTRA_APP_PACKAGE, packageName))
                        }
                        .setNegativeButton("Later", null)
                        .show()
                }
            }
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        webView.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    override fun onPause() {
        foreground = false
        NotificationHandler.setActiveConversation(null)
        foregroundHandler.removeCallbacks(foregroundCheck)
        rememberSessionCookie()
        CookieManager.getInstance().flush()
        WorkManager.getInstance(this).enqueueUniqueWork(
            "background-transition-check", ExistingWorkPolicy.REPLACE,
            OneTimeWorkRequestBuilder<UnreadWorker>().build())
        super.onPause()
    }

    override fun onResume() {
        super.onResume()
        foreground = true
        NotificationHandler.setActiveConversation(webView.url)
        foregroundHandler.removeCallbacks(foregroundCheck)
        foregroundHandler.post(foregroundCheck)
    }

    private fun rememberSessionCookie() {
        val cookie = CookieManager.getInstance().getCookie(HOME_URL)
        if (!cookie.isNullOrBlank()) getSharedPreferences("unread", Context.MODE_PRIVATE)
            .edit().putString("session_cookie", cookie).apply()
    }

    companion object {
        const val HOST = "chat.sinafateh.ir"
        const val HOME_URL = "https://chat.sinafateh.ir/"
        private const val FILE_REQUEST = 100
        private const val AUDIO_REQUEST = 101
        private const val NOTIFICATION_REQUEST = 102
    }
}
