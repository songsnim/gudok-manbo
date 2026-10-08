package com.contentscurator.widget

import android.appwidget.AppWidgetManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.glance.appwidget.state.updateAppWidgetState
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.*
import androidx.glance.action.ActionParameters
import androidx.glance.action.actionParametersOf
import androidx.glance.action.actionStartActivity
import androidx.glance.action.clickable
import androidx.glance.appwidget.*
import androidx.glance.appwidget.lazy.LazyColumn
import androidx.glance.appwidget.lazy.itemsIndexed
import androidx.glance.layout.*
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import com.contentscurator.MainActivity
import com.contentscurator.data.ServerResolver
import com.contentscurator.data.api.RetrofitClient
import com.contentscurator.data.db.AppDatabase
import com.contentscurator.ui.feed.thumbnailUrl
import com.contentscurator.ui.subscriptions.platformColor
import com.contentscurator.ui.subscriptions.platformLetter
import com.contentscurator.ui.theme.Background
import com.contentscurator.ui.theme.OnBackground
import com.contentscurator.ui.theme.Outline
import com.contentscurator.ui.theme.Primary
import com.contentscurator.ui.theme.Surface
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.net.URL
import java.time.LocalDate
import java.time.LocalTime

// 인앱 FeedItemRow와 같은 값. 앱이 다크 고정이라 위젯도 day/night 분기 없음.
private val DATE = Color(0xFFCAC4D0)      // M3 다크 onSurfaceVariant (인앱 날짜 줄)
private val DIVIDER = Color(0xFF36383B)   // outline 30% over background (인앱 디바이더)

private const val MAX_ROWS = 5
// 하루치만 보여주므로 누적되지 않는다 — 넉넉한 안전 상한. 이미지는 URI로 넘겨 RemoteViews 크기와 무관.
private const val MAX_ITEMS = 50
private const val READ_ALPHA = 0.45f   // 인앱 FeedItemRow 읽음 alpha

/** 위젯 행 탭 → MainActivity가 이 extra로 본문을 연다. */
val SlugParam = ActionParameters.Key<String>(MainActivity.EXTRA_SLUG)

class FeedWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget = FeedWidget()
}

/**
 * 실제 화면 dp → 위젯 dp. One UI는 큰 위젯을 보고된 크기로 그린 뒤 hsResizeRatio(5×6에서 ≈0.71)로
 * 축소해 보여준다. 그대로 두면 인앱보다 30% 작게 보이므로 모든 치수를 1/ratio 배 한다.
 */
private class Scale(val ratio: Float) {
    fun d(v: Float): Dp = (v / ratio).dp
    fun t(v: Float): TextUnit = (v / ratio).sp
}

class FeedWidget : GlanceAppWidget() {
    override val sizeMode = SizeMode.Exact

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        // ponytail: 비율은 세션 시작 때 한 번 읽는다. 런처 그리드를 바꾸면 다음 세션부터 반영.
        val options = AppWidgetManager.getInstance(context)
            .getAppWidgetOptions(GlanceAppWidgetManager(context).getAppWidgetId(id))
        val ratio = (options.get("hsResizeRatio") as? Number)?.toFloat()?.takeIf { it in 0.3f..1f } ?: 1f
        provideContent {
            // 세션이 살아 있는 동안 update()는 provideGlance를 다시 부르지 않고 재구성만 한다.
            // 그래서 데이터는 재구성 안에서, notifyWidget이 올리는 버전이 바뀔 때마다 다시 읽는다.
            val version = currentState(KEY_VERSION) ?: 0L
            val data by produceState<WidgetData?>(null, version) { value = loadWidgetData(context) }
            data?.let { WidgetContent(it.items, it.read, it.bgAlpha, it.images, it.emptyText, Scale(ratio)) }
        }
    }
}

private class WidgetData(
    val items: List<WidgetItem>, val read: Set<String>, val bgAlpha: Float, val images: Map<String, Uri?>, val emptyText: String,
)

private val KEY_VERSION = longPreferencesKey("version")

private suspend fun loadWidgetData(context: Context): WidgetData = withContext(Dispatchers.IO) {
    val snap = loadSnapshot(context)
    val read = AppDatabase.getInstance(context).readStatusDao().getAllReadSlugs().toSet()
    val shown = pickToday(snap?.items.orEmpty(), LocalDate.now().toString()).take(MAX_ITEMS)
    val images = shown.flatMap { listOf(thumbFile(context, it.slug), avatarFile(context, it.author)) }
        .associate { it.name to imageUri(context, it) }
    val emptyText = if (snap == null) "앱을 한 번 열어 주세요"
                    else nextCollectLabel(snap.hours, LocalTime.now().hour)
    WidgetData(shown, read, 1f - widgetTransparency(context) / 100f, images, emptyText)
}

