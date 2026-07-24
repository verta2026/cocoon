package cocoon.common

import android.content.Context
import android.content.Intent

/** The app's launcher intent — lets library modules open the main activity
 *  without a compile-time reference to the app module's class. */
fun appLaunchIntent(ctx: Context): Intent =
    ctx.packageManager.getLaunchIntentForPackage(ctx.packageName) ?: Intent()
