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

    val api: ApiService = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(okhttp)
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()
        .create(ApiService::class.java)
}
