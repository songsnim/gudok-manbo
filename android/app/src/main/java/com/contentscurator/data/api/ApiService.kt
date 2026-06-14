package com.contentscurator.data.api

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.http.*

@JsonClass(generateAdapter = true)
data class FeedItem(
    val slug: String,
    val title: String,
    val platform: String,
    val source_url: String,
    val author: String,
    val date: String,
    val subscription: Boolean,
    val body: String,
)

@JsonClass(generateAdapter = true)
data class Subscription(
    val id: String,
    val platform: String,
    val author: String,
    val channel_id: String?,
    val feed_url: String?,
    val avatar_url: String? = null,
    val priority: Int = 2,
)

@JsonClass(generateAdapter = true)
data class SubscriptionRequest(
    val platform: String,
    val author: String,
    val channel_id: String?,
    val feed_url: String?,
    val username: String? = null,
    val avatar_url: String? = null,
    val priority: Int = 2,
)

@JsonClass(generateAdapter = true)
data class SubscriptionPatch(val priority: Int)

@JsonClass(generateAdapter = true)
data class AppSettings(val daily_quota: Int)

@JsonClass(generateAdapter = true)
data class DiscoverRequest(val query: String)

@JsonClass(generateAdapter = true)
data class DiscoverSource(
    val author: String,
    val platform: String,
    val reason: String,
)

@JsonClass(generateAdapter = true)
data class DiscoverResult(
    val added: Int,
    val sources: List<DiscoverSource>,
    val skipped: List<DiscoverSource>,
)

interface ApiService {
    @GET("feed/today")
    suspend fun getTodayFeed(): List<FeedItem>

    @GET("feed/items")
    suspend fun getAllItems(): List<FeedItem>

    @GET("feed/items/{slug}")
    suspend fun getItem(@Path("slug") slug: String): FeedItem

    @GET("subscriptions")
    suspend fun getSubscriptions(): List<Subscription>

    @POST("subscriptions")
    suspend fun addSubscription(@Body body: SubscriptionRequest): Subscription

    @PATCH("subscriptions/{id}")
    suspend fun patchSubscription(@Path("id") id: String, @Body body: SubscriptionPatch): Subscription

    @DELETE("subscriptions/{id}")
    suspend fun deleteSubscription(@Path("id") id: String)

    @DELETE("feed/items/{slug}")
    suspend fun deleteFeedItem(@Path("slug") slug: String)

    @GET("settings")
    suspend fun getSettings(): AppSettings

    @PUT("settings")
    suspend fun putSettings(@Body body: AppSettings): AppSettings

    @POST("agent/collect")
    suspend fun collect(): Map<String, Any>

    @POST("agent/discover")
    suspend fun discover(@Body body: DiscoverRequest): DiscoverResult

    @GET("search")
    suspend fun search(@Query("q") q: String, @Query("platform") platform: String): SearchResponse

    @GET("subscriptions/{id}/preview")
    suspend fun preview(@Path("id") id: String): PreviewResponse

    @POST("feed/add")
    suspend fun addToFeed(@Body body: AddItemRequest): AddItemResult
}

@JsonClass(generateAdapter = true)
data class SearchResult(
    val platform: String,
    val name: String,
    val channel_id: String?,
    val handle: String,
    val description: String,
    val subscriber_count: String,
    val avatar_url: String? = null,
)

@JsonClass(generateAdapter = true)
data class SearchResponse(val results: List<SearchResult>)

@JsonClass(generateAdapter = true)
data class PreviewItem(
    val title: String,
    val source_url: String,
    val date: String,
    val platform: String,
    val author: String,
    val type: String,
    val video_id: String?,
    val thumbnail: String?,
    val in_feed: Boolean,
    val body: String? = null,
)

@JsonClass(generateAdapter = true)
data class PreviewResponse(val items: List<PreviewItem>)

@JsonClass(generateAdapter = true)
data class AddItemRequest(
    val platform: String,
    val source_url: String,
    val author: String,
    val title: String,
    val type: String,
    val video_id: String?,
    val body: String = "",
)

@JsonClass(generateAdapter = true)
data class AddItemResult(
    val status: String,
    val slug: String? = null,
    val reason: String? = null,
)
