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
import org.json.JSONObject

object NotificationHandler {
    private const val CHANNEL_ID = "chat_messages"

    @Synchronized
    fun process(context: Context, payload: JSONObject) {
        val messages = payload.getJSONArray("messages")
        val userId = payload.getString("user_id")
        val prefs = context.getSharedPreferences("unread", Context.MODE_PRIVATE)
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
        if (pending.isNotEmpty() && !canNotify(context)) return
        if (pending.isNotEmpty()) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(NotificationChannel(
                CHANNEL_ID, "Chat messages", NotificationManager.IMPORTANCE_DEFAULT))
            pending.takeLast(5).forEach { notifyMessage(context, manager, it) }
        }
        prefs.edit().putString("user_id", userId).putLong("last_message_id", newest).apply()
    }

    private fun canNotify(context: Context): Boolean {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        return manager.areNotificationsEnabled() && (Build.VERSION.SDK_INT < 33 ||
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)
    }

    private fun notifyMessage(context: Context, manager: NotificationManager, message: JSONObject) {
        val id = message.getLong("id")
        val sender = message.optString("sender", "Message")
        val preview = message.optString("message").ifBlank {
            message.optString("name").ifBlank { "New message" }
        }.take(120)
        val profileId = message.getString("sender_profile_id")
        val intent = Intent(context, MainActivity::class.java).apply {
            data = Uri.parse(MainActivity.HOME_URL + "chat/$profileId/")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val tap = PendingIntent.getActivity(context, id.toInt(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = Notification.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(sender)
            .setContentText(preview)
            .setStyle(Notification.BigTextStyle().bigText(preview))
            .setContentIntent(tap)
            .setAutoCancel(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .build()
        manager.notify(id.toInt(), notification)
    }
}
