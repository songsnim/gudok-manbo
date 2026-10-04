package com.contentscurator.ui.agent

import android.app.Application
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.os.Build
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.contentscurator.data.api.AppSettings
import com.contentscurator.data.api.CollectRun
import com.contentscurator.data.api.DiscoverResult
import com.contentscurator.data.api.Stats
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

    // ── 설정 · 통계 ──────────────────────────────────────────────
    private val _settings = MutableStateFlow<AppSettings?>(null)
    val settings: StateFlow<AppSettings?> = _settings

    private val _stats = MutableStateFlow<Stats?>(null)
    val stats: StateFlow<Stats?> = _stats

    init { refreshSettingsAndStats() }

    fun refreshSettingsAndStats() = viewModelScope.launch {
        runCatching { _settings.value = repo.getSettings() }
        runCatching { _stats.value = repo.getStats() }
    }

    /** 넘긴 값만 저장한다 — 나머지는 백엔드에 그대로 남는다. */
    fun saveSettings(
        autoCollect: Boolean? = null,
        schedule: Map<String, Int>? = null,
        expireDays: Int? = null,
    ) = viewModelScope.launch {
        runCatching { repo.updateSettings(autoCollect = autoCollect, schedule = schedule, expireDays = expireDays) }
            .onSuccess { _settings.value = it; _status.value = "설정 저장됨" }
            .onFailure { _status.value = "설정 저장 실패: ${it.message}" }
    }

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
        refreshSettingsAndStats()  // 방금 실행이 최근 실행 목록에 나와야 한다
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
    val settings by vm.settings.collectAsStateWithLifecycle()
    val stats by vm.stats.collectAsStateWithLifecycle()

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

            // ── 수집 설정 ─────────────────────────────────────────
            Spacer(Modifier.height(32.dp))
            HorizontalDivider()
            Spacer(Modifier.height(24.dp))
            ScheduleSettingsSection(settings = settings, onSave = vm::saveSettings)

            // ── 최근 실행 ─────────────────────────────────────────
            Spacer(Modifier.height(32.dp))
            HorizontalDivider()
            Spacer(Modifier.height(24.dp))
            RecentRunsSection(runs = stats?.recent_runs ?: emptyList())

            // ── 통계 ─────────────────────────────────────────────
            Spacer(Modifier.height(32.dp))
            HorizontalDivider()
            Spacer(Modifier.height(24.dp))
            StatsSection(stats = stats, onRefresh = { vm.refreshSettingsAndStats() })
            Spacer(Modifier.height(32.dp))
        }
    }
}

// ── 수집 설정 ────────────────────────────────────────────────────────────────

@Composable
private fun ScheduleSettingsSection(settings: AppSettings?, onSave: (Boolean?, Map<String, Int>?, Int?) -> Unit) {
    SectionTitle("수집 설정")
    if (settings == null) {
        Text("불러오는 중…", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline, modifier = Modifier.fillMaxWidth())
        return
    }

    val autoCollect = settings.auto_collect ?: true
    // 시각(트리거)은 register_tasks.ps1이 정한다 — 여기서는 개수만 편집한다
    val hours = remember(settings.schedule) { (settings.schedule ?: emptyMap()).keys.sortedBy { it.toIntOrNull() ?: 0 } }
    val counts = remember(settings.schedule) {
        mutableStateMapOf<String, String>().apply {
            (settings.schedule ?: emptyMap()).forEach { (h, c) -> put(h, c.toString()) }
        }
    }
    var expireDays by remember(settings.expire_days) { mutableStateOf((settings.expire_days ?: 0).toString()) }

    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("자동 수집", style = MaterialTheme.typography.bodyMedium)
            Text(
                if (autoCollect) "정해진 시각에 수집한다"
                else "꺼짐 — 수집하지 않는다 (만료는 아래 설정대로 진행)",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline,
            )
        }
        Switch(checked = autoCollect, onCheckedChange = { onSave(it, null, null) })
    }

    Spacer(Modifier.height(16.dp))
    Text("시각별 수집 개수", style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.fillMaxWidth())
    Spacer(Modifier.height(4.dp))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        hours.forEach { hour ->
            OutlinedTextField(
                value = counts[hour] ?: "",
                onValueChange = { counts[hour] = it.filter(Char::isDigit) },
                label = { Text("${hour}시") },
                modifier = Modifier.weight(1f),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            )
        }
    }
    Text("시각 자체를 바꾸려면 backend/register_tasks.ps1 을 다시 실행한다.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.outline, modifier = Modifier.fillMaxWidth())

    Spacer(Modifier.height(16.dp))
    OutlinedTextField(
        value = expireDays,
        onValueChange = { expireDays = it.filter(Char::isDigit) },
        label = { Text("피드 만료 일수") },
        supportingText = {
            Text(
                if ((expireDays.toIntOrNull() ?: 0) <= 0)
                    "0 = 만료 없음. 피드가 계속 쌓인다."
                else "수집일로부터 ${expireDays}일 지나고 컬렉션에 담지 않은 글은 삭제된다. 되돌릴 수 없다."
            )
        },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
    )

    Spacer(Modifier.height(8.dp))
    Button(
        onClick = {
            val schedule = hours.mapNotNull { h -> counts[h]?.toIntOrNull()?.let { h to it } }.toMap()
            onSave(null, schedule.ifEmpty { null }, expireDays.toIntOrNull() ?: 0)
        },
        modifier = Modifier.fillMaxWidth(),
    ) { Text("설정 저장") }
}

