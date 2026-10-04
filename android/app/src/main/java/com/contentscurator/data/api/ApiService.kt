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
    val published: String = "",  // 매체 게시일. 비어 있으면 date(수집일)로 대체
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

/**
 * 백엔드 app_settings.json. PUT은 부분 갱신 — null 필드는 Moshi가 생략하고
 * 백엔드도 None을 무시하므로, 바꿀 값만 채워 보내면 나머지는 그대로 남는다.
 */
@JsonClass(generateAdapter = true)
data class AppSettings(
    val daily_quota: Int? = null,
    val auto_collect: Boolean? = null,
    val schedule: Map<String, Int>? = null,
    val expire_days: Int? = null,
)

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

    /** lite=true면 body가 빈 문자열 — 위젯용 목록. */
    @GET("feed/items")
    suspend fun getAllItems(@Query("lite") lite: Boolean? = null): List<FeedItem>

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

    @GET("collections")
    suspend fun getCollections(): List<FeedItem>

    /** Feed → Collection 파일 이동. 되돌릴 수 없다. */
    @POST("collections/{slug}")
    suspend fun collectItem(@Path("slug") slug: String)

    /** Collection에서 제거 = 완전 삭제. */
    @DELETE("collections/{slug}")
    suspend fun deleteCollectionItem(@Path("slug") slug: String)

    @GET("stats")
    suspend fun getStats(): Stats

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

    @GET("search/videos")
    suspend fun searchVideos(@Query("q") q: String): PreviewResponse

    @GET("subscriptions/{id}/preview")
    suspend fun preview(
        @Path("id") id: String,
        @Query("cursor") cursor: String? = null,
    ): PreviewResponse

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
    val feed_url: String = "",
)

@JsonClass(generateAdapter = true)
data class PreviewResponse(val items: List<PreviewItem>, val next_cursor: String? = null)

@JsonClass(generateAdapter = true)
data class AddItemRequest(
    val platform: String,
    val source_url: String,
    val author: String,
    val title: String,
    val type: String,
    val date: String = "",
    val video_id: String?,
    val body: String = "",
    val feed_url: String = "",
)

// ── 통계 ──────────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class DateCount(val date: String, val count: Int)

@JsonClass(generateAdapter = true)
data class AuthorCount(val author: String, val count: Int)

@JsonClass(generateAdapter = true)
data class PlatformCount(val platform: String, val count: Int)

@JsonClass(generateAdapter = true)
data class RunFailure(val author: String = "", val reason: String = "")

@JsonClass(generateAdapter = true)
data class CollectRun(
    val at: String,
    val trigger: String,          // schedule | manual | skipped
    val target: Int? = null,
    val collected: Int = 0,
    val slugs: List<String> = emptyList(),
    val failures: List<RunFailure> = emptyList(),
    val expired: List<String> = emptyList(),
    val error: String = "",
)

@JsonClass(generateAdapter = true)
data class Stats(
    val total_feed: Int = 0,
    val total_collection: Int = 0,
    val by_date: List<DateCount> = emptyList(),
    val by_author: List<AuthorCount> = emptyList(),
    val by_platform: List<PlatformCount> = emptyList(),
    val recent_runs: List<CollectRun> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class AddItemResult(
    val status: String,
    val slug: String? = null,
    val reason: String? = null,
)
