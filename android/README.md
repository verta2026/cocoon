# cocoon-android

A thin Android shell for a cocoon deployment: a WebView wrapping your cocoon
web UI, plus optional native feature plugins.

## Layout

| Module | What it is |
| --- | --- |
| `:common` | `Net` (bridge HTTP client), the `CocoonPlugin` contract, deployment `BuildConfig` |
| `:app` | Core shell: WebView + login token capture + FCM channel + quick-reply notifications + system alarm relay |
| `:plugin-widgets` | Home-screen widgets: agent status, heart rate, next reminder, tasks, quick pokes, health quick-log, notes |
| `:plugin-guard` | Remote app lock (blocklist + overlay) and screen share (MediaProjection frames posted to the bridge) |
| `:plugin-call` | Full-screen incoming-call page over FCM, lock-screen visible, looping ringtone |
| `:plugin-telemetry` | Battery / location / screen-time / Health Connect reporting to `/widget/phone` |

The core never references plugin classes at compile time. Each plugin exposes a
Kotlin `object` (e.g. `cocoon.guard.GuardPlugin`) implementing `CocoonPlugin`,
discovered reflectively at runtime — deleting a module from the build simply
removes the feature.

## Configure

Everything deployment-specific lives in `gradle.properties` (override in
`local.properties` or with `-P` flags):

```properties
cocoon.baseUrl=https://your.host/bridge
cocoon.homeUrl=https://your.host/
cocoon.storageNs=cocoon          # webapp localStorage namespace (token key = <ns>_token)
cocoon.landscapePages=           # comma-separated page paths forced to landscape
cocoon.plugins=widgets,guard,call,telemetry
```

Drop `cocoon.plugins` entries you don't want; the modules are then neither
included nor compiled.

## Push (optional)

FCM needs your own Firebase project. Put its `google-services.json` next to
`app/build.gradle.kts` — the gms plugin is applied only when the file exists,
so the project builds fine without it (push features stay dormant).

Data-message contract handled by the shell:

| `kind` | Behavior | Needs |
| --- | --- | --- |
| `msg` (default) | High-priority notification with inline quick-reply (POSTs to `/widget/reply`) | core |
| `alarm` | Sets an alarm in the system clock app (`hour`/`minutes`/`label`); backgrounded, posts a tap-to-set notification instead | core |
| `call` | Full-screen incoming call page (`title`/`reason`) | `call` |
| `lock` / `unlock` | Starts/refreshes the app-lock blocklist from `GET /widget/applock` | `guard` |
| `screen` | Notification that opens the screen-share page (`/screen.html?auto=1`) | `guard` |

## Ringtone

`plugin-call` uses the system default ringtone. To ship your own, add a file at
`plugin-call/src/main/res/raw/ringtone.mp3`.

## Build

```
./gradlew assembleRelease
```

Release signing reads `KEYSTORE_PATH` / `KEYSTORE_PASS` / `KEY_ALIAS` /
`KEY_PASS` from the environment (e.g. CI secrets); without them only debug
builds are signed.

## Bridge endpoints used

`/widget/state`, `/widget/tasks`, `/widget/tasks/done`, `/widget/poke`,
`/widget/reply`, `/widget/heartrate`, `/widget/reminder`, `/widget/mailbox`,
`/widget/health`, `/widget/health/quick`, `/widget/phone`, `/widget/fcm_token`,
`/widget/applock`, `/widget/screen` — all optional; a deployment implements the
ones matching the plugins it ships. All are instance routes (see
`docs/split-status.md`), not cocoon core.
