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
    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .build()

    /**
     * 매 호출마다 포인터를 다시 읽어 백엔드 주소를 갱신한다. 실패하면 저장된 주소를 그대로 쓴다.
     * 세션 래치를 두지 않는 이유: 재부팅 직후 백엔드가 뜨기 전에 앱을 열면 옛(죽은) 주소를 한 번
     * 받아 고착될 수 있다 → 매번 재해소해 self-heal 한다(새로고침 한 번이면 라이브 주소로 복구).
     * 캐시버스터 쿼리로 Gist raw의 CDN 캐시(max-age=300)도 우회한다.
     */
    suspend fun ensure(context: Context) {
        if (BuildConfig.POINTER_URL.isBlank()) return
        withContext(Dispatchers.IO) {
            runCatching {
                val sep = if (BuildConfig.POINTER_URL.contains("?")) "&" else "?"
                val req = Request.Builder()
                    .url(BuildConfig.POINTER_URL + sep + "t=" + System.currentTimeMillis())
                    .header("Cache-Control", "no-cache")
                    .build()
                client.newCall(req).execute().use { resp ->
                    val body = resp.body?.string()?.trim()
                    if (resp.isSuccessful && !body.isNullOrBlank() && body.startsWith("http")) {
                        RetrofitClient.setBaseUrl(ServerPrefs.save(context, body))
                    }
                }
            }
        }
    }
}
