package com.contentscurator.ui.feed

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.BookmarkAdd
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.window.DialogProperties
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.activity.compose.BackHandler
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.contentscurator.data.api.FeedItem
import com.contentscurator.ui.subscriptions.PlatformBadge
import com.contentscurator.ui.subscriptions.PreviewRow
import dev.jeziellago.compose.markdowntext.MarkdownText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeedScreen(vm: FeedViewModel = viewModel()) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var selectedItem by remember { mutableStateOf<FeedItem?>(null) }

    if (selectedItem != null) {
        ItemDetailScreen(
            item = selectedItem!!,
            onBack = { selectedItem = null },
            onDelete = { vm.delete(selectedItem!!.slug) { selectedItem = null } },
            onCollect = { vm.collect(selectedItem!!.slug) { selectedItem = null } },
        )
        return
    }

    var showSearch by remember { mutableStateOf(false) }
    var showFilter by remember { mutableStateOf(false) }
    var sort by rememberSaveable { mutableStateOf(SortBy.COLLECTED) }
    var period by rememberSaveable { mutableStateOf(Period.ALL) }
    var author by rememberSaveable { mutableStateOf<String?>(null) }
    var platform by rememberSaveable { mutableStateOf<String?>(null) }
    val filtered = author != null || platform != null || period != Period.ALL

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("컨텐츠 피드") },
                actions = {
                    IconButton(onClick = { showFilter = true }) {
                        Icon(
                            Icons.Default.FilterList,
                            contentDescription = "정렬·필터",
                            tint = if (filtered || sort != SortBy.COLLECTED) MaterialTheme.colorScheme.primary
                                   else LocalContentColor.current,
                        )
                    }
                    IconButton(onClick = { vm.load() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "새로고침")
                    }
                    IconButton(onClick = { showSearch = true }) {
                        Icon(Icons.Default.Search, contentDescription = "영상 검색")
                    }
                }
            )
        }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when (val s = state) {
                is FeedUiState.Loading -> CircularProgressIndicator(Modifier.align(Alignment.Center))
                is FeedUiState.Error -> Column(
                    Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text("연결 실패: ${s.message}", color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = { vm.load() }) { Text("재시도") }
                }
                is FeedUiState.Success -> {
                    val shownItems = remember(s.items, sort, author, platform, period) {
                        sortAndFilter(s.items, sort, author, platform, period)
                    }
                    if (shownItems.isEmpty()) {
                        Text(
                            if (s.items.isEmpty()) "수집된 아이템이 없습니다." else "조건에 맞는 아이템이 없습니다.",
                            Modifier.align(Alignment.Center),
                        )
                    } else {
                        LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
                            items(shownItems, key = { it.slug }) { item ->
                                FeedItemRow(
                                    item = item,
                                    isRead = item.slug in s.readSlugs,
                                    avatarUrl = s.avatars[item.author],
                                    onClick = {
                                        vm.markRead(item.slug)
                                        selectedItem = item
                                    }
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    if (showSearch) {
        VideoSearchDialog(vm = vm, onDismiss = { vm.clearSearch(); showSearch = false })
    }

    if (showFilter) {
        SortFilterDialog(
            items = (state as? FeedUiState.Success)?.items ?: emptyList(),
            sort = sort, author = author, platform = platform, period = period,
            onSort = { sort = it }, onAuthor = { author = it },
            onPlatform = { platform = it }, onPeriod = { period = it },
            onReset = { sort = SortBy.COLLECTED; author = null; platform = null; period = Period.ALL },
            onDismiss = { showFilter = false },
        )
    }
}

// ── 정렬·필터 ────────────────────────────────────────────────────────────────

enum class SortBy(val label: String) {
    COLLECTED("수집순"),   // 서버가 이미 수집 시각 역순으로 준다
    PUBLISHED("게시일순"),
}

enum class Period(val label: String, val days: Long?) {
    ALL("전체", null), WEEK("1주", 7), MONTH("1개월", 30), QUARTER("3개월", 90),
}

private val ISO_DATE = Regex("^\\d{4}-\\d{2}-\\d{2}")

/**
 * 매체 게시일(없으면 수집일)의 YYYY-MM-DD. 기간 필터·게시일 정렬의 기준.
 * ISO가 아니면(RFC822 원문 등) 빈 문자열 — 날짜 불명으로 취급한다.
 */
private fun FeedItem.dateKey(): String =
    ISO_DATE.find(published)?.value ?: ISO_DATE.find(date)?.value ?: ""

private fun sortAndFilter(
    items: List<FeedItem>, sort: SortBy, author: String?, platform: String?, period: Period,
): List<FeedItem> {
    val cutoff = period.days?.let { java.time.LocalDate.now().minusDays(it).toString() }
    val kept = items.filter { item ->
        (author == null || item.author == author) &&
        (platform == null || item.platform.equals(platform, ignoreCase = true)) &&
        // 날짜를 못 읽는 아이템은 기간 필터에서 빼지 않는다
        (cutoff == null || item.dateKey().isEmpty() || item.dateKey() >= cutoff)
    }
    // 날짜 불명("")은 게시일순에서 맨 아래로
    return if (sort == SortBy.PUBLISHED) kept.sortedByDescending { it.dateKey() } else kept
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SortFilterDialog(
    items: List<FeedItem>,
    sort: SortBy, author: String?, platform: String?, period: Period,
    onSort: (SortBy) -> Unit, onAuthor: (String?) -> Unit,
    onPlatform: (String?) -> Unit, onPeriod: (Period) -> Unit,
    onReset: () -> Unit, onDismiss: () -> Unit,
) {
    // 비교가 대소문자 무시라 목록도 맞춘다 — youtube/YouTube가 칩 두 개로 갈리지 않게
    val platforms = remember(items) {
        items.map { it.platform }.filter { it.isNotBlank() }.distinctBy { it.lowercase() }.sorted()
    }
    val authors = remember(items) { items.map { it.author }.filter { it.isNotBlank() }.distinct().sorted() }

    AlertDialog(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        properties = DialogProperties(usePlatformDefaultWidth = false),
        onDismissRequest = onDismiss,
        title = { Text("정렬·필터") },
        text = {
            Column(
                Modifier.fillMaxWidth().heightIn(max = 480.dp).verticalScroll(rememberScrollState())
            ) {
                FilterSection("정렬") {
                    SortBy.entries.forEach { option ->
                        FilterChip(
                            selected = sort == option,
                            onClick = { onSort(option) },
                            label = { Text(option.label) },
                        )
                    }
                }
                FilterSection("기간") {
                    Period.entries.forEach { option ->
                        FilterChip(
                            selected = period == option,
                            onClick = { onPeriod(option) },
                            label = { Text(option.label) },
                        )
                    }
                }
                FilterSection("플랫폼") {
                    FilterChip(platform == null, { onPlatform(null) }, { Text("전체") })
                    platforms.forEach { p ->
                        FilterChip(platform == p, { onPlatform(p) }, { Text(p) })
                    }
                }
                FilterSection("채널") {
                    FilterChip(author == null, { onAuthor(null) }, { Text("전체") })
                    authors.forEach { a ->
                        FilterChip(author == a, { onAuthor(a) }, { Text(a) })
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("닫기") } },
        dismissButton = { TextButton(onClick = onReset) { Text("초기화") } },
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun FilterSection(title: String, content: @Composable FlowRowScope.() -> Unit) {
    Text(title, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 12.dp, bottom = 4.dp))
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
        content = content,
    )
}

// ── 영상 검색 Dialog ──────────────────────────────────────────────────────────

@Composable
private fun VideoSearchDialog(vm: FeedViewModel, onDismiss: () -> Unit) {
    val results by vm.searchResults.collectAsStateWithLifecycle()
    val loading by vm.searchLoading.collectAsStateWithLifecycle()
    val addingUrls by vm.addingUrls.collectAsStateWithLifecycle()
    val addedUrls by vm.addedUrls.collectAsStateWithLifecycle()
    var query by remember { mutableStateOf("") }

    AlertDialog(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        properties = DialogProperties(usePlatformDefaultWidth = false),
        onDismissRequest = onDismiss,
        title = { Text("영상 검색") },
        text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 480.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    placeholder = { Text("키워드 입력") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    trailingIcon = {
                        if (loading) {
                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            IconButton(onClick = { vm.searchVideos(query) }) {
                                Icon(Icons.Default.Search, contentDescription = null)
                            }
                        }
                    },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { vm.searchVideos(query) }),
                )
                Spacer(Modifier.height(8.dp))
                LazyColumn {
                    items(results, key = { it.source_url }) { item ->
                        PreviewRow(
                            item = item,
                            added = item.in_feed || item.source_url in addedUrls,
                            adding = item.source_url in addingUrls,
                            onAdd = { vm.addToFeed(item) },
                        )
                        HorizontalDivider()
                    }
                }
                if (!loading && results.isEmpty() && query.isNotBlank()) {
                    Text("결과 없음", color = MaterialTheme.colorScheme.outline,
                        modifier = Modifier.padding(vertical = 16.dp).align(Alignment.CenterHorizontally))
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("닫기") } },
    )
}

/** YouTube 영상이면 썸네일 URL. 그 외 플랫폼은 null. */
private fun thumbnailUrl(item: FeedItem): String? {
    if (item.platform.lowercase() != "youtube") return null
    val videoId = Regex("[?&]v=([^&]+)").find(item.source_url)?.groupValues?.get(1)
        ?: item.slug.removePrefix("yt-").takeIf { it != item.slug }
        ?: return null
    // hqdefault은 4:3에 레터박스 — Crop으로 16:9로 자르면 검은 띠가 정확히 잘린다
    return "https://i.ytimg.com/vi/$videoId/hqdefault.jpg"
}

/** 피드·컬렉션이 공유하는 목록 행. */
@Composable
fun FeedItemRow(item: FeedItem, isRead: Boolean, avatarUrl: String?, onClick: () -> Unit) {
    val alpha = if (isRead) 0.45f else 1f
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                PlatformBadge(item.platform, size = 20)
                Spacer(Modifier.width(6.dp))
                if (!avatarUrl.isNullOrBlank()) {
                    AsyncImage(
                        model = avatarUrl,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.size(18.dp).clip(CircleShape).alpha(alpha),
                    )
                    Spacer(Modifier.width(6.dp))
                }
                Text(
                    text = item.author,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.primary.copy(alpha = alpha),
                )
            }
            Spacer(Modifier.height(2.dp))
            Text(
                text = item.title,
                fontWeight = if (isRead) FontWeight.Normal else FontWeight.SemiBold,
                fontSize = 15.sp,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = alpha),
            )
            val shown = item.published.ifBlank { item.date }
            if (shown.isNotBlank()) {
                Text(
                    text = shown,
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = alpha),
                )
            }
        }
        thumbnailUrl(item)?.let { url ->
            Spacer(Modifier.width(12.dp))
            AsyncImage(
                model = url,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    // 행 높이(제목 3줄 + 채널/날짜)가 허용하는 최대치 — 16:9 유지
                    .size(width = 152.dp, height = 86.dp)
                    .clip(MaterialTheme.shapes.small)
                    .alpha(alpha),
            )
        }
    }
    HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f))
}

