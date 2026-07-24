pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "cocoon-android"
include(":common")
include(":app")

// Optional feature plugins — pick yours in gradle.properties (cocoon.plugins=...).
// Each is a self-contained library module; the core app discovers them at runtime
// via the cocoon.common.Plugins registry, so removing one never breaks the build.
val enabled = (providers.gradleProperty("cocoon.plugins").orNull ?: "")
    .split(",").map { it.trim() }.filter { it.isNotEmpty() }
for (p in enabled) include(":plugin-$p")
