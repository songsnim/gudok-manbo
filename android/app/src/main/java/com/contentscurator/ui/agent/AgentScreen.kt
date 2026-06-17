package com.contentscurator.ui.agent

import android.app.Application
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.os.Build
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.contentscurator.data.api.DiscoverResult
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.data.repository.FeedRepository
import com.contentscurator.widget.FeedWidgetReceiver
import com.contentscurator.widget.WidgetItem
import com.contentscurator.widget.updateWidgetData
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class AgentViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = FeedRepository(AppDatabase.getInstance(app))

    private val _status = MutableStateFlow<String?>(null)
    val status: StateFlow<String?> = _status

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading

    private val _widgetLoading = MutableStateFlow(false)
    val widgetLoading: StateFlow<Boolean> = _widgetLoading

    private val _discoverLoading = MutableStateFlow(false)
    val discoverLoading: StateFlow<Boolean> = _discoverLoading

    private val _discoverResult = MutableStateFlow<DiscoverResult?>(null)
    val discoverResult: StateFlow<DiscoverResult?> = _discoverResult

    fun collect() = viewModelScope.launch {
        _loading.value = true
        _status.value = null
        runCatching {
            val result = repo.triggerCollect()
            val collected = (result["collected"] as? Number)?.toInt() ?: 0
            _status.value = "수집 완료: ${collected}개 저장됨"
            // 수집 후 위젯 자동 갱신
            val items = repo.getTodayFeed()
            val readSlugs = repo.getAllReadSlugs()
            val widgetItems = items.map { WidgetItem(it.slug, it.title, it.platform, it.slug in readSlugs) }
            updateWidgetData(getApplication(), widgetItems)
        }.onFailure {
            _status.value = "오류: ${it.message}"
        }
        _loading.value = false
    }

    fun pinWidget(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false
        val mgr = AppWidgetManager.getInstance(getApplication())
        if (!mgr.isRequestPinAppWidgetSupported) return false
        val provider = ComponentName(getApplication<Application>(), FeedWidgetReceiver::class.java)
        mgr.requestPinAppWidget(provider, null, null)
        return true
    }

    fun discover(query: String) = viewModelScope.launch {
        if (query.isBlank()) return@launch
        _discoverLoading.value = true
        _discoverResult.value = null
        _status.value = null
        runCatching {
            val result = repo.discover(query)
            _discoverResult.value = result
            _status.value = "탐색 완료: ${result.added}개 구독 추가됨"
        }.onFailure { _status.value = "탐색 오류: ${it.message}" }
        _discoverLoading.value = false
    }

    fun syncWidget() = viewModelScope.launch {
        _widgetLoading.value = true
        _status.value = null
        runCatching {
            val items = repo.getTodayFeed()
            val readSlugs = repo.getAllReadSlugs()
            val widgetItems = items.map { WidgetItem(it.slug, it.title, it.platform, it.slug in readSlugs) }
            updateWidgetData(getApplication(), widgetItems)
            _status.value = "위젯 업데이트 완료: ${widgetItems.size}개 중 ${widgetItems.count { !it.read }}개 미읽음"
        }.onFailure {
            _status.value = "위젯 오류: ${it.message}"
        }
        _widgetLoading.value = false
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentScreen(vm: AgentViewModel = viewModel()) {
    val loading by vm.loading.collectAsStateWithLifecycle()
    val widgetLoading by vm.widgetLoading.collectAsStateWithLifecycle()
    val discoverLoading by vm.discoverLoading.collectAsStateWithLifecycle()
    val discoverResult by vm.discoverResult.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()

    val anyLoading = loading || widgetLoading || discoverLoading
    var query by remember { mutableStateOf("") }

    Scaffold(topBar = { TopAppBar(title = { Text("에이전트") }) }) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // ── 수집 ──────────────────────────────────────────────
            Text("수동으로 콘텐츠를 수집합니다.", style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(16.dp))
            Button(onClick = { vm.collect() }, enabled = !anyLoading) {
                if (loading) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text("지금 수집 실행")
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { vm.pinWidget() }, enabled = !anyLoading) {
                Text("홈 화면에 위젯 추가")
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { vm.syncWidget() }, enabled = !anyLoading) {
                if (widgetLoading) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text("위젯 강제 업데이트")
            }

            // ── AI 소스 탐색 ──────────────────────────────────────
            Spacer(Modifier.height(32.dp))
            HorizontalDivider()
            Spacer(Modifier.height(24.dp))
            Text("AI 소스 탐색", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("예: 파이썬 머신러닝 유튜버 찾아줘") },
                modifier = Modifier.fillMaxWidth(),
                enabled = !anyLoading,
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { vm.discover(query) }),
            )
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = { vm.discover(query) },
                enabled = !anyLoading && query.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (discoverLoading) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text("AI로 소스 탐색")
            }

            discoverResult?.let { result ->
                Spacer(Modifier.height(12.dp))
                result.sources.forEach { src ->
                    Text(
                        "+ ${src.author} (${src.platform}) — ${src.reason}",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(4.dp))
                }
                if (result.skipped.isNotEmpty()) {
                    Text(
                        "건너뜀 ${result.skipped.size}개",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            status?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
