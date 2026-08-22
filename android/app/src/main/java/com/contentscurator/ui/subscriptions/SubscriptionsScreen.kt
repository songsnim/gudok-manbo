package com.contentscurator.ui.subscriptions

import android.app.Application
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.contentscurator.data.api.PreviewItem
import com.contentscurator.data.api.SearchResult
import com.contentscurator.data.api.Subscription
import com.contentscurator.data.api.SubscriptionRequest
import com.contentscurator.data.ServerPrefs
import com.contentscurator.data.ServerResolver
import com.contentscurator.data.api.RetrofitClient
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.data.repository.FeedRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

// ── URL 자동 파싱 ──────────────────────────────────────────────────────────────

/** 파싱은 됐지만 구독은 못 하는 URL (Threads/X/Dev.to). */
const val UNSUPPORTED = "unsupported"

data class ParsedSub(
    val platform: String,
    val author: String,
    val channelId: String?,
    val feedUrl: String?,
    val username: String?,
    val hint: String? = null,
)

fun parseUrl(raw: String): ParsedSub? {
    val url = raw.trim()
    if (url.isBlank()) return null
    return when {
        "youtube.com" in url || "youtu.be" in url -> {
            val channelId = Regex("channel/([A-Za-z0-9_-]{20,})").find(url)?.groupValues?.get(1)
                ?: Regex("[?&]channel_id=([A-Za-z0-9_-]+)").find(url)?.groupValues?.get(1)
            val handle = Regex("youtube\\.com/@([^/?]+)").find(url)?.groupValues?.get(1)
            if (channelId != null) {
                ParsedSub("youtube", "", channelId, null, null)
            } else if (handle != null) {
                ParsedSub("youtube", handle, null, null, null,
                    hint = "채널 ID(UCxx...)가 필요합니다.\n채널 페이지 소스에서 'channel_id=' 검색 후 입력하세요.")
            } else {
                ParsedSub("youtube", "", null, null, null, hint = "채널 URL 또는 채널 ID를 확인해주세요.")
            }
        }
        ".substack.com" in url -> {
            val pub = Regex("([^/.]+)\\.substack\\.com").find(url)?.groupValues?.get(1) ?: ""
            ParsedSub("substack", pub, null, null, pub)
        }
        "medium.com" in url -> {
            val username = Regex("medium\\.com/(@[^/?]+)").find(url)?.groupValues?.get(1)
                ?: Regex("medium\\.com/([^/@?][^/?]*)").find(url)?.groupValues?.get(1) ?: ""
            ParsedSub("medium", username, null, null, username)
        }
        "threads.net" in url || "twitter.com" in url || "x.com" in url || "dev.to" in url ->
            ParsedSub(UNSUPPORTED, "", null, null, null, hint = "지원하지 않는 플랫폼입니다.")
        "linkedin.com" in url -> {
            val name = Regex("linkedin\\.com/(?:company|in)/([^/?]+)").find(url)?.groupValues?.get(1) ?: ""
            ParsedSub("linkedin", name, null, url, null)
        }
        "hashnode" in url -> {
            val username = Regex("([^.]+)\\.hashnode\\.dev").find(url)?.groupValues?.get(1) ?: ""
            ParsedSub("rss", username, null, "https://$username.hashnode.dev/rss.xml", null)
        }
        "news.ycombinator.com" in url || "hnrss.org" in url ->
            ParsedSub("hackernews", "HackerNews", null, null, "frontpage")
        else ->
            ParsedSub("rss", url.removePrefix("https://").removePrefix("http://").substringBefore("/"), url, null, null)
    }
}

fun platformColor(platform: String): Color = when (platform.lowercase()) {
    "youtube" -> Color(0xFFFF0000)
    // 원래 브랜드색이 검정인 플랫폼은 다크 배경에서 안 보이므로 밝은 회색으로
    "medium" -> Color(0xFF3C4043)
    "linkedin" -> Color(0xFF0A66C2)
    "substack" -> Color(0xFFFF6719)
    "hackernews" -> Color(0xFFFF6600)
    else -> Color(0xFF888888)
}

