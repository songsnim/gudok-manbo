package com.contentscurator.work

import android.content.Context
import androidx.work.*
import com.contentscurator.data.api.RetrofitClient
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.widget.WidgetItem
import com.contentscurator.widget.updateWidgetData
import java.util.concurrent.TimeUnit

class FeedSyncWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result {
        return runCatching {
            com.contentscurator.data.ServerResolver.ensure(applicationContext)
            val items = RetrofitClient.api.getTodayFeed()
            val readSlugs = AppDatabase.getInstance(applicationContext).readStatusDao().getAllReadSlugs().toSet()
            val widgetItems = items.map { WidgetItem(it.slug, it.title, it.platform, it.slug in readSlugs) }
            updateWidgetData(applicationContext, widgetItems)
            Result.success()
        }.getOrDefault(Result.retry())
    }

    companion object {
        private const val WORK_NAME = "feed_sync"

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<FeedSyncWorker>(1, TimeUnit.HOURS)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )
        }
    }
}
