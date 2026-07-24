plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "cocoon.common"
    compileSdk = 34
    defaultConfig {
        minSdk = 26
        val prop = { k: String, d: String -> (project.findProperty(k) as? String ?: d) }
        buildConfigField("String", "BASE_URL", "\"${prop("cocoon.baseUrl", "https://cocoon.example/bridge")}\"")
        buildConfigField("String", "HOME_URL", "\"${prop("cocoon.homeUrl", "https://cocoon.example/")}\"")
        buildConfigField("String", "STORAGE_NS", "\"${prop("cocoon.storageNs", "cocoon")}\"")
        buildConfigField("String", "LANDSCAPE_PAGES", "\"${prop("cocoon.landscapePages", "")}\"")
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
