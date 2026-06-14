package com.contentscurator.data

import android.content.Context
import com.contentscurator.BuildConfig

/** 백엔드 주소를 로컬에 저장/로드. CI 재빌드 없이 앱에서 서버 주소를 바꾸기 위함. */
object ServerPrefs {
    private const val PREFS = "curator"
    private const val KEY = "server_url"

    fun load(context: Context): String {
        val saved = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)
        return saved?.takeIf { it.isNotBlank() } ?: BuildConfig.API_BASE_URL
    }

    fun save(context: Context, url: String): String {
        val normalized = normalize(url)
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, normalized).apply()
        return normalized
    }

    fun normalize(url: String): String {
        val t = url.trim()
        return if (t.endsWith("/")) t else "$t/"
    }
}
