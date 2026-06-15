package com.contentscurator.ui.feed

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.contentscurator.data.ServerResolver
import com.contentscurator.data.api.FeedItem
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.data.repository.FeedRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

sealed interface FeedUiState {
    data object Loading : FeedUiState
    data class Success(val items: List<FeedItem>, val readSlugs: Set<String>) : FeedUiState
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
                _uiState.value = FeedUiState.Success(items, readSlugs)
            }.onFailure {
                _uiState.value = FeedUiState.Error(it.message ?: "알 수 없는 오류")
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
