package cocoon.common

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

object Net {
    const val BASE = BuildConfig.BASE_URL

    fun token(ctx: Context): String =
        ctx.getSharedPreferences("cocoon", Context.MODE_PRIVATE).getString("token", "") ?: ""

    fun saveToken(ctx: Context, t: String) {
        ctx.getSharedPreferences("cocoon", Context.MODE_PRIVATE).edit().putString("token", t).apply()
    }

    fun get(ctx: Context, path: String): JSONObject? = request(ctx, path, "GET", null)

    fun post(ctx: Context, path: String, body: JSONObject?): JSONObject? =
        request(ctx, path, "POST", body ?: JSONObject())

    private fun request(ctx: Context, path: String, method: String, body: JSONObject?): JSONObject? {
        val tok = token(ctx)
        if (tok.isEmpty()) return null
        return try {
            val sep = if (path.contains('?')) "&" else "?"
            val conn = URL("$BASE$path${sep}token=${URLEncoder.encode(tok, "UTF-8")}")
                .openConnection() as HttpURLConnection
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.requestMethod = method
            if (body != null) {
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val text = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            JSONObject(text)
        } catch (e: Exception) {
            android.util.Log.w("Net", "$method $path failed: ${e.message}")
            null
        }
    }
}
