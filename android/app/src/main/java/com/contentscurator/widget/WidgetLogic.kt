package com.contentscurator.widget

/** 위젯 한 행. 본문은 들고 다니지 않는다 — 위젯은 입간판이다. */
data class WidgetItem(
    val slug: String,
    val title: String,
    val platform: String,
    val author: String,
    val thumbnailUrl: String? = null,
    val avatarUrl: String? = null,
    val date: String = "",   // 게시일, 없으면 수집일 — 인앱 날짜 줄과 같은 규칙
)

/** 마지막 동기화 결과. 렌더 중에는 네트워크를 쓰지 않으므로 이것만 본다. */
data class WidgetSnapshot(val items: List<WidgetItem>, val hours: List<Int>)

/** 수집 최신순 목록에서 안 읽은 것만 앞에서 n개, 그리고 미읽음 총개수. */
fun pickUnread(items: List<WidgetItem>, read: Set<String>, n: Int): Pair<List<WidgetItem>, Int> {
    val unread = items.filterNot { it.slug in read }
    return unread.take(n) to unread.size
}

/** 빈 상태 문구 — 지금 이후 첫 수집 시각, 없으면 내일 첫 시각. */
fun nextCollectLabel(hours: List<Int>, nowHour: Int): String {
    if (hours.isEmpty()) return "새 글을 기다리고 있어요"
    val next = hours.sorted().firstOrNull { it > nowHour }
    return if (next != null) "${next}시에 새 글이 와요" else "내일 ${hours.min()}시에 새 글이 와요"
}

/** 2026-10-05 → 26-10-05. 형식이 다르면 그대로. */
fun shortDate(date: String): String =
    if (Regex("""\d{4}-\d{2}-\d{2}""").matches(date)) date.substring(2) else date
