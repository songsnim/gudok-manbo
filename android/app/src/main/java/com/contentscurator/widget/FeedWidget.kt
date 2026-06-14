package com.contentscurator.widget

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.glance.*
import androidx.glance.action.actionStartActivity
import androidx.glance.action.clickable
import androidx.glance.appwidget.*
import androidx.glance.appwidget.lazy.LazyColumn
import androidx.glance.appwidget.lazy.items
import androidx.glance.appwidget.state.updateAppWidgetState
import androidx.glance.layout.*
import androidx.glance.state.PreferencesGlanceStateDefinition
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import com.contentscurator.MainActivity
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

private val KEY_ITEMS = stringPreferencesKey("widget_items")

class FeedWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget = FeedWidget()
}

class FeedWidget : GlanceAppWidget() {
    override suspend fun provideGlance(context: Context, id: GlanceId) {
        provideContent { WidgetContent() }
    }
}

@Composable
private fun WidgetContent() {
    val prefs = currentState<Preferences>()
    val json = prefs[KEY_ITEMS] ?: "[]"
    val items = parseItems(json).take(6)
    val unreadCount = items.count { !it.read }

    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ColorProvider(Color.White))
    ) {
        Row(
            modifier = GlanceModifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "Contents Curator",
                style = TextStyle(fontWeight = FontWeight.Bold),
                modifier = GlanceModifier.defaultWeight(),
            )
            if (unreadCount > 0) {
                Text(
                    "$unreadCount 미읽음",
                    style = TextStyle(color = ColorProvider(Color(0xFF1976D2))),
                )
            }
        }
        if (items.isEmpty()) {
            Text(
                "콘텐츠가 없습니다. 앱에서 수집을 실행하세요.",
                style = TextStyle(color = ColorProvider(Color.Gray)),
                modifier = GlanceModifier.padding(horizontal = 12.dp, vertical = 8.dp),
            )
        } else {
            LazyColumn {
                items(items) { item ->
                    Row(
                        modifier = GlanceModifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 4.dp)
                            .clickable(actionStartActivity<MainActivity>()),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(
                            modifier = GlanceModifier
                                .size(24.dp)
                                .background(ColorProvider(platformColor(item.platform)))
                                .cornerRadius(4.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                platformEmoji(item.platform),
                                style = TextStyle(color = ColorProvider(Color.White)),
                            )
                        }
                        Spacer(GlanceModifier.width(8.dp))
                        Text(
                            item.title,
                            style = TextStyle(
                                color = ColorProvider(
                                    if (item.read) Color.Gray else Color.Black
                                )
                            ),
                            modifier = GlanceModifier.defaultWeight(),
                        )
                    }
                }
            }
        }
    }
}

private fun platformEmoji(platform: String) = when (platform.lowercase()) {
    "youtube" -> "▶"
    "medium" -> "M"
    "linkedin" -> "in"
    "x", "twitter" -> "X"
    "threads" -> "@"
    "substack" -> "S"
    "devto" -> "D"
    "hackernews" -> "Y"
    else -> "·"
}

private fun platformColor(platform: String) = when (platform.lowercase()) {
    "youtube" -> Color(0xFFFF0000)
    "medium" -> Color(0xFF000000)
    "linkedin" -> Color(0xFF0A66C2)
    "x", "twitter" -> Color(0xFF000000)
    "threads" -> Color(0xFF000000)
    "substack" -> Color(0xFFFF6719)
    "devto" -> Color(0xFF0A0A0A)
    "hackernews" -> Color(0xFFFF6600)
    else -> Color(0xFF888888)
}

data class WidgetItem(val slug: String, val title: String, val platform: String, val read: Boolean)

private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
private val listType = Types.newParameterizedType(List::class.java, WidgetItem::class.java)
private val adapter = moshi.adapter<List<WidgetItem>>(listType)

fun parseItems(json: String): List<WidgetItem> =
    runCatching { adapter.fromJson(json) ?: emptyList() }.getOrDefault(emptyList())

suspend fun updateWidgetData(context: Context, items: List<WidgetItem>) {
    val json = adapter.toJson(items)
    GlanceAppWidgetManager(context).getGlanceIds(FeedWidget::class.java).forEach { id ->
        updateAppWidgetState(context, PreferencesGlanceStateDefinition, id) {
            it.toMutablePreferences().apply { this[KEY_ITEMS] = json }
        }
        FeedWidget().update(context, id)
    }
}
