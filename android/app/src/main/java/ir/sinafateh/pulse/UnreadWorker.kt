package ir.sinafateh.pulse

import android.content.Context
import android.util.Log
import android.webkit.CookieManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class UnreadWorker(context: Context, parameters: WorkerParameters) : Worker(context, parameters) {
    override fun doWork(): Result {
        val prefs = applicationContext.getSharedPreferences("unread", Context.MODE_PRIVATE)
        var connection: HttpURLConnection? = null
        return try {
            val cookie = prefs.getString("session_cookie", null)
                ?: CookieManager.getInstance().getCookie(MainActivity.HOME_URL)
                ?: return Result.success()
            val request = URL(MainActivity.HOME_URL + "api/mobile/unread/").openConnection() as HttpURLConnection
            connection = request
            request.connectTimeout = 10_000
            request.readTimeout = 10_000
            request.instanceFollowRedirects = false
            request.setRequestProperty("Cookie", cookie)
            request.setRequestProperty("Accept", "application/json")
            when (request.responseCode) {
                HttpURLConnection.HTTP_OK -> {
                    val body = request.inputStream.bufferedReader().use { it.readText() }
                    NotificationHandler.process(applicationContext, JSONObject(body))
                    Result.success()
                }
                HttpURLConnection.HTTP_MOVED_TEMP -> {
                    prefs.edit().remove("session_cookie").remove("last_message_id").remove("user_id").apply()
                    Result.success()
                }
                else -> if (request.responseCode >= 500) Result.retry() else Result.success()
            }
        } catch (error: Exception) {
            Log.w("PulseNotifications", "Notification check failed", error)
            Result.retry()
        } finally {
            connection?.disconnect()
        }
    }
}
