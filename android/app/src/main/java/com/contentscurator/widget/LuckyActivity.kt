package com.contentscurator.widget

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.contentscurator.data.ServerResolver
import com.contentscurator.data.api.LuckyNote
import com.contentscurator.data.api.RetrofitClient
import com.contentscurator.ui.theme.ContentsCuratorTheme
import dev.jeziellago.compose.markdowntext.MarkdownText

/**
 * 위젯 주사위 버튼 → 바탕화면 위에 뜨는 모달. 내가 쓴 노트 하나를 무작위로 보여 준다.
 * 투명 테마라 뒤로 홈 화면이 보이고, 앱 본체(MainActivity)와 다른 task라 앱을 띄우지 않는다.
 */
class LuckyActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ContentsCuratorTheme { LuckyDialog(onClose = ::finish) } }
    }
}

@Composable
private fun LuckyDialog(onClose: () -> Unit) {
    val context = LocalContext.current
    var roll by remember { mutableIntStateOf(0) }
    val note by produceState<Result<LuckyNote>?>(null, roll) {
        value = null
        value = runCatching {
            ServerResolver.ensure(context)
            RetrofitClient.api.getLucky()
        }
    }

    Dialog(onDismissRequest = onClose) {
        Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(start = 20.dp, end = 12.dp, top = 20.dp, bottom = 8.dp)) {
                val n = note
                when {
                    n == null -> Box(Modifier.fillMaxWidth().height(120.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                    n.isFailure -> Text(
                        "노트를 불러오지 못했어요",
                        color = MaterialTheme.colorScheme.outline,
                        modifier = Modifier.padding(vertical = 24.dp),
                    )
                    else -> {
                        val it = n.getOrThrow()
                        // 본문만 스크롤 — 제목과 버튼은 고정
                        Column(Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()).padding(end = 8.dp)) {
                            Text(it.title, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                            if (it.date.isNotBlank()) {
                                Spacer(Modifier.height(2.dp))
                                Text(it.date, fontSize = 12.sp, color = MaterialTheme.colorScheme.outline)
                            }
                            Spacer(Modifier.height(12.dp))
                            MarkdownText(
                                markdown = it.body,
                                style = MaterialTheme.typography.bodyLarge.copy(
                                    color = MaterialTheme.colorScheme.onBackground,
                                    fontSize = 15.sp,
                                    lineHeight = 22.sp,
                                ),
                            )
                        }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = { roll++ }, enabled = note != null) { Text("다시 뽑기") }
                    TextButton(onClick = onClose) { Text("닫기") }
                }
            }
        }
    }
}
