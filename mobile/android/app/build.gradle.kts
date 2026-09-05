import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing. The keystore and its passwords live in `android/key.properties`,
// which is gitignored — committing it would put the upload key in the repo, and
// losing that key means this Play listing can never be updated again.
//
//   android/key.properties:
//     storeFile=../upload-keystore.jks
//     storePassword=...
//     keyAlias=upload
//     keyPassword=...
//
// A release must never silently use the debug key: Play accepts only a stable
// upload identity, and every future update must use that same identity.
val keystoreProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val hasReleaseKey = keystoreProperties.getProperty("storeFile") != null

android {
    // Set once, deliberately: this becomes the iOS bundle id and the Android
    // package name. Changing it after a store submission means a new listing
    // and losing every installed user.
    namespace = "com.banterclips.app"
    compileSdk = flutter.compileSdkVersion
    // Current native Flutter plugins require NDK 27. Android NDK releases are
    // backward compatible, so use the highest requested plugin version.
    ndkVersion = "27.0.12077973"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        applicationId = "com.banterclips.app"
        // Play Billing (the in_app_purchase plugin) requires 21+; Flutter's
        // own floor is already above that, so the default is safe.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            check(hasReleaseKey) {
                "Release signing is not configured. Create android/key.properties before building a release."
            }
            storeFile = file(keystoreProperties.getProperty("storeFile"))
            storePassword = keystoreProperties.getProperty("storePassword")
            keyAlias = keystoreProperties.getProperty("keyAlias")
            keyPassword = keystoreProperties.getProperty("keyPassword")
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            // Left off for now: R8 shrinking needs keep rules verified against
            // every plugin (video_player and in_app_purchase both use
            // reflection), and a silently broken release build is worse than
            // a larger one. Turn on once there is a device to test it against.
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}

flutter {
    source = "../.."
}
