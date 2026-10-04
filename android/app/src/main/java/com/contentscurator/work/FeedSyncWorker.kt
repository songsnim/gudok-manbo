package com.contentscurator.work

import android.content.Context
import androidx.work.*
import com.contentscurator.widget.cachedCollectHours
import com.contentscurator.widget.refreshWidget
import java.time.Duration
import java.time.LocalDateTime
import java.util.concurrent.TimeUnit

class FeedSyncWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result {
        return runCatching {
            refreshWidget(applicationContext)
            scheduleAfterNextCollect(applicationContext)
            Result.success()
        }.getOrDefault(Result.retry())
    }

    companion object {
        private const val WORK_NAME = "feed_sync"
        private const val AFTER_COLLECT = "feed_sync_after_collect"

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<FeedSyncWorker>(1, TimeUnit.HOURS)
                .setConstraints(networkConstraint())
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )
        }

        /** 지금 한 번 — 앱 시작, 피드에서 Item이 빠졌을 때(담기·삭제). */
        fun runNow(context: Context) {
            WorkManager.getInstance(context).enqueue(
                OneTimeWorkRequestBuilder<FeedSyncWorker>().setConstraints(networkConstraint()).build()
            )
        }

        /** 다음 수집 시각 10분 뒤에 한 번 더 — 1시간 주기를 기다리지 않고 새 글을 위젯에 올린다. */
        private fun scheduleAfterNextCollect(context: Context) {
            val hours = cachedCollectHours(context).ifEmpty { return }
            val now = LocalDateTime.now()
            val next = hours.map { now.toLocalDate().atTime(it, 10) }.firstOrNull { it.isAfter(now) }
                ?: now.toLocalDate().plusDays(1).atTime(hours.min(), 10)
            val request = OneTimeWorkRequestBuilder<FeedSyncWorker>()
                .setInitialDelay(Duration.between(now, next))
                .setConstraints(networkConstraint())
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(AFTER_COLLECT, ExistingWorkPolicy.REPLACE, request)
        }

        private fun networkConstraint() =
            Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
    }
}
