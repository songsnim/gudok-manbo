package com.contentscurator

import android.app.Application
import com.contentscurator.data.ServerPrefs
import com.contentscurator.data.ServerResolver
import com.contentscurator.data.api.RetrofitClient
import com.contentscurator.work.FeedSyncWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class CuratorApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // 저장된 백엔드 주소를 우선 적용(없으면 BuildConfig 기본값) — 즉시 동작용 폴백
        RetrofitClient.setBaseUrl(ServerPrefs.load(this))
        // 고정 포인터에서 현재 백엔드 주소를 자동으로 받아 갱신(외부망 대응)
        CoroutineScope(Dispatchers.IO).launch { ServerResolver.ensure(this@CuratorApp) }
        FeedSyncWorker.schedule(this)
    }
}
