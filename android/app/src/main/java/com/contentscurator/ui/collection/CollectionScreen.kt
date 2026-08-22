package com.contentscurator.ui.collection

import android.app.Application
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.contentscurator.data.api.FeedItem
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.data.repository.FeedRepository
import com.contentscurator.ui.feed.FeedItemRow
import com.contentscurator.ui.feed.ItemDetailScreen
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class CollectionViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = FeedRepository(AppDatabase.getInstance(app))

    private val _items = MutableStateFlow<List<FeedItem>?>(null)  // null = 로딩 중
    val items: StateFlow<List<FeedItem>?> = _items

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    init { load() }

    fun load() = viewModelScope.launch {
        _items.value = null
        _error.value = null
        runCatching { repo.getCollections() }
            .onSuccess { _items.value = it }
            .onFailure { _items.value = emptyList(); _error.value = it.message ?: "알 수 없는 오류" }
    }

    /** 컬렉션에서 제거 = 완전 삭제. 피드로 돌아가지 않는다. */
    fun delete(slug: String, onDone: () -> Unit) = viewModelScope.launch {
        val ok = runCatching { repo.deleteCollectionItem(slug) }.isSuccess
        if (ok) _items.value = _items.value?.filterNot { it.slug == slug }
        onDone()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CollectionScreen(vm: CollectionViewModel = viewModel()) {
    val items by vm.items.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    var selected by remember { mutableStateOf<FeedItem?>(null) }

    if (selected != null) {
        ItemDetailScreen(
            item = selected!!,
            onBack = { selected = null },
            onDelete = { vm.delete(selected!!.slug) { selected = null } },
            // 이미 컬렉션에 있는 글 — 담기 버튼 없음
            onCollect = null,
            deleteTitle = "컬렉션에서 삭제",
            deleteMessage = "이 글을 완전히 삭제할까요?\n피드로 돌아가지 않습니다. 되돌릴 수 없습니다.",
        )
        return
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("컬렉션") },
                actions = {
                    IconButton(onClick = { vm.load() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "새로고침")
                    }
                },
            )
        }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            val list = items
            when {
                list == null -> CircularProgressIndicator(Modifier.align(Alignment.Center))
                error != null -> Column(
                    Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("연결 실패: $error", color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = { vm.load() }) { Text("재시도") }
                }
                list.isEmpty() -> Text(
                    "아직 담은 글이 없습니다.\n피드에서 글을 열고 담기 버튼을 누르세요.",
                    Modifier.align(Alignment.Center).padding(32.dp),
                    color = MaterialTheme.colorScheme.outline,
                )
                else -> LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
                    items(list, key = { it.slug }) { item ->
                        // 컬렉션은 읽음 흐림 처리를 하지 않는다 — 이미 읽고 남긴 글이다
                        FeedItemRow(
                            item = item,
                            isRead = false,
                            avatarUrl = null,
                            onClick = { selected = item },
                        )
                    }
                }
            }
        }
    }
}
