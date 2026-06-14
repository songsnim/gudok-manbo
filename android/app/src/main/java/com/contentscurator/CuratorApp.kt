package com.contentscurator

import android.app.Application
import com.contentscurator.data.ServerPrefs
import com.contentscurator.data.api.RetrofitClient
import com.contentscurator.work.FeedSyncWorker

class CuratorApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // 저장된 백엔드 주소를 적용(없으면 BuildConfig 기본값)
        RetrofitClient.setBaseUrl(ServerPrefs.load(this))
        FeedSyncWorker.schedule(this)
    }
}
