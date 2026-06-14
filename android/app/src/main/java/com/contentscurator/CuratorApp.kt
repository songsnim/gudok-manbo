package com.contentscurator

import android.app.Application
import com.contentscurator.work.FeedSyncWorker

class CuratorApp : Application() {
    override fun onCreate() {
        super.onCreate()
        FeedSyncWorker.schedule(this)
    }
}