private fun widgetPrefs(context: Context) = context.getSharedPreferences("widget", Context.MODE_PRIVATE)

/** 배경 투명도 0–100. 100이면 배경 없이 글이 배경화면 위에 뜬다. */
fun widgetTransparency(context: Context): Int = widgetPrefs(context).getInt("transparency", 0)

suspend fun setWidgetTransparency(context: Context, value: Int) {
    widgetPrefs(context).edit().putInt("transparency", value.coerceIn(0, 100)).apply()
    notifyWidget(context)
}

/** 스냅샷이나 읽음 상태가 바뀌었을 때 — 위젯마다 버전을 올려 재구성 안에서 데이터를 다시 읽게 한다. */
suspend fun notifyWidget(context: Context) {
    GlanceAppWidgetManager(context).getGlanceIds(FeedWidget::class.java).forEach { id ->
        updateAppWidgetState(context, id) { it[KEY_VERSION] = System.currentTimeMillis() }
        FeedWidget().update(context, id)
    }
}

@Composable
private fun WidgetContent(
    items: List<WidgetItem>, read: Set<String>, bgAlpha: Float, images: Map<String, Uri?>, emptyText: String, s: Scale,
) {
    // 실제 화면 기준 크기로 계산한 뒤 s로 위젯 단위로 바꾼다
    val size = LocalSize.current
    val realW = size.width.value * s.ratio
    // 헤더 없음 — 위아래 패딩 4씩 빼고 전부 행에 쓴다. 5×3(≈280dp)에서 3행이 들어가는 높이.
    // 행 높이를 보이는 칸에 딱 맞춰 두고 나머지는 스크롤로 내린다.
    val avail = size.height.value * s.ratio - 8f
    val rows = (avail / 80f).toInt().coerceIn(1, MAX_ROWS)
    val rowH = avail / rows
    // 메타 20 + 2 + 13sp 3줄(≈52) ≈ 74 — 5×3의 행(≈88)에 3줄이 들어간다
    val titleLines = if (rowH >= 78f) 3 else 2
    val thumbH = minOf(77f, rowH - 16f)   // 인앱 86dp보다 10% 작게 — 제목 열에 폭을 준다
    val showThumb = realW >= 300f

    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            // One UI는 이 표시가 없으면 위젯을 못 그린다("위젯을 추가할 수 없습니다") — 완전 투명이어도 유지
            .appWidgetBackground()
            .background(Background.copy(alpha = bgAlpha))
            .cornerRadius(android.R.dimen.system_app_widget_background_radius)
            .padding(vertical = s.d(4f))
    ) {
        if (items.isEmpty()) {
            Column(
                modifier = GlanceModifier.fillMaxSize().clickable(actionStartActivity<MainActivity>()),
                verticalAlignment = Alignment.CenterVertically,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("오늘 글이 아직 없어요", style = TextStyle(color = ColorProvider(OnBackground), fontSize = s.t(18f), fontWeight = FontWeight.Bold))
                Spacer(GlanceModifier.height(s.d(4f)))
                Text(emptyText, style = TextStyle(color = ColorProvider(Outline), fontSize = s.t(13f)))
            }
        } else {
            LazyColumn(GlanceModifier.fillMaxSize()) {
                itemsIndexed(items, itemId = { _, it -> it.slug.hashCode().toLong() }) { i, item ->
                    Column {
                        if (i > 0) Box(GlanceModifier.fillMaxWidth().height(s.d(0.5f)).background(DIVIDER.copy(alpha = bgAlpha))) {}
                        ItemRow(
                            item, item.slug in read, s, rowH, titleLines, if (showThumb) thumbH else 0f,
                            images[thumbFileName(item.slug)], images[avatarFileName(item.author)],
                        )
                    }
                }
            }
        }
    }
}

