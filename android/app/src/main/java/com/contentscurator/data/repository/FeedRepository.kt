package com.contentscurator.data.repository

import com.contentscurator.data.api.AddItemRequest
import com.contentscurator.data.api.AddItemResult
import com.contentscurator.data.api.AppSettings
import com.contentscurator.data.api.DiscoverRequest
import com.contentscurator.data.api.SubscriptionPatch
import com.contentscurator.data.api.DiscoverResult
import com.contentscurator.data.api.FeedItem
import com.contentscurator.data.api.PreviewItem
import com.contentscurator.data.api.RetrofitClient
import com.contentscurator.data.api.SearchResult
import com.contentscurator.data.api.Subscription
import com.contentscurator.data.api.SubscriptionRequest
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.data.db.ReadStatusEntity

class FeedRepository(private val db: AppDatabase) {

    suspend fun getTodayFeed(): List<FeedItem> = RetrofitClient.api.getTodayFeed()

    suspend fun getAllItems(): List<FeedItem> = RetrofitClient.api.getAllItems()

    suspend fun getItem(slug: String): FeedItem = RetrofitClient.api.getItem(slug)

    suspend fun getSubscriptions(): List<Subscription> = RetrofitClient.api.getSubscriptions()

    suspend fun addSubscription(req: SubscriptionRequest): Subscription =
        RetrofitClient.api.addSubscription(req)

    suspend fun deleteSubscription(id: String) = RetrofitClient.api.deleteSubscription(id)

    suspend fun setPriority(id: String, priority: Int): Subscription =
        RetrofitClient.api.patchSubscription(id, SubscriptionPatch(priority))

    suspend fun deleteFeedItem(slug: String) = RetrofitClient.api.deleteFeedItem(slug)

    suspend fun getSettings(): AppSettings = RetrofitClient.api.getSettings()

    suspend fun updateSettings(dailyQuota: Int): AppSettings =
        RetrofitClient.api.putSettings(AppSettings(dailyQuota))

    suspend fun isRead(slug: String): Boolean = db.readStatusDao().isRead(slug)

    suspend fun markRead(slug: String) =
        db.readStatusDao().markRead(ReadStatusEntity(slug))

    suspend fun markUnread(slug: String) = db.readStatusDao().markUnread(slug)

    suspend fun getAllReadSlugs(): Set<String> =
        db.readStatusDao().getAllReadSlugs().toSet()

    suspend fun triggerCollect() = RetrofitClient.api.collect()

    suspend fun discover(query: String): DiscoverResult =
        RetrofitClient.api.discover(DiscoverRequest(query))

    suspend fun search(q: String, platform: String): List<SearchResult> =
        RetrofitClient.api.search(q, platform).results

    suspend fun preview(subId: String): List<PreviewItem> =
        RetrofitClient.api.preview(subId).items

    suspend fun addToFeed(item: PreviewItem): AddItemResult =
        RetrofitClient.api.addToFeed(AddItemRequest(
            platform = item.platform,
            source_url = item.source_url,
            author = item.author,
            title = item.title,
            type = item.type,
            video_id = item.video_id,
            body = item.body ?: "",
        ))
}
