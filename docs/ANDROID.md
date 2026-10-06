# Android application

The Android project lives in `android/` in this repository. It uses the existing responsive chat interface inside a locked-down WebView, so message rendering, replies, themes, profiles, uploads and voice recording match the website. The native shell supplies file selection, microphone permission, private downloads, deep links and notifications. It connects only to `https://chat.sinafateh.ir/` for app pages; external links open in the device browser. TLS errors are never bypassed.

## Build and install

Open `android/` in Android Studio with JDK 17 and Android SDK 36, or run:

```sh
gradle -p android :app:assembleDebug
```

The APK is at `android/app/build/outputs/apk/debug/app-debug.apk`. The [Android APK workflow](../.github/workflows/android-apk.yml) builds and verifies the APK, then installs it on an Android 15 emulator. On GitHub Actions, `pulse-android-apk` is a **ZIP archive**, not an APK: extract it before installing `app-debug.apk`. Do not try to install `pulse-android-apk.zip`. GitHub retains Actions artifacts for 30 days.

For a phone, use the [GitHub Releases page](https://github.com/cnafateh/PrivateReal-timeChatPlatform/releases) and download the `.apk` asset directly. Release files are not wrapped in the Actions ZIP. Open the downloaded `.apk` with Android's package installer. The minimum supported version is Android 8.0.

Without signing secrets, a tagged GitHub Release is marked as a preview and contains a development-signed installation build. Each CI run may use a different debug key, so a newer preview may require uninstalling an older preview first. For a production APK that can update in place, create a private, persistent Android keystore and add four repository secrets: `ANDROID_KEYSTORE_BASE64` (base64 of the keystore file), `ANDROID_STORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`. The workflow then also uploads `pulse-android-release-apk` and publishes that signed APK for Android version tags. Keep the original keystore secure: future updates must use the same key. Never commit the key to this repository. The app's package name is `ir.sinafateh.pulse`.

## Notifications

The app checks received messages about every 15 seconds while it is open. In the background, WorkManager schedules checks at intervals of at least 15 minutes; Android battery management may delay them further. On Android 13 and newer the user must allow notifications in system settings. A notification opens the sender's conversation. Notifications show the sender and a short preview; lock-screen content is private. The first check after signing in records the newest received message and alerts only for messages that are still unread, avoiding a flood of old notifications. Later checks include newly received messages even if they were read before the check.

This does not provide instant push delivery while the app is closed. Instant push would require a push provider, server-side device token registration and delivery, and deployment credentials. The chat view and conversation list use WebSockets for immediate updates while a page is open. They also refresh after reconnecting or returning to the app.

## Server endpoint

`GET /api/mobile/unread/` returns the last 50 received messages for the signed-in user, including their read state, conversation and sender profile UUIDs, and the current user's public identifier. It uses the existing Django session cookie and never exposes another user's messages. An expired session redirects to login; the Android worker ignores it. The endpoint is intended for notification checks, not as a replacement for the full history API. `GET /api/inbox/` returns the authenticated user's rendered conversation list for WebSocket catch-up and polling fallback.

## Operational notes

- The application requires HTTPS and access to the deployed server. The WebView and background worker use the same session cookies.
- Android 15 and newer draw app content behind system bars by default. The native container applies status, cutout, navigation and keyboard insets so the chat stays visible and usable.
- Voice recording needs microphone permission; choosing files uses the Android file picker without broad storage permission.
- Downloaded attachments go to the device's Downloads folder. Users should treat them as local copies of private media.
- If the deployment hostname changes, update `MainActivity.HOST`, `HOME_URL` and the app-link host in `AndroidManifest.xml`, then build a new APK.
