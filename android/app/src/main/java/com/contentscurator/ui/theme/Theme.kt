package com.contentscurator.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = Primary,
    onPrimary = OnPrimary,
    background = Background,
    surface = Surface,
    onBackground = OnBackground,
    outline = Outline,
)

@Composable
fun ContentsCuratorTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        content = content,
    )
}
