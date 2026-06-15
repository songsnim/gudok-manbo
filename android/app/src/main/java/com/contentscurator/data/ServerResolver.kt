package com.contentscurator.data

import android.content.Context
import com.contentscurator.BuildConfig
import com.contentscurator.data.api.RetrofitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * 백엔드 주소를 '고정 포인터'(BuildConfig.POINTER_URL, 예: GitHub Gist raw)에서 자동으로 읽는다.
 * 터널 주소가 재시작마다 바뀌어도 포인터 URL은 고정이라, 앱에 매번 다시 입력할 필요가 없다.
 */
object ServerResolver {
    @Volatile private var resolved = false

    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .build()

    /** 세션당 1회(성공 시) 포인터를 읽어 백엔드 주소를 갱신. 실패하면 저장된 주소를 그대로 쓴다. */
    suspend fun ensure(context: Context) {
        if (resolved || BuildConfig.POINTER_URL.isBlank()) return
        withContext(Dispatchers.IO) {
            runCatching {
                val req = Request.Builder().url(BuildConfig.POINTER_URL).build()
                client.newCall(req).execute().use { resp ->
                    val body = resp.body?.string()?.trim()
                    if (resp.isSuccessful && !body.isNullOrBlank() && body.startsWith("http")) {
                        RetrofitClient.setBaseUrl(ServerPrefs.save(context, body))
                        resolved = true
                    }
                }
            }
        }
    }
}
