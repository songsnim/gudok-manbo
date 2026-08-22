package com.contentscurator.ui.feed

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.contentscurator.data.ServerResolver
import com.contentscurator.data.api.FeedItem
import com.contentscurator.data.api.PreviewItem
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.data.repository.FeedRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

sealed interface FeedUiState {
    data object Loading : FeedUiState
    data class Success(
        val items: List<FeedItem>,
        val readSlugs: Set<String>,
        val avatars: Map<String, String> = emptyMap(),  // author -> avatar_url
    ) : FeedUiState
    data class Error(val message: String) : FeedUiState
}

class FeedViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = FeedRepository(AppDatabase.getInstance(app))

    private val _uiState = MutableStateFlow<FeedUiState>(FeedUiState.Loading)
    val uiState: StateFlow<FeedUiState> = _uiState

    init { load() }

    fun load() {
        viewModelScope.launch {
            _uiState.value = FeedUiState.Loading
            ServerResolver.ensure(getApplication())
            runCatching {
                val items = repo.getAllItems()
                val readSlugs = repo.getAllReadSlugs()
                // 아바타는 목록 표시용 부가 정보 — 실패해도 피드는 보여준다
                val avatars = runCatching {
                    repo.getSubscriptions()
                        .mapNotNull { s -> s.avatar_url?.takeIf { it.isNotBlank() }?.let { s.author to it } }
                        .toMap()
                }.getOrDefault(emptyMap())
                _uiState.value = FeedUiState.Success(items, readSlugs, avatars)
            }.onFailure {
                _uiState.value = FeedUiState.Error(it.message ?: "알 수 없는 오류")
            }
        }
    }

    // ── 영상 검색 ──
    private val _searchResults = MutableStateFlow<List<PreviewItem>>(emptyList())
    val searchResults: StateFlow<List<PreviewItem>> = _searchResults
    private val _searchLoading = MutableStateFlow(false)
    val searchLoading: StateFlow<Boolean> = _searchLoading
    private val _addingUrls = MutableStateFlow<Set<String>>(emptySet())
    val addingUrls: StateFlow<Set<String>> = _addingUrls
    private val _addedUrls = MutableStateFlow<Set<String>>(emptySet())
    val addedUrls: StateFlow<Set<String>> = _addedUrls

    fun searchVideos(query: String) {
        if (query.isBlank()) return
        viewModelScope.launch {
            _searchLoading.value = true
            _searchResults.value = runCatching { repo.searchVideos(query) }.getOrDefault(emptyList())
            _searchLoading.value = false
        }
    }

    fun clearSearch() {
        _searchResults.value = emptyList()
    }

    fun addToFeed(item: PreviewItem) {
        viewModelScope.launch {
            _addingUrls.value += item.source_url
            val result = runCatching { repo.addToFeed(item) }.getOrNull()
            _addingUrls.value -= item.source_url
            if (result?.status == "added" || result?.status == "exists") {
                _addedUrls.value += item.source_url
                load()
            }
        }
    }

    fun markRead(slug: String) {
        viewModelScope.launch {
            repo.markRead(slug)
            val current = _uiState.value
            if (current is FeedUiState.Success) {
                _uiState.value = current.copy(readSlugs = current.readSlugs + slug)
            }
        }
    }

    /** Feed → Collection 이동. 성공하면 피드 목록에서 사라진다. */
    fun collect(slug: String, onDone: () -> Unit) {
        viewModelScope.launch {
            val ok = runCatching { repo.collectItem(slug) }.isSuccess
            val current = _uiState.value
            if (ok && current is FeedUiState.Success) {
                _uiState.value = current.copy(items = current.items.filterNot { it.slug == slug })
            }
            onDone()
        }
    }

    fun delete(slug: String, onDone: () -> Unit) {
        viewModelScope.launch {
            runCatching { repo.deleteFeedItem(slug) }
            val current = _uiState.value
            if (current is FeedUiState.Success) {
                _uiState.value = current.copy(items = current.items.filterNot { it.slug == slug })
            }
            onDone()
        }
    }
}