fun platformLabel(platform: String): String = when (platform.lowercase()) {
    "youtube" -> "YouTube"
    "medium" -> "Medium"
    "linkedin" -> "LinkedIn"
    "substack" -> "Substack"
    "hackernews" -> "HackerNews"
    "rss" -> "RSS"
    UNSUPPORTED -> "미지원"
    else -> platform
}

// ── ViewModel ─────────────────────────────────────────────────────────────────

class SubscriptionsViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = FeedRepository(AppDatabase.getInstance(app))

    private val _items = MutableStateFlow<List<Subscription>>(emptyList())
    val items: StateFlow<List<Subscription>> = _items

    private val _searchResults = MutableStateFlow<List<SearchResult>>(emptyList())
    val searchResults: StateFlow<List<SearchResult>> = _searchResults

    private val _searchLoading = MutableStateFlow(false)
    val searchLoading: StateFlow<Boolean> = _searchLoading

    private val _subscribedIds = MutableStateFlow<Set<String>>(emptySet())
    val subscribedIds: StateFlow<Set<String>> = _subscribedIds

    // ── 미리보기 ──
    private val _previewSub = MutableStateFlow<Subscription?>(null)
    val previewSub: StateFlow<Subscription?> = _previewSub

    private val _previewItems = MutableStateFlow<List<PreviewItem>>(emptyList())
    val previewItems: StateFlow<List<PreviewItem>> = _previewItems

    private val _previewLoading = MutableStateFlow(false)
    val previewLoading: StateFlow<Boolean> = _previewLoading

    private val _previewLoadingMore = MutableStateFlow(false)
    val previewLoadingMore: StateFlow<Boolean> = _previewLoadingMore

    private var previewCursor: String? = null

    private val _addingUrls = MutableStateFlow<Set<String>>(emptySet())
    val addingUrls: StateFlow<Set<String>> = _addingUrls

    private val _addedUrls = MutableStateFlow<Set<String>>(emptySet())
    val addedUrls: StateFlow<Set<String>> = _addedUrls

    private val _toast = MutableStateFlow<String?>(null)
    val toast: StateFlow<String?> = _toast

    private val _dailyQuota = MutableStateFlow(10)
    val dailyQuota: StateFlow<Int> = _dailyQuota

    private val _serverUrl = MutableStateFlow(ServerPrefs.load(app))
    val serverUrl: StateFlow<String> = _serverUrl

    init { load(); loadSettings() }

    fun saveServerUrl(url: String) {
        val normalized = ServerPrefs.save(getApplication(), url)
        RetrofitClient.setBaseUrl(normalized)
        _serverUrl.value = normalized
        _toast.value = "서버 주소 저장됨"
        load(); loadSettings()  // 새 주소로 재시도
    }

    fun loadSettings() = viewModelScope.launch {
        runCatching { repo.getSettings().daily_quota?.let { _dailyQuota.value = it } }
    }

    fun saveQuota(n: Int) = viewModelScope.launch {
        runCatching { repo.updateSettings(dailyQuota = n).daily_quota?.let { _dailyQuota.value = it } }
            .onSuccess { _toast.value = "일일 할당량: ${_dailyQuota.value}개" }
    }

    fun setPriority(id: String, priority: Int) = viewModelScope.launch {
        runCatching { repo.setPriority(id, priority); load() }
    }

    fun load() = viewModelScope.launch {
        ServerResolver.ensure(getApplication())
        runCatching {
            val subs = repo.getSubscriptions()
            _items.value = subs
            _subscribedIds.value = subs.mapNotNull { it.channel_id }.toSet() +
                subs.mapNotNull { it.feed_url }.toSet()
        }
    }

    fun add(req: SubscriptionRequest) = viewModelScope.launch {
        runCatching { repo.addSubscription(req); load() }
    }

    fun addFromSearch(result: SearchResult) {
        add(SubscriptionRequest(
            platform = result.platform,
            author = result.name,
            channel_id = result.channel_id,
            feed_url = result.handle.takeIf { result.platform == "linkedin" },
            username = result.handle.takeIf { result.platform !in setOf("youtube", "linkedin") },
            avatar_url = result.avatar_url,
        ))
    }

    fun delete(id: String) = viewModelScope.launch {
        runCatching { repo.deleteSubscription(id); load() }
    }

    fun search(query: String, platform: String) = viewModelScope.launch {
        if (query.isBlank()) return@launch
        _searchLoading.value = true
        _searchResults.value = emptyList()
        runCatching { _searchResults.value = repo.search(query, platform) }
        _searchLoading.value = false
    }

    fun clearSearch() { _searchResults.value = emptyList() }

    fun openPreview(sub: Subscription) = viewModelScope.launch {
        _previewSub.value = sub
        _previewItems.value = emptyList()
        _addedUrls.value = emptySet()
        previewCursor = null
        _previewLoading.value = true
        runCatching { repo.preview(sub.id) }
            .onSuccess { _previewItems.value = it.items; previewCursor = it.next_cursor }
            .onFailure { _toast.value = "미리보기 실패: ${it.message}" }
        _previewLoading.value = false
    }

    /** 스크롤 끝 도달 시 이전 영상 이어서 로드. 커서 없으면 무시. */
    fun loadMorePreview() {
        val sub = _previewSub.value ?: return
        val cursor = previewCursor ?: return
        if (_previewLoadingMore.value || _previewLoading.value) return
        _previewLoadingMore.value = true
        viewModelScope.launch {
            runCatching { repo.preview(sub.id, cursor) }
                .onSuccess {
                    val seen = _previewItems.value.mapTo(mutableSetOf()) { i -> i.source_url }
                    _previewItems.value += it.items.filter { i -> i.source_url !in seen }
                    previewCursor = it.next_cursor
                }
                .onFailure { _toast.value = "추가 로드 실패: ${it.message}" }
            _previewLoadingMore.value = false
        }
    }

    fun closePreview() {
        _previewSub.value = null
        _previewItems.value = emptyList()
        previewCursor = null
    }

    fun addToFeed(item: PreviewItem) = viewModelScope.launch {
        _addingUrls.value = _addingUrls.value + item.source_url
        runCatching { repo.addToFeed(item) }
            .onSuccess { result ->
                when (result.status) {
                    "added" -> { _addedUrls.value = _addedUrls.value + item.source_url; _toast.value = "피드에 추가됨" }
                    "exists" -> _toast.value = "이미 피드에 있습니다"
                    else -> _toast.value = result.reason ?: "추가 실패"
                }
            }
            .onFailure { _toast.value = "추가 실패: ${it.message}" }
        _addingUrls.value = _addingUrls.value - item.source_url
    }

    fun clearToast() { _toast.value = null }
}

