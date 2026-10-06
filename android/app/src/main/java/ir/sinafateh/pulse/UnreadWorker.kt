package ir.sinafateh.pulse

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.webkit.CookieManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class UnreadWorker(context: Context, parameters: WorkerParameters) : Worker(context, parameters) {
    override fun doWork(): Result {
        val cookie = CookieManager.getInstance().getCookie(MainActivity.HOME_URL) ?: return Result.success()
        val connection = (URL(MainActivity.HOME_URL + "api/mobile/unread/").openConnection() as HttpURLConnection)
        return try {
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Cookie", cookie)
            connection.setRequestProperty("Accept", "application/json")
            if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                if (connection.responseCode == HttpURLConnection.HTTP_MOVED_TEMP) {
                    applicationContext.getSharedPreferences("unread", Context.MODE_PRIVATE)
                        .edit().remove("last_message_id").apply()
                }
                return if (connection.responseCode >= 500) Result.retry() else Result.success()
            }
            val body = connection.inputStream.bufferedReader().use { it.readText() }
            val payload = JSONObject(body)
            val messages = payload.getJSONArray("messages")
            val prefs = applicationContext.getSharedPreferences("unread", Context.MODE_PRIVATE)
            val userId = payload.getString("user_id")
            val lastId = if (prefs.getString("user_id", null) == userId)
                prefs.getLong("last_message_id", 0) else 0
            var newest = lastId
            val pending = mutableListOf<JSONObject>()
            for (index in 0 until messages.length()) {
                val message = messages.getJSONObject(index)
                val id = message.getLong("id")
                if (id > newest) newest = id
                if (id > lastId && (lastId != 0L || !message.getBoolean("is_read")))
                    pending.add(message)
            }
            if (pending.isNotEmpty() && !canNotify()) return Result.success()
            if (pending.isNotEmpty()) {
                createChannel()
                pending.takeLast(5).forEach { notifyMessage(it) }
            }
            prefs.edit().putString("user_id", userId).putLong("last_message_id", newest).apply()
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        } finally {
            connection.disconnect()
        }
    }

    private fun canNotify(): Boolean = Build.VERSION.SDK_INT < 33 ||
        applicationContext.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    private fun createChannel() {
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(
            CHANNEL_ID, "Chat messages", NotificationManager.IMPORTANCE_DEFAULT))
    }

    private fun notifyMessage(message: JSONObject) {
        val id = message.getLong("id")
        val sender = message.optString("sender", "Message")
        val preview = message.optString("message").ifBlank {
            message.optString("name").ifBlank { "New message" }
        }.take(120)
        val profileId = message.getString("sender_profile_id")
        val intent = Intent(applicationContext, MainActivity::class.java).apply {
            data = Uri.parse(MainActivity.HOME_URL + "chat/$profileId/")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val tap = PendingIntent.getActivity(applicationContext, id.toInt(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = Notification.Builder(applicationContext, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_pulse)
            .setContentTitle(sender)
            .setContentText(preview)
            .setStyle(Notification.BigTextStyle().bigText(preview))
            .setContentIntent(tap)
            .setAutoCancel(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .build()
        (applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .notify(id.toInt(), notification)
    }

    companion object { private const val CHANNEL_ID = "chat_messages" }
}
