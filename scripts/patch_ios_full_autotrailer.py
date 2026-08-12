from pathlib import Path

root = Path('.')

policy_path = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/core/build/AppFeaturePolicy.ios.kt'
policy = policy_path.read_text(encoding='utf-8')
policy = policy.replace(
    'actual val heroTrailerPlaybackSupported: Boolean = false',
    'actual val heroTrailerPlaybackSupported: Boolean = true',
)
policy_path.write_text(policy, encoding='utf-8')

details_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/details/MetaDetailsScreen.kt'
details = details_path.read_text(encoding='utf-8')
old_gate = '''val heroTrailerPlaybackEnabled = AppFeaturePolicy.heroTrailerPlaybackSupported &&
                    inAppTrailerPlaybackEnabled &&
                    metaScreenSettingsUiState.heroTrailerPlayback'''
new_gate = '''val heroTrailerPlaybackEnabled = AppFeaturePolicy.heroTrailerPlaybackSupported &&
                    inAppTrailerPlaybackEnabled'''
if old_gate in details:
    details = details.replace(old_gate, new_gate, 1)
elif new_gate not in details:
    raise SystemExit('Could not locate hero trailer autoplay gate')
details_path.write_text(details, encoding='utf-8')

hero_path = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/details/components/HeroTrailerPlayerSurface.ios.kt'
hero_path.write_text(r'''package com.nuvio.app.features.details.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.interop.UIKitViewController
import com.nuvio.app.features.player.NuvioPlayerBridgeFactory
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

@OptIn(ExperimentalForeignApi::class)
@Composable
actual fun HeroTrailerPlayerSurface(
    sourceUrl: String,
    sourceAudioUrl: String?,
    playWhenReady: Boolean,
    muted: Boolean,
    modifier: Modifier,
    onReady: () -> Unit,
    onEnded: () -> Unit,
    onError: () -> Unit,
) {
    val latestOnReady = rememberUpdatedState(onReady)
    val latestOnEnded = rememberUpdatedState(onEnded)
    val latestOnError = rememberUpdatedState(onError)
    val bridge = remember(sourceUrl, sourceAudioUrl) { NuvioPlayerBridgeFactory.create() }

    var readyReported by remember(sourceUrl, sourceAudioUrl) { mutableStateOf(false) }
    var endedReported by remember(sourceUrl, sourceAudioUrl) { mutableStateOf(false) }
    var errorReported by remember(sourceUrl, sourceAudioUrl) { mutableStateOf(false) }

    if (bridge == null) {
        LaunchedEffect(Unit) {
            if (!errorReported) {
                errorReported = true
                latestOnError.value()
            }
        }
        return
    }

    LaunchedEffect(bridge, sourceUrl, sourceAudioUrl) {
        bridge.loadFileWithAudio(
            videoUrl = sourceUrl,
            audioUrl = sourceAudioUrl,
            headersJson = null,
            subtitlesJson = null,
        )
        bridge.setResizeMode(2)
        bridge.setMuted(muted)
        if (playWhenReady) bridge.play() else bridge.pause()
    }

    LaunchedEffect(bridge, playWhenReady) {
        if (playWhenReady) bridge.play() else bridge.pause()
    }

    LaunchedEffect(bridge, muted) {
        bridge.setMuted(muted)
    }

    LaunchedEffect(bridge) {
        while (isActive) {
            val isLoading = bridge.getIsLoading()
            val isPlaying = bridge.getIsPlaying()
            val isEnded = bridge.getIsEnded()
            val durationMs = bridge.getDurationMs()
            val errorMessage = bridge.getErrorMessage()

            if (!readyReported && !isLoading && !isEnded && (isPlaying || durationMs > 0L)) {
                readyReported = true
                latestOnReady.value()
            }
            if (!endedReported && isEnded) {
                endedReported = true
                latestOnEnded.value()
            }
            if (!errorReported && errorMessage.isNotBlank()) {
                errorReported = true
                latestOnError.value()
            }
            delay(250L)
        }
    }

    DisposableEffect(bridge) {
        onDispose { bridge.destroy() }
    }

    Box(modifier = modifier) {
        UIKitViewController(
            factory = { bridge.createPlayerViewController() },
            modifier = Modifier.fillMaxSize(),
            onResize = { viewController, rect -> viewController.view.setFrame(rect) },
            interactive = false,
        )
    }
}
''', encoding='utf-8')

