package com.contentscurator.widget

import org.junit.Assert.assertEquals
import org.junit.Test

class WidgetLogicTest {
    private fun item(slug: String) = WidgetItem(slug, slug, "youtube", "a")

    @Test
    fun pickUnreadKeepsOrderSkipsReadAndCaps() {
        val items = (1..8).map { item("s$it") }  // 수집 최신순
        val (shown, total) = pickUnread(items, setOf("s1", "s3"), 5)
        assertEquals(listOf("s2", "s4", "s5", "s6", "s7"), shown.map { it.slug })
        assertEquals(6, total)
    }

    @Test
    fun nextCollectLabelWrapsToTomorrow() {
        assertEquals("11시에 새 글이 와요", nextCollectLabel(listOf(17, 6, 11), 6))
        assertEquals("내일 6시에 새 글이 와요", nextCollectLabel(listOf(6, 11, 17), 17))
    }

    @Test
    fun shortDateDropsCentury() {
        assertEquals("26-10-05", shortDate("2026-10-05"))
        assertEquals("", shortDate(""))
    }
}
