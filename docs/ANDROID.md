# Android application: architecture and releases

The Android project lives in `android/` in this repository. It uses the existing responsive chat interface inside a locked-down WebView, so message rendering, replies, themes, profiles, uploads and voice recording match the website. The native shell supplies file selection, microphone permission, private downloads, deep links and notifications. It connects only to `https://chat.sinafateh.ir/` for app pages; external links open in the device browser. TLS errors are never bypassed.

## Why a WebView wrapper?

The project has one source of truth for conversation behavior: Django templates and browser JavaScript. The Android wrapper gives that interface access to platform features without maintaining a second chat UI. `MainActivity` owns the WebView, file picker, Android permissions and a narrowly scoped message bridge. `UnreadWorker` performs scheduled checks, and `NotificationHandler` deduplicates and displays alerts. The bridge accepts messages only from the application's HTTPS origin and main frame. A native alert uses a monochrome status-bar icon; the launcher uses the same image as the website.

## Build and install

Open `android/` in Android Studio with JDK 17 and Android SDK 36, or run:

```sh
gradle -p android :app:assembleDebug
```

The APK is at `android/app/build/outputs/apk/debug/app-debug.apk`. The [Android APK workflow](../.github/workflows/android-apk.yml) builds and verifies the APK, then installs it on an Android 15 emulator. On GitHub Actions, `pulse-android-apk` is a **ZIP archive**, not an APK: extract it before installing `app-debug.apk`. Do not try to install `pulse-android-apk.zip`. GitHub retains Actions artifacts for 30 days.

For a phone, use the [GitHub Releases page](https://github.com/cnafateh/PrivateReal-timeChatPlatform/releases) and download the `.apk` asset directly. Release files are not wrapped in the Actions ZIP. Open the downloaded `.apk` with Android's package installer. The minimum supported version is Android 8.0.

GitHub Releases now require a permanent signing key. Configure four repository Actions secrets: `ANDROID_KEYSTORE_BASE64` (base64 of the PKCS#12 keystore file), `ANDROID_STORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`. The workflow verifies the signed APK, installs it on an Android 15 emulator and publishes it for `android-v*` tags. A missing key fails the release instead of publishing an APK that cannot update in place.

Create a private key with Android Studio or `keytool` and keep the keystore and passwords in a secure backup. The repository ignores `android/signing/` and common keystore extensions, but **never commit or share the keystore or its passwords**. The app's package name is `ir.sinafateh.pulse`. Future APKs can update this release only when they use the same package name, the same signing certificate and a higher version code. CI debug APKs use temporary keys and are for testing only. An existing `1.0.1-preview` or `1.0.2-preview` installation has a different signature and must be removed once before installing the first permanently signed release; this clears only app-local data, so sign in again. Keep the permanent key for every later release.

For the current maintainer, the locally generated key is `android/signing/pulse-release.p12`. Back up that file together with `android/signing/signing-info.txt` in a secure location before releasing. In the repository's **Settings → Secrets and variables → Actions**, create the four secrets above. Copy `ANDROID_KEYSTORE_BASE64` from `android/signing/keystore.base64.txt`; the other three values are in `signing-info.txt`. Keep these files outside Git and out of issue comments, pull requests and chat messages. For future versions, increment `versionCode` and use the same four secrets. Build and verify a signed APK on the feature branch before pushing an `android-v*` tag; the tag workflow publishes the APK directly to GitHub Releases.

## Notifications

When a private chat or group is visible in the foreground, a message for that same conversation updates the page without a system notification. Alerts for other conversations still appear. `MainActivity` tracks the visible destination, and `NotificationHandler` compares it with the destination in each server payload before posting an alert. On pause, the visible destination is cleared. The message cursor advances even when an alert is suppressed, so reopening the app does not replay it.

Group notifications open the relevant group directly. The server includes group messages only for current members.

While the app is open, an inbox WebSocket prompts a notification check immediately and a 15-second fallback check uses the authenticated WebView session. The native worker also checks in the foreground. When the app moves to the background it schedules a one-time catch-up check; WorkManager maintains periodic checks at intervals of at least 15 minutes and updates the schedule after an app upgrade. Android battery management may delay or suppress work, especially after force-stop. On Android 13 and newer the user must allow notifications in system settings. A notification opens its private or group conversation. Notifications show the sender and a short preview; lock-screen content is private. The first check after signing in records the newest received message and alerts only for messages that are still unread, avoiding a flood of old notifications. Later checks include newly received messages even if they were read before the check.

This does not provide instant push delivery while the app is closed. Instant push would require a push provider, server-side device token registration and delivery, and deployment credentials. The chat view and conversation list use WebSockets for immediate updates while a page is open. They also refresh after reconnecting or returning to the app.

To diagnose a missing background alert, first confirm the app is signed in and allowed to show notifications. Then check battery restrictions for Pulse and wait beyond the 15-minute minimum interval; the actual execution time is not exact. A force-stopped app will not run its jobs until opened again. Test with two accounts, and do not mark the incoming message read before the first check. If immediate delivery is a product requirement, integrate a push provider rather than reducing WorkManager's minimum interval or keeping a permanent background service alive.

## Server endpoint

`GET /api/mobile/unread/` returns the last 50 received private and group messages for the signed-in user, including their read state, destination path, conversation and sender profile UUIDs, and the current user's public identifier. It uses the existing Django session cookie and never exposes another user's messages. An expired session redirects to login; the Android worker ignores it. The endpoint is intended for notification checks, not as a replacement for the full history API. `GET /api/inbox/` returns the authenticated user's rendered conversation list for WebSocket catch-up and polling fallback.

## Operational notes

- The application requires HTTPS and access to the deployed server. The WebView and background worker use the same session cookies.
- Android 15 and newer draw app content behind system bars by default. The native container applies status, cutout, navigation and keyboard insets so the chat stays visible and usable.
- Voice recording needs microphone permission; choosing files uses the Android file picker without broad storage permission.
- Online status uses WebSocket and HTTP heartbeats. It can take about 75 seconds after closing the app to change to last seen. Both need the updated server image deployed.
- Downloaded attachments go to the device's Downloads folder. Users should treat them as local copies of private media.
- If the deployment hostname changes, update `MainActivity.HOST`, `HOME_URL` and the app-link host in `AndroidManifest.xml`, then build a new APK.
