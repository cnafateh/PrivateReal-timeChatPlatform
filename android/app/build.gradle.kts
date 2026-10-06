plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "ir.sinafateh.pulse"
    compileSdk = 36

    defaultConfig {
        applicationId = "ir.sinafateh.pulse"
        minSdk = 26
        targetSdk = 35
        versionCode = 4
        versionName = "1.1.0"
    }

    val releaseKeyStore = System.getenv("PULSE_KEYSTORE_FILE")
    if (!releaseKeyStore.isNullOrBlank()) {
        signingConfigs {
            create("production") {
                storeFile = file(releaseKeyStore)
                storePassword = System.getenv("PULSE_STORE_PASSWORD") ?: ""
                keyAlias = System.getenv("PULSE_KEY_ALIAS") ?: ""
                keyPassword = System.getenv("PULSE_KEY_PASSWORD") ?: ""
                storeType = System.getenv("PULSE_STORE_TYPE") ?: "pkcs12"
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (!releaseKeyStore.isNullOrBlank()) signingConfig = signingConfigs.getByName("production")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.work:work-runtime-ktx:2.10.5")
    implementation("androidx.webkit:webkit:1.17.1")
}
