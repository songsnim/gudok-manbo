package com.contentscurator

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material.icons.Icons
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
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.contentscurator.ui.agent.AgentScreen
import com.contentscurator.ui.feed.FeedScreen
import com.contentscurator.ui.subscriptions.SubscriptionsScreen
import com.contentscurator.ui.theme.ContentsCuratorTheme
import com.contentscurator.work.FeedSyncWorker

private enum class Tab(val route: String, val label: String, val icon: ImageVector) {
    Feed("feed", "피드", Icons.Default.Home),
    Subscriptions("subscriptions", "구독", Icons.Default.List),
    Agent("agent", "에이전트", Icons.Default.SmartToy),
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 앱 시작 시 위젯 즉시 갱신
        WorkManager.getInstance(this).enqueue(
            OneTimeWorkRequestBuilder<FeedSyncWorker>().build()
        )
        FeedSyncWorker.schedule(this)
        enableEdgeToEdge()
        setContent {
            ContentsCuratorTheme {
                MainNav()
            }
        }
    }
}

@Composable
private fun MainNav() {
    val navController = rememberNavController()
    val currentEntry by navController.currentBackStackEntryAsState()
    val currentRoute = currentEntry?.destination?.route

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
            composable(Tab.Feed.route) { FeedScreen() }
            composable(Tab.Subscriptions.route) { SubscriptionsScreen() }
            composable(Tab.Agent.route) { AgentScreen() }
        }
    }
}