/** 인앱 FeedItemRow 그대로: 배지 · 아바타 · 채널명 / 제목 / 날짜 + 오른쪽 16:9 썸네일. */
@Composable
private fun ItemRow(
    item: WidgetItem, isRead: Boolean, s: Scale, rowH: Float, titleLines: Int, thumbH: Float, thumb: Uri?, avatar: Uri?,
) {
    // 읽은 글은 인앱처럼 흐리게. Glance Image엔 alpha가 없어 이미지는 배경색 막을 덮는다.
    val a = if (isRead) READ_ALPHA else 1f
    val veil = Background.copy(alpha = 1f - READ_ALPHA)
    Row(
        modifier = GlanceModifier
            .fillMaxWidth()
            .height(s.d(rowH))
            .padding(horizontal = s.d(16f))
            .clickable(actionStartActivity<MainActivity>(actionParametersOf(SlugParam to item.slug))),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(GlanceModifier.defaultWeight()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = GlanceModifier.size(s.d(20f)).background(platformColor(item.platform).copy(alpha = a)).cornerRadius(s.d(8f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        platformLetter(item.platform),
                        style = TextStyle(color = ColorProvider(Color.White.copy(alpha = a)), fontSize = s.t(7.2f), fontWeight = FontWeight.Bold),
                    )
                }
                Spacer(GlanceModifier.width(s.d(6f)))
                if (avatar != null) {
                    Box(GlanceModifier.size(s.d(18f)).cornerRadius(s.d(9f))) {
                        Image(
                            ImageProvider(avatar), contentDescription = null, contentScale = ContentScale.Crop,
                            modifier = GlanceModifier.fillMaxSize(),
                        )
                        if (isRead) Box(GlanceModifier.fillMaxSize().background(veil)) {}
                    }
                    Spacer(GlanceModifier.width(s.d(6f)))
                }
                Text(item.author, maxLines = 1, style = TextStyle(color = ColorProvider(Primary.copy(alpha = a)), fontSize = s.t(11f)))
                if (item.date.isNotBlank()) {
                    Spacer(GlanceModifier.width(s.d(6f)))
                    // 날짜는 채널명 옆 한 줄로 — 아래 줄을 제목에 준다
                    Text(shortDate(item.date), maxLines = 1, style = TextStyle(color = ColorProvider(DATE.copy(alpha = a)), fontSize = s.t(10f)))
                }
            }
            Spacer(GlanceModifier.height(s.d(2f)))
            // Glance엔 SemiBold가 없다 — 인앱 미읽음 SemiBold에 가장 가까운 Bold, 읽으면 Normal
            Text(
                item.title,
                maxLines = titleLines,
                style = TextStyle(
                    color = ColorProvider(OnBackground.copy(alpha = a)), fontSize = s.t(13f),
                    fontWeight = if (isRead) FontWeight.Normal else FontWeight.Bold,
                ),
            )
        }
        if (thumbH > 0f) {
            Spacer(GlanceModifier.width(s.d(12f)))
            val thumbMod = GlanceModifier.size(width = s.d(thumbH * 16f / 9f), height = s.d(thumbH)).cornerRadius(s.d(8f))
            if (thumb != null) {
                Box(thumbMod) {
                    Image(ImageProvider(thumb), contentDescription = null, contentScale = ContentScale.Crop, modifier = GlanceModifier.fillMaxSize())
                    if (isRead) Box(GlanceModifier.fillMaxSize().background(veil)) {}
                }
            } else {
                // 영상이 아닌 글 — 플랫폼은 배지가 말하므로 블록은 '누가 썼는지'만
                Box(thumbMod.background(Surface.copy(alpha = a)), contentAlignment = Alignment.Center) {
                    Text(
                        item.author.take(1),
                        style = TextStyle(color = ColorProvider(Outline.copy(alpha = a)), fontSize = s.t(24f), fontWeight = FontWeight.Bold),
                    )
                }
            }
        }
    }
}

// ── 데이터 ──────────────────────────────────────────────────────────────────

private val snapshotAdapter = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    .adapter(WidgetSnapshot::class.java)

private fun snapshotFile(context: Context) = File(context.filesDir, "widget_snapshot.json")
private fun imageDir(context: Context) = File(context.cacheDir, "widget_thumbs").apply { mkdirs() }
private fun thumbFileName(slug: String) = "t-$slug.jpg"
private fun avatarFileName(author: String) = "a-${author.hashCode()}.jpg"
private fun thumbFile(context: Context, slug: String) = File(imageDir(context), thumbFileName(slug))
private fun avatarFile(context: Context, author: String) = File(imageDir(context), avatarFileName(author))

private fun loadSnapshot(context: Context): WidgetSnapshot? =
    runCatching { snapshotAdapter.fromJson(snapshotFile(context).readText()) }.getOrNull()

