package com.contentscurator.data.db

import android.content.Context
import androidx.room.*

@Entity(tableName = "read_status")
data class ReadStatusEntity(
    @PrimaryKey val slug: String,
    val readAt: Long = System.currentTimeMillis(),
)

@Dao
interface ReadStatusDao {
    @Query("SELECT slug FROM read_status")
    suspend fun getAllReadSlugs(): List<String>

    @Query("SELECT EXISTS(SELECT 1 FROM read_status WHERE slug = :slug)")
    suspend fun isRead(slug: String): Boolean

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun markRead(entity: ReadStatusEntity)

    @Query("DELETE FROM read_status WHERE slug = :slug")
    suspend fun markUnread(slug: String)
}

@Database(entities = [ReadStatusEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun readStatusDao(): ReadStatusDao

    companion object {
        @Volatile private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase =
            INSTANCE ?: synchronized(this) {
                Room.databaseBuilder(context.applicationContext, AppDatabase::class.java, "curator.db")
                    .build()
                    .also { INSTANCE = it }
            }
    }
}