// ── UI ────────────────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SubscriptionsScreen(vm: SubscriptionsViewModel = viewModel()) {
    val items by vm.items.collectAsStateWithLifecycle()
    val previewSub by vm.previewSub.collectAsStateWithLifecycle()
    val toast by vm.toast.collectAsStateWithLifecycle()
    var showAddDialog by remember { mutableStateOf(false) }
    var showSearchSheet by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }

    val snackbarHost = remember { SnackbarHostState() }
    LaunchedEffect(toast) {
        toast?.let { snackbarHost.showSnackbar(it); vm.clearToast() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("구독 관리") },
                actions = {
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Default.Settings, contentDescription = "설정")
                    }
                    IconButton(onClick = { showSearchSheet = true }) {
                        Icon(Icons.Default.Search, contentDescription = "채널 검색")
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHost) },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddDialog = true }) {
                Icon(Icons.Default.Add, contentDescription = "URL로 추가")
            }
        }
    ) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(
                top = padding.calculateTopPadding() + 8.dp,
                bottom = padding.calculateBottomPadding() + 88.dp,
                start = 0.dp,
                end = 0.dp,
            ),
            modifier = Modifier.fillMaxSize()
        ) {
            items(items, key = { it.id }) { sub ->
                ListItem(
                    modifier = Modifier.clickable { vm.openPreview(sub) },
                    leadingContent = { PlatformBadge(sub.platform, size = 28) },
                    headlineContent = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            if (!sub.avatar_url.isNullOrBlank()) {
                                AsyncImage(
                                    model = sub.avatar_url,
                                    contentDescription = null,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.size(28.dp).clip(CircleShape),
                                )
                                Spacer(Modifier.width(8.dp))
                            }
                            Text(
                                sub.author,
                                fontWeight = FontWeight.Medium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f, fill = false),
                            )
                            Spacer(Modifier.width(8.dp))
                            PriorityChip(
                                priority = sub.priority,
                                onClick = { vm.setPriority(sub.id, nextPriority(sub.priority)) },
                            )
                        }
                    },
                    trailingContent = {
                        IconButton(onClick = { vm.delete(sub.id) }) {
                            Icon(Icons.Default.Delete, contentDescription = "삭제")
                        }
                    }
                )
                HorizontalDivider()
            }
        }
    }

    if (showAddDialog) {
        AddByUrlDialog(
            onDismiss = { showAddDialog = false },
            onConfirm = { req -> vm.add(req); showAddDialog = false }
        )
    }

    if (showSearchSheet) {
        SearchDialog(
            vm = vm,
            onDismiss = { vm.clearSearch(); showSearchSheet = false }
        )
    }

    previewSub?.let { sub ->
        PreviewDialog(vm = vm, sub = sub, onDismiss = { vm.closePreview() })
    }

    if (showSettings) {
        QuotaDialog(vm = vm, onDismiss = { showSettings = false })
    }
}