/** 마지막 동기화에서 받은 수집 시각(개수 > 0인 시각만). 워커가 다음 갱신 시점을 잡을 때 쓴다. */
fun cachedCollectHours(context: Context): List<Int> = loadSnapshot(context)?.hours.orEmpty()

/** 런처가 WidgetImageProvider로 직접 읽어 가는 주소. 파일이 없으면 null — 대체 블록. */
private fun imageUri(context: Context, f: File): Uri? =
    if (!f.exists()) null else Uri.parse("content://${context.packageName}.widgetimages/${f.name}")

/**
 * 위젯 이미지를 런처 프로세스에 건넨다. 비트맵을 RemoteViews에 실으면 행 수 × 이미지 크기가
 * 1MB 한도에 걸린다. 공개 썸네일·아바타뿐이라 권한 없이 내보내되 widget_thumbs 밖은 막는다.
 */
class WidgetImageProvider : android.content.ContentProvider() {
    override fun openFile(uri: Uri, mode: String): android.os.ParcelFileDescriptor {
        val dir = imageDir(context!!).canonicalFile
        val f = File(dir, uri.lastPathSegment ?: "").canonicalFile
        if (f.parentFile != dir || !f.isFile) throw java.io.FileNotFoundException(uri.toString())
        return android.os.ParcelFileDescriptor.open(f, android.os.ParcelFileDescriptor.MODE_READ_ONLY)
    }
    override fun getType(uri: Uri) = "image/jpeg"
    override fun onCreate() = true
    override fun query(u: Uri, p: Array<String>?, s: String?, a: Array<String>?, o: String?) = null
    override fun insert(u: Uri, v: android.content.ContentValues?) = null
    override fun update(u: Uri, v: android.content.ContentValues?, s: String?, a: Array<String>?) = 0
    override fun delete(u: Uri, s: String?, a: Array<String>?) = 0
}

/**
 * 받아서 w×h로 잘라 저장. 썸네일은 hqdefault(4:3 레터박스)의 가운데 16:9.
 */
private fun saveImage(url: String, file: File, w: Int, h: Int) {
    val src = URL(url).openStream().use { BitmapFactory.decodeStream(it) } ?: return
    val ch = minOf(src.height, src.width * h / w)
    val cw = ch * w / h
    val crop = Bitmap.createBitmap(src, (src.width - cw) / 2, (src.height - ch) / 2, cw, ch)
    val out = Bitmap.createScaledBitmap(crop, w, h, true)
    file.outputStream().use { out.compress(Bitmap.CompressFormat.JPEG, 88, it) }
}

/** 서버에서 목록·수집 시각·아바타를 받아 스냅샷과 이미지를 갱신하고 위젯을 다시 그린다. */
suspend fun refreshWidget(context: Context) = withContext(Dispatchers.IO) {
    ServerResolver.ensure(context)
    val avatars = runCatching {
        RetrofitClient.api.getSubscriptions()
            .mapNotNull { s -> s.avatar_url?.takeIf { it.isNotBlank() }?.let { s.author to it } }.toMap()
    }.getOrDefault(emptyMap())
    val items = RetrofitClient.api.getAllItems(lite = true).map {
        WidgetItem(
            it.slug, it.title, it.platform, it.author,
            thumbnailUrl(it.platform, it.source_url, it.slug),
            avatars[it.author],
            it.published.ifBlank { it.date },
            it.date,
        )
    }
    val hours = runCatching {
        RetrofitClient.api.getSettings().schedule.orEmpty()
            .filterValues { it > 0 }.keys.mapNotNull { it.toIntOrNull() }.sorted()
    }.getOrElse { cachedCollectHours(context) }
    snapshotFile(context).writeText(snapshotAdapter.toJson(WidgetSnapshot(items, hours)))

    val wanted = pickToday(items, LocalDate.now().toString()).take(MAX_ITEMS)
    val keep = wanted.flatMap { listOf(thumbFileName(it.slug), avatarFileName(it.author)) }.toSet()
    imageDir(context).listFiles()?.filter { it.name !in keep }?.forEach { it.delete() }
    wanted.forEach { item ->
        val t = thumbFile(context, item.slug)
        if (item.thumbnailUrl != null && !t.exists()) runCatching { saveImage(item.thumbnailUrl, t, 320, 180) }
        val a = avatarFile(context, item.author)
        if (item.avatarUrl != null && !a.exists()) runCatching { saveImage(item.avatarUrl, a, 64, 64) }
    }
    notifyWidget(context)
}
