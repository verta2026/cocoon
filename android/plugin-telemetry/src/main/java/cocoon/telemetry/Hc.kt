package cocoon.telemetry

// Health Connect 原生读：心率(今日曲线+最新)/步数/睡眠/血氧。
// 链路：手表 → 官方app → Health Connect → 这里 → /widget/phone 的 hc 区。
// Gadgetbridge→Tasker 心率链的接班人。每个数据类型各自探权限，缺哪读哪。

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.OxygenSaturationRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

object Hc {

    val PERMS: Set<String> = setOf(
        HealthPermission.getReadPermission(HeartRateRecord::class),
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(OxygenSaturationRecord::class),
    )

    fun available(ctx: Context): Boolean =
        HealthConnectClient.getSdkStatus(ctx) == HealthConnectClient.SDK_AVAILABLE

    fun grantedAny(ctx: Context): Boolean = try {
        runBlocking {
            HealthConnectClient.getOrCreate(ctx).permissionController
                .getGrantedPermissions().any { it in PERMS }
        }
    } catch (e: Exception) { false }

    fun collect(ctx: Context): JSONObject? {
        // 不拿 available()/getSdkStatus 当门槛——ColorOS 上它谎报系统内置 HC 不可用(false),
        // 但 getOrCreate + 实际读取是好的(部署实测)。直接试读,read() 内部按已授权项逐个读,
        // 真不可用会在 getOrCreate 抛异常时兜住。
        return try {
            runBlocking { read(HealthConnectClient.getOrCreate(ctx)) }
        } catch (e: Exception) { null }
    }

    private suspend fun read(client: HealthConnectClient): JSONObject? {
        val granted = client.permissionController.getGrantedPermissions()
        if (granted.none { it in PERMS }) return null
        val out = JSONObject()
        val zone = ZoneId.systemDefault()
        val dayStart = LocalDate.now(zone).atStartOfDay(zone).toInstant()
        val now = Instant.now()

        if (HealthPermission.getReadPermission(HeartRateRecord::class) in granted) try {
            val recs = client.readRecords(ReadRecordsRequest(
                HeartRateRecord::class, TimeRangeFilter.between(dayStart, now))).records
            val samples = recs.flatMap { it.samples }.sortedBy { it.time }
            if (samples.isNotEmpty()) {
                val vals = samples.map { it.beatsPerMinute.toInt() }
                val cap = 48
                val today = JSONArray()
                if (vals.size <= cap) vals.forEach { today.put(it) }
                else {
                    val step = vals.size.toDouble() / cap
                    for (i in 0 until cap) today.put(vals[(i * step).toInt()])
                }
                out.put("heart", JSONObject()
                    .put("bpm", vals.last())
                    .put("ts", samples.last().time.toString())
                    .put("today", today))
            }
        } catch (e: Exception) {}

        if (HealthPermission.getReadPermission(StepsRecord::class) in granted) try {
            val agg = client.aggregate(AggregateRequest(
                setOf(StepsRecord.COUNT_TOTAL), TimeRangeFilter.between(dayStart, now)))
            agg[StepsRecord.COUNT_TOTAL]?.let { out.put("steps_today", it) }
        } catch (e: Exception) {}

        if (HealthPermission.getReadPermission(SleepSessionRecord::class) in granted) try {
            val recs = client.readRecords(ReadRecordsRequest(
                SleepSessionRecord::class,
                TimeRangeFilter.between(now.minusSeconds(36 * 3600), now))).records
            recs.maxByOrNull { it.endTime }?.let {
                out.put("sleep", JSONObject()
                    .put("start", it.startTime.toString())
                    .put("end", it.endTime.toString())
                    .put("min", (it.endTime.epochSecond - it.startTime.epochSecond) / 60))
            }
        } catch (e: Exception) {}

        if (HealthPermission.getReadPermission(OxygenSaturationRecord::class) in granted) try {
            val recs = client.readRecords(ReadRecordsRequest(
                OxygenSaturationRecord::class,
                TimeRangeFilter.between(now.minusSeconds(24 * 3600), now))).records
            recs.maxByOrNull { it.time }?.let {
                out.put("spo2", it.percentage.value)
            }
        } catch (e: Exception) {}

        return if (out.length() == 0) null else out
    }
}
