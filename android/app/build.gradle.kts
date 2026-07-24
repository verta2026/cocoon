plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
// Firebase config is deployment-specific: the gms plugin is only applied when you
// drop your own google-services.json next to this file. Without it the app still
// builds — push features just stay dormant.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

android {
    namespace = "cocoon.window"
    compileSdk = 34

    defaultConfig {
        applicationId = "cocoon.window"
        minSdk = 26
        targetSdk = 34
        versionCode = (project.findProperty("cocoon.versionCode") as? String)?.toIntOrNull() ?: 1
        versionName = (project.findProperty("cocoon.versionName") as? String) ?: "1.0"
    }

    signingConfigs {
        create("release") {
            // Inject a stable keystore via env (e.g. from CI secrets) so upgrades
            // never hit a signature mismatch. Absent env vars only affect release packaging.
            System.getenv("KEYSTORE_PATH")?.let { storeFile = file(it) }
            storePassword = System.getenv("KEYSTORE_PASS")
            keyAlias = System.getenv("KEY_ALIAS")
            keyPassword = System.getenv("KEY_PASS")
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation(project(":common"))
    implementation("androidx.core:core-ktx:1.13.1")
    implementation(platform("com.google.firebase:firebase-bom:33.1.2"))
    implementation("com.google.firebase:firebase-messaging-ktx")
    // Compile in the feature plugins selected in gradle.properties
    val enabled = (project.findProperty("cocoon.plugins") as? String ?: "")
        .split(",").map { it.trim() }.filter { it.isNotEmpty() }
    for (p in enabled) implementation(project(":plugin-$p"))
}