/**
 * Feed와 컬렉션이 공유하는 상세 화면.
 *
 * onCollect가 null이면 컬렉션 담기 아이콘을 그리지 않는다 — 컬렉션 탭에서는 이미 담긴 글이다.
 * deleteMessage는 삭제 확인 문구: Feed는 "다시 담을 수 있다", 컬렉션은 완전 삭제다.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ItemDetailScreen(
    item: FeedItem,
    onBack: () -> Unit,
    onDelete: () -> Unit,
    onCollect: (() -> Unit)? = null,
    deleteTitle: String = "피드에서 삭제",
    deleteMessage: String = "이 글을 피드에서 삭제할까요?\n구독 채널에서 다시 담을 수 있습니다.",
) {
    var confirmDelete by remember { mutableStateOf(false) }
    var confirmCollect by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val openSource = {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(item.source_url)))
    }
    BackHandler(onBack = onBack)
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        item.title,
                        style = MaterialTheme.typography.titleSmall,
                        lineHeight = 18.sp,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "뒤로")
                    }
                },
                actions = {
                    // 원문 링크는 본문 하단에 그대로 있다 — 여기 자리는 컬렉션에 넘겼다
                    if (onCollect != null) {
                        IconButton(onClick = { confirmCollect = true }) {
                            Icon(Icons.Default.BookmarkAdd, contentDescription = "컬렉션에 담기")
                        }
                    }
                    IconButton(onClick = { confirmDelete = true }) {
                        Icon(Icons.Default.Delete, contentDescription = deleteTitle)
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .fillMaxWidth()
        ) {
            Text(item.title, fontWeight = FontWeight.Bold, fontSize = 20.sp)
            Spacer(Modifier.height(4.dp))
            Text("${item.author} · ${item.date}", fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
            Spacer(Modifier.height(12.dp))
            MarkdownText(
                markdown = item.body,
                style = MaterialTheme.typography.bodyLarge.copy(
                    color = MaterialTheme.colorScheme.onBackground,
                    fontSize = 15.sp,
                    lineHeight = 22.sp,
                ),
            )
            // 본문 끝의 원문 링크 — 저장 시점에 본문에 넣지 않고 여기서 붙여 기존 글에도 나온다
            if (item.source_url.startsWith("http")) {
                Spacer(Modifier.height(24.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f))
                TextButton(onClick = openSource, modifier = Modifier.padding(top = 4.dp)) {
                    Icon(Icons.Default.OpenInNew, contentDescription = null,
                        modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("원문 보기")
                }
                Text(
                    text = item.source_url,
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(32.dp))
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text(deleteTitle) },
            text = { Text(deleteMessage) },
            confirmButton = {
                TextButton(onClick = { confirmDelete = false; onDelete() }) { Text("삭제") }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("취소") } }
        )
    }

    if (confirmCollect && onCollect != null) {
        AlertDialog(
            onDismissRequest = { confirmCollect = false },
            title = { Text("컬렉션에 담기") },
            text = { Text("이 글을 컬렉션으로 옮길까요?\n피드에서는 사라지고 만료로 삭제되지 않습니다. 되돌릴 수 없습니다.") },
            confirmButton = {
                TextButton(onClick = { confirmCollect = false; onCollect() }) { Text("담기") }
            },
            dismissButton = { TextButton(onClick = { confirmCollect = false }) { Text("취소") } }
        )
    }
}