# Preserve the proven iOS plugin stability fix from the plugin-only build.
# Full mode can expose hundreds of providers; without a limit each scraper may
# create its own native QuickJS runtime at once, causing a process-level crash.
plugin_runtime_path = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/plugins/runtime/PluginRuntime.kt'
plugin_runtime = plugin_runtime_path.read_text(encoding='utf-8')

sync_import_anchor = 'import kotlinx.coroutines.withTimeout\n'
if 'import kotlinx.coroutines.sync.Semaphore' not in plugin_runtime:
    if sync_import_anchor not in plugin_runtime:
        raise SystemExit('Could not locate coroutine import anchor in Full PluginRuntime')
    plugin_runtime = plugin_runtime.replace(
        sync_import_anchor,
        sync_import_anchor + 'import kotlinx.coroutines.sync.Semaphore\nimport kotlinx.coroutines.sync.withPermit\n',
        1,
    )

json_anchor = '    private val json = Json { ignoreUnknownKeys = true }\n'
semaphore_decl = '    private val executionSemaphore = Semaphore(4)\n'
if semaphore_decl not in plugin_runtime:
    if json_anchor not in plugin_runtime:
        raise SystemExit('Could not locate Full PluginRuntime json field')
    plugin_runtime = plugin_runtime.replace(json_anchor, json_anchor + semaphore_decl, 1)

old_execute = '''        withTimeout(PLUGIN_TIMEOUT_MS) {
            executePluginInternal(
                code = code,
                tmdbId = tmdbId,
                mediaType = mediaType,
                season = season,
                episode = episode,
                scraperId = scraperId,
                scraperSettings = scraperSettingsMap,
            )
        }'''
new_execute = '''        executionSemaphore.withPermit {
            withTimeout(PLUGIN_TIMEOUT_MS) {
                executePluginInternal(
                    code = code,
                    tmdbId = tmdbId,
                    mediaType = mediaType,
                    season = season,
                    episode = episode,
                    scraperId = scraperId,
                    scraperSettings = scraperSettingsMap,
                )
            }
        }'''
if old_execute in plugin_runtime:
    plugin_runtime = plugin_runtime.replace(old_execute, new_execute, 1)
elif new_execute not in plugin_runtime:
    raise SystemExit('Could not locate Full executePlugin timeout block')

plugin_runtime_path.write_text(plugin_runtime, encoding='utf-8')

full_plugins_page = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/settings/PluginsSettingsPage.kt'
p2p_file = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/p2p/P2pStreamingEngine.ios.kt'

patched_policy = policy_path.read_text(encoding='utf-8')
if 'actual val pluginsEnabled: Boolean = true' not in patched_policy:
    raise SystemExit('Full plugins policy is not enabled')
if 'actual val p2pEnabled: Boolean = true' not in patched_policy:
    raise SystemExit('Full P2P policy is not enabled')
if 'actual val heroTrailerPlaybackSupported: Boolean = true' not in patched_policy:
    raise SystemExit('Hero trailer policy patch failed')
if 'PluginsSettingsPageContent' not in full_plugins_page.read_text(encoding='utf-8'):
    raise SystemExit('Real Full plugin settings page is missing')
if not p2p_file.is_file():
    raise SystemExit('iOS Full P2P engine implementation is missing')
if 'NuvioPlayerBridgeFactory.create()' not in hero_path.read_text(encoding='utf-8'):
    raise SystemExit('Dedicated Full iOS hero player patch failed')
patched_runtime = plugin_runtime_path.read_text(encoding='utf-8')
if 'executionSemaphore = Semaphore(4)' not in patched_runtime or 'executionSemaphore.withPermit' not in patched_runtime:
    raise SystemExit('Full QuickJS execution concurrency limit was not installed')

print('Applied iOS Full + P2P + Auto Trailer V2 with max 4 concurrent QuickJS plugin executions.')