// ── 최근 실행 ────────────────────────────────────────────────────────────────

@Composable
private fun RecentRunsSection(runs: List<CollectRun>) {
    SectionTitle("최근 실행")
    if (runs.isEmpty()) {
        Text("기록 없음", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline, modifier = Modifier.fillMaxWidth())
        return
    }
    runs.forEach { run -> RunRow(run) }
}

@Composable
private fun RunRow(run: CollectRun) {
    var expanded by remember { mutableStateOf(false) }
    // "2026-08-22T06:00:03" → "08-22 06:00"
    val at = run.at.replace("T", " ").let { if (it.length >= 16) it.substring(5, 16) else it }
    val label = when (run.trigger) {
        "skipped" -> "$at · 자동 수집 꺼짐 — 건너뜀"
        else -> buildString {
            append(at)
            append(if (run.trigger == "manual") " · 수동" else " · ${run.target ?: "할당량"}개 목표")
            append(" → ${run.collected}개 저장")
            if (run.failures.isNotEmpty()) append(" · 실패 ${run.failures.size}")
            if (run.expired.isNotEmpty()) append(" · 만료 삭제 ${run.expired.size}")
        }
    }
    Column(
        Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded }
            .padding(vertical = 6.dp)
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall)
        if (run.error.isNotBlank()) {
            Text(run.error, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error)
        }
        if (expanded) {
            run.failures.forEach {
                Text("  실패 ${it.author}: ${it.reason}", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error)
            }
            run.expired.forEach {
                Text("  만료 삭제 $it", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline)
            }
            run.slugs.forEach {
                Text("  + $it", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline)
            }
        }
    }
    HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f))
}

// ── 통계 ─────────────────────────────────────────────────────────────────────

@Composable
private fun StatsSection(stats: Stats?, onRefresh: () -> Unit) {
    SectionTitle("통계")
    if (stats == null) {
        OutlinedButton(onClick = onRefresh) { Text("통계 불러오기") }
        return
    }
    Text("피드 ${stats.total_feed}개 · 컬렉션 ${stats.total_collection}개",
        style = MaterialTheme.typography.bodyMedium, modifier = Modifier.fillMaxWidth())

    if (stats.by_platform.isNotEmpty()) {
        Spacer(Modifier.height(8.dp))
        Text(stats.by_platform.joinToString("  ") { "${it.platform} ${it.count}" },
            style = MaterialTheme.typography.bodySmall, modifier = Modifier.fillMaxWidth())
    }

    if (stats.by_date.isNotEmpty()) {
        Spacer(Modifier.height(12.dp))
        Text("최근 30일 일별", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.fillMaxWidth())
        stats.by_date.forEach {
            Text("${it.date}   ${it.count}개", style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.fillMaxWidth())
        }
    }

    if (stats.by_author.isNotEmpty()) {
        Spacer(Modifier.height(12.dp))
        Text("채널별 상위", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.fillMaxWidth())
        stats.by_author.forEach {
            Text("${it.author}   ${it.count}개", style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.fillMaxWidth())
        }
    }

    Spacer(Modifier.height(8.dp))
    OutlinedButton(onClick = onRefresh) { Text("통계 새로고침") }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleSmall, modifier = Modifier.fillMaxWidth())
    Spacer(Modifier.height(8.dp))
}
