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

The app checks the authenticated user's unread messages with WorkManager while it is in the background. On Android 13 and newer the user must allow notifications. An initial check runs after opening the inbox, then Android schedules checks at intervals of at least 15 minutes. Battery management may delay checks further. A notification opens the sender's conversation. Notifications show the sender and a short preview; lock-screen content is private.

This does not provide instant push delivery while the app is closed. Instant push would require a push provider, server-side device token registration and delivery, and deployment credentials. The live WebSocket chat remains immediate while the conversation is open.

## Server endpoint

`GET /api/mobile/unread/` returns the last 50 unread messages for the signed-in user, with conversation and sender profile UUIDs. It uses the existing Django session cookie and never exposes another user's unread messages. An expired session redirects to login; the Android worker ignores it. The endpoint is intended for notification checks, not as a replacement for the full history API.

## Operational notes

- The application requires HTTPS and access to the deployed server. The WebView and background worker use the same session cookies.
- Voice recording needs microphone permission; choosing files uses the Android file picker without broad storage permission.
- Downloaded attachments go to the device's Downloads folder. Users should treat them as local copies of private media.
- If the deployment hostname changes, update `MainActivity.HOST`, `HOME_URL` and the app-link host in `AndroidManifest.xml`, then build a new APK.
