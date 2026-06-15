import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
}

// 설정 값은 환경변수(CI) → local.properties(로컬, gitignore됨) 순으로 읽는다.
// 홈 IP·키스토어 비밀번호 등을 소스/공개 레포에 박지 않기 위함.
val localProps = Properties()
rootProject.file("local.properties").let { f ->
    if (f.exists()) f.inputStream().use { localProps.load(it) }
}
fun cfg(key: String): String? = System.getenv(key) ?: localProps.getProperty(key)

android {
    namespace = "com.contentscurator"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.contentscurator"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("VERSION_CODE") ?: "1").toInt()
        versionName = "1.0"
        buildConfigField("String", "API_BASE_URL", "\"${cfg("API_BASE_URL") ?: "http://10.0.2.2:8000/"}\"")
        // 고정 포인터(공개 Gist raw). 앱이 여기서 현재 백엔드 주소를 자동으로 읽는다.
        // 비밀이 아니라 기본값으로 둔다(env/local.properties로 덮어쓸 수 있음).
        buildConfigField("String", "POINTER_URL", "\"${cfg("POINTER_URL") ?: "https://gist.githubusercontent.com/songsnim/f1d24fd04191a56b8b1119c0ccf2aee2/raw/backend_url.txt"}\"")
    }

    signingConfigs {
        create("release") {
            val ksPath = cfg("KEYSTORE_PATH")
            if (ksPath != null) {
                storeFile = file(ksPath)
                storePassword = cfg("KEYSTORE_PASSWORD")
                keyAlias = cfg("KEY_ALIAS")
                keyPassword = cfg("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // 키스토어가 설정된 경우(CI 또는 로컬 release)에만 서명. 없으면 미서명 빌드.
            if (cfg("KEYSTORE_PATH") != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.navigation.compose)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.retrofit)
    implementation(libs.retrofit.moshi)
    implementation(libs.okhttp.logging)
    implementation(libs.moshi.kotlin)

    implementation(libs.androidx.work.runtime)

    implementation(libs.androidx.glance)
    implementation(libs.androidx.glance.material3)

    implementation(libs.coil.compose)
    implementation(libs.compose.markdown)

    debugImplementation(libs.androidx.compose.ui.tooling)
}
