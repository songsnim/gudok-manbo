package com.contentscurator.widget

import org.junit.Assert.assertEquals
import org.junit.Test

class WidgetLogicTest {
    private fun item(slug: String, collected: String) = WidgetItem(slug, slug, "youtube", "a", collected = collected)

    @Test
    fun pickTodayKeepsOrderAndDropsOtherDays() {
        val items = listOf(item("s1", "2026-10-08"), item("s2", "2026-10-07"), item("s3", "2026-10-08"))
        assertEquals(listOf("s1", "s3"), pickToday(items, "2026-10-08").map { it.slug })
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
