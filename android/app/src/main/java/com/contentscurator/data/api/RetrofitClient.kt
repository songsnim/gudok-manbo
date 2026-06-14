package com.contentscurator.data.api

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import com.contentscurator.BuildConfig
import java.util.concurrent.TimeUnit

object RetrofitClient {
    private val moshi = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()

    private val okhttp = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(300, TimeUnit.SECONDS)   // LLM 자막→글 변환 대기 (영상 길면 오래 걸림)
        .writeTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        })
        .build()

    // 백엔드 주소는 런타임에 바꿀 수 있다(앱 설정에서 입력). BuildConfig 값이 기본값.
    @Volatile private var baseUrl: String = BuildConfig.API_BASE_URL
    @Volatile private var current: ApiService = build(baseUrl)

    private fun build(url: String): ApiService = Retrofit.Builder()
        .baseUrl(url)
        .client(okhttp)
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()
        .create(ApiService::class.java)

    val api: ApiService get() = current

    fun baseUrl(): String = baseUrl

    /** 새 백엔드 주소 적용. url은 정규화돼(끝에 "/") 들어와야 한다. */
    fun setBaseUrl(url: String) {
        baseUrl = url
        current = build(url)
    }
}
