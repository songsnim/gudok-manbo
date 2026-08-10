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
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
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
        )
        return
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("컨텐츠 피드") },
                actions = {
                    IconButton(onClick = { vm.load() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "새로고침")
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
                    if (s.items.isEmpty()) {
                        Text("수집된 아이템이 없습니다.", Modifier.align(Alignment.Center))
                    } else {
                        LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
                            items(s.items, key = { it.slug }) { item ->
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

@Composable
private fun FeedItemRow(item: FeedItem, isRead: Boolean, avatarUrl: String?, onClick: () -> Unit) {
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ItemDetailScreen(item: FeedItem, onBack: () -> Unit, onDelete: () -> Unit) {
    var confirmDelete by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val openSource = {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(item.source_url)))
    }
    BackHandler(onBack = onBack)
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(item.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "뒤로")
                    }
                },
                actions = {
                    if (item.source_url.startsWith("http")) {
                        IconButton(onClick = openSource) {
                            Icon(Icons.Default.OpenInNew, contentDescription = "원문 보기")
                        }
                    }
                    IconButton(onClick = { confirmDelete = true }) {
                        Icon(Icons.Default.Delete, contentDescription = "피드에서 삭제")
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
            title = { Text("피드에서 삭제") },
            text = { Text("이 글을 피드에서 삭제할까요?\n구독 채널에서 다시 담을 수 있습니다.") },
            confirmButton = {
                TextButton(onClick = { confirmDelete = false; onDelete() }) { Text("삭제") }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("취소") } }
        )
    }
}
