package com.contentscurator.ui.feed

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.contentscurator.data.api.FeedItem
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
                title = { Text("오늘의 피드") },
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
                        Text("오늘 수집된 아이템이 없습니다.", Modifier.align(Alignment.Center))
                    } else {
                        LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
                            items(s.items, key = { it.slug }) { item ->
                                FeedItemRow(
                                    item = item,
                                    isRead = item.slug in s.readSlugs,
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

@Composable
private fun FeedItemRow(item: FeedItem, isRead: Boolean, onClick: () -> Unit) {
    val alpha = if (isRead) 0.45f else 1f
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        PlatformIcon(platform = item.platform, modifier = Modifier.size(32.dp))
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            if (item.subscription) {
                Text(
                    text = item.author,
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.primary.copy(alpha = alpha),
                )
            }
            Text(
                text = item.title,
                fontWeight = if (isRead) FontWeight.Normal else FontWeight.SemiBold,
                fontSize = 15.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = alpha),
            )
        }
        if (!isRead) {
            Spacer(Modifier.width(8.dp))
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(MaterialTheme.colorScheme.primary, shape = androidx.compose.foundation.shape.CircleShape)
            )
        }
    }
    HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f))
}

@Composable
private fun PlatformIcon(platform: String, modifier: Modifier = Modifier) {
    val emoji = when (platform.lowercase()) {
        "youtube" -> "▶"
        "medium" -> "M"
        "linkedin" -> "in"
        "x", "twitter" -> "X"
        "threads" -> "@"
        "rss", "news" -> "📰"
        else -> "·"
    }
    Box(
        modifier = modifier
            .background(
                color = platformColor(platform),
                shape = androidx.compose.foundation.shape.RoundedCornerShape(6.dp)
            ),
        contentAlignment = Alignment.Center
    ) {
        Text(emoji, fontSize = 13.sp, color = androidx.compose.ui.graphics.Color.White)
    }
}

@Composable
private fun platformColor(platform: String): androidx.compose.ui.graphics.Color {
    return when (platform.lowercase()) {
        "youtube" -> androidx.compose.ui.graphics.Color(0xFFFF0000)
        "medium" -> androidx.compose.ui.graphics.Color(0xFF000000)
        "linkedin" -> androidx.compose.ui.graphics.Color(0xFF0A66C2)
        "x", "twitter" -> androidx.compose.ui.graphics.Color(0xFF000000)
        "threads" -> androidx.compose.ui.graphics.Color(0xFF000000)
        else -> androidx.compose.ui.graphics.Color(0xFF888888)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ItemDetailScreen(item: FeedItem, onBack: () -> Unit, onDelete: () -> Unit) {
    var confirmDelete by remember { mutableStateOf(false) }
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