// ── 우선순위 ──────────────────────────────────────────────────────────────────

fun nextPriority(p: Int): Int = when (p) { 1 -> 2; 2 -> 3; else -> 1 }

private fun priorityLabel(p: Int) = "P$p"
private fun priorityColor(p: Int) = when (p) {
    1 -> Color(0xFFE53935); 3 -> Color(0xFF1E88E5); else -> Color(0xFF9E9E9E)
}

@Composable
private fun PriorityChip(priority: Int, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(MaterialTheme.shapes.small)
            .background(priorityColor(priority).copy(alpha = 0.15f))
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 2.dp),
    ) {
        Text(
            priorityLabel(priority),
            fontSize = 11.sp,
            color = priorityColor(priority),
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
private fun QuotaDialog(vm: SubscriptionsViewModel, onDismiss: () -> Unit) {
    val quota by vm.dailyQuota.collectAsStateWithLifecycle()
    val serverUrl by vm.serverUrl.collectAsStateWithLifecycle()
    var text by remember(quota) { mutableStateOf(quota.toString()) }
    var urlText by remember(serverUrl) { mutableStateOf(serverUrl) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("설정") },
        text = {
            Column {
                Text(
                    "백엔드 서버 주소입니다. 집/외부(터널) 주소를 바꿀 때 입력하세요.",
                    fontSize = 13.sp, color = MaterialTheme.colorScheme.outline,
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = urlText,
                    onValueChange = { urlText = it },
                    label = { Text("서버 주소") },
                    placeholder = { Text("http://192.168.0.10:8000/") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(20.dp))
                Text(
                    "자동 수집 시 하루에 모을 글/영상 개수입니다.\n우선순위 높은 채널부터 채웁니다.",
                    fontSize = 13.sp, color = MaterialTheme.colorScheme.outline,
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it.filter(Char::isDigit) },
                    label = { Text("할당량 (개)") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                enabled = text.toIntOrNull()?.let { it > 0 } == true,
                onClick = {
                    if (urlText.isNotBlank() && urlText != serverUrl) vm.saveServerUrl(urlText)
                    text.toIntOrNull()?.let { vm.saveQuota(it) }
                    onDismiss()
                },
            ) { Text("저장") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("취소") } }
    )
}

// ── 최신 글/영상 미리보기 Dialog ──────────────────────────────────────────────

@Composable
private fun PreviewDialog(
    vm: SubscriptionsViewModel,
    sub: Subscription,
    onDismiss: () -> Unit,
) {
    val items by vm.previewItems.collectAsStateWithLifecycle()
    val loading by vm.previewLoading.collectAsStateWithLifecycle()
    val loadingMore by vm.previewLoadingMore.collectAsStateWithLifecycle()
    val addingUrls by vm.addingUrls.collectAsStateWithLifecycle()
    val addedUrls by vm.addedUrls.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()

    // 끝에서 5개 남으면 다음 페이지 요청
    LaunchedEffect(listState, items.size) {
        snapshotFlow { listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0 }
            .collect { last -> if (items.isNotEmpty() && last >= items.size - 5) vm.loadMorePreview() }
    }

    AlertDialog(
        // 기본 폭이 좁아서 해제. 좌우 여백을 남겨 뒤 화면이 보이게 한다
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        properties = DialogProperties(usePlatformDefaultWidth = false),
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                PlatformBadge(sub.platform, size = 28)
                Spacer(Modifier.width(8.dp))
                Text(sub.author, style = MaterialTheme.typography.titleMedium,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        },
        text = {
            when {
                loading -> Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                items.isEmpty() -> Text(
                    "미리보기를 가져올 수 없습니다.\n(LinkedIn은 쿠키 설정 필요)",
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(vertical = 24.dp),
                )
                else -> LazyColumn(
                    state = listState,
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                    modifier = Modifier.heightIn(max = 480.dp),
                ) {
                    items(items, key = { it.source_url }) { item ->
                        val added = item.in_feed || item.source_url in addedUrls
                        PreviewRow(
                            item = item,
                            added = added,
                            adding = item.source_url in addingUrls,
                            onAdd = { vm.addToFeed(item) },
                        )
                        HorizontalDivider()
                    }
                    if (loadingMore) item {
                        Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("닫기") } },
    )
}

@Composable
internal fun PreviewRow(
    item: PreviewItem,
    added: Boolean,
    adding: Boolean,
    onAdd: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(enabled = !added && !adding) { onAdd() }
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (item.type == "video" && !item.thumbnail.isNullOrBlank()) {
            AsyncImage(
                model = item.thumbnail,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(width = 80.dp, height = 45.dp)
                    .clip(MaterialTheme.shapes.small),
            )
            Spacer(Modifier.width(12.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(item.title, fontSize = 14.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (item.date.isNotBlank()) {
                Text(item.date, fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            }
        }
        Spacer(Modifier.width(8.dp))
        when {
            adding -> CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            added -> Text("피드에 있음", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
            else -> FilledTonalButton(
                onClick = onAdd,
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
            ) { Text("담기", fontSize = 13.sp) }
        }
    }
}

// ── 플랫폼 배지 ────────────────────────────────────────────────────────────────

@Composable
fun PlatformBadge(platform: String, size: Int = 36) {
    val emoji = when (platform.lowercase()) {
        "youtube" -> "▶"; "medium" -> "M"; "linkedin" -> "in"
        "substack" -> "S"; "hackernews" -> "Y"; else -> "·"
    }
    Box(
        modifier = Modifier
            .size(size.dp)
            .background(platformColor(platform), shape = MaterialTheme.shapes.small),
        contentAlignment = Alignment.Center,
    ) {
        Text(emoji, color = Color.White, fontSize = (size * 0.36f).sp, fontWeight = FontWeight.Bold)
    }
}

// ── 채널 검색 Dialog ──────────────────────────────────────────────────────────

@Composable
private fun SearchDialog(vm: SubscriptionsViewModel, onDismiss: () -> Unit) {
    val searchResults by vm.searchResults.collectAsStateWithLifecycle()
    val searchLoading by vm.searchLoading.collectAsStateWithLifecycle()
    val subscribedIds by vm.subscribedIds.collectAsStateWithLifecycle()

    var query by remember { mutableStateOf("") }
    var platform by remember { mutableStateOf("youtube") }
    val platforms = listOf(
        "youtube" to "YouTube",
        "medium" to "Medium",
    )

    AlertDialog(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        properties = DialogProperties(usePlatformDefaultWidth = false),
        onDismissRequest = onDismiss,
        title = { Text("채널 / 계정 검색") },
        text = {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 480.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            // 플랫폼 선택
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(platforms) { (key, label) ->
                    FilterChip(
                        selected = platform == key,
                        onClick = { platform = key; vm.clearSearch() },
                        label = { Text(label) },
                    )
                }
            }
            Spacer(Modifier.height(12.dp))

            // 검색 입력
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("채널명, 키워드 입력") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                trailingIcon = {
                    if (searchLoading) {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    } else {
                        IconButton(onClick = { vm.search(query, platform) }) {
                            Icon(Icons.Default.Search, contentDescription = null)
                        }
                    }
                },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { vm.search(query, platform) }),
            )
            Spacer(Modifier.height(8.dp))

            // 결과 목록
            searchResults.forEach { result ->
                val alreadySubscribed = result.channel_id in subscribedIds ||
                    result.handle in subscribedIds
                SearchResultRow(
                    result = result,
                    alreadySubscribed = alreadySubscribed,
                    onAdd = { vm.addFromSearch(result) },
                )
                HorizontalDivider()
            }

            if (!searchLoading && searchResults.isEmpty() && query.isNotBlank()) {
                Text("결과 없음", color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(vertical = 16.dp).align(Alignment.CenterHorizontally))
            }
        }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("닫기") } },
    )
}

@Composable
private fun SearchResultRow(
    result: SearchResult,
    alreadySubscribed: Boolean,
    onAdd: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PlatformBadge(result.platform, size = 40)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (!result.avatar_url.isNullOrBlank()) {
                    AsyncImage(
                        model = result.avatar_url,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.size(20.dp).clip(CircleShape),
                    )
                    Spacer(Modifier.width(6.dp))
                }
                Text(result.name, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            if (result.subscriber_count.isNotBlank()) {
                Text(result.subscriber_count, fontSize = 11.sp, color = MaterialTheme.colorScheme.outline)
            }
            if (result.description.isNotBlank()) {
                Text(result.description, fontSize = 12.sp, maxLines = 2,
                    overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Spacer(Modifier.width(8.dp))
        if (alreadySubscribed) {
            Text("구독중", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
        } else {
            FilledTonalButton(onClick = onAdd, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)) {
                Text("+구독", fontSize = 13.sp)
            }
        }
    }
}

// ── URL로 추가 다이얼로그 ──────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddByUrlDialog(
    onDismiss: () -> Unit,
    onConfirm: (SubscriptionRequest) -> Unit,
) {
    var urlInput by remember { mutableStateOf("") }
    var authorInput by remember { mutableStateOf("") }
    var channelIdInput by remember { mutableStateOf("") }

    val parsed = remember(urlInput) { parseUrl(urlInput) }

    LaunchedEffect(parsed) {
        if (parsed != null && parsed.author.isNotBlank()) authorInput = parsed.author
        if (parsed?.channelId != null) channelIdInput = parsed.channelId
    }

    val isYoutube = parsed?.platform == "youtube"
    val canConfirm = parsed != null && parsed.platform != UNSUPPORTED &&
        authorInput.isNotBlank() && (!isYoutube || channelIdInput.isNotBlank())

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("URL로 구독 추가") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = urlInput, onValueChange = { urlInput = it },
                    label = { Text("URL 붙여넣기") },
                    placeholder = { Text("https://...") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
                if (parsed != null) {
                    Row(verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PlatformBadge(parsed.platform, size = 28)
                        Text(platformLabel(parsed.platform), style = MaterialTheme.typography.labelLarge)
                    }
                }
                parsed?.hint?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error)
                }
                if (isYoutube) {
                    OutlinedTextField(
                        value = channelIdInput, onValueChange = { channelIdInput = it },
                        label = { Text("채널 ID (UCxx...)") },
                        modifier = Modifier.fillMaxWidth(), singleLine = true,
                    )
                }
                OutlinedTextField(
                    value = authorInput, onValueChange = { authorInput = it },
                    label = { Text("표시 이름") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
            }
        },
        confirmButton = {
            TextButton(
                enabled = canConfirm,
                onClick = {
                    val p = parsed ?: return@TextButton
                    onConfirm(SubscriptionRequest(
                        platform = p.platform, author = authorInput.trim(),
                        channel_id = if (isYoutube) channelIdInput.trim() else p.channelId,
                        feed_url = p.feedUrl, username = p.username,
                    ))
                }
            ) { Text("추가") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("취소") } }
    )
}
