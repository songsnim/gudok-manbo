package com.contentscurator

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmarks
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.contentscurator.ui.agent.AgentScreen
import com.contentscurator.ui.collection.CollectionScreen
import com.contentscurator.ui.feed.FeedScreen
import com.contentscurator.ui.subscriptions.SubscriptionsScreen
import com.contentscurator.ui.theme.ContentsCuratorTheme
import com.contentscurator.work.FeedSyncWorker

private enum class Tab(val route: String, val label: String, val icon: ImageVector) {
    Feed("feed", "피드", Icons.Default.Home),
    Subscriptions("subscriptions", "구독", Icons.Default.List),
    Agent("agent", "에이전트", Icons.Default.SmartToy),
    Collection("collection", "컬렉션", Icons.Default.Bookmarks),
}

class MainActivity : ComponentActivity() {
    /** 위젯 행에서 넘어온 slug. 본문을 연 뒤 비운다. */
    private val openSlug = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 앱 시작 시 위젯 즉시 갱신
        FeedSyncWorker.runNow(this)
        FeedSyncWorker.schedule(this)
        if (savedInstanceState == null) openSlug.value = intent.getStringExtra(EXTRA_SLUG)
        enableEdgeToEdge()
        setContent {
            ContentsCuratorTheme {
                MainNav(openSlug.value) { openSlug.value = null }
            }
        }
    }

    // singleTask — 앱이 떠 있을 때 위젯을 탭하면 여기로 온다
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intent.getStringExtra(EXTRA_SLUG)?.let { openSlug.value = it }
    }

    companion object {
        const val EXTRA_SLUG = "slug"
    }
}

@Composable
private fun MainNav(openSlug: String?, onOpened: () -> Unit) {
    val navController = rememberNavController()
    val currentEntry by navController.currentBackStackEntryAsState()
    val currentRoute = currentEntry?.destination?.route

    LaunchedEffect(openSlug) {
        if (openSlug != null && currentRoute != Tab.Feed.route) {
            navController.navigate(Tab.Feed.route) {
                popUpTo(navController.graph.startDestinationId) { saveState = true }
                launchSingleTop = true
            }
        }
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = currentRoute == tab.route,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.startDestinationId) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                    )
                }
            }
        }
    ) { _ ->
        NavHost(navController = navController, startDestination = Tab.Feed.route) {
            composable(Tab.Feed.route) { FeedScreen(openSlug = openSlug, onOpened = onOpened) }
            composable(Tab.Subscriptions.route) { SubscriptionsScreen() }
            composable(Tab.Agent.route) { AgentScreen() }
            composable(Tab.Collection.route) { CollectionScreen() }
        }
    }
}
