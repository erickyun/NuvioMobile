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

full_plugins_page = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/settings/PluginsSettingsPage.kt'
p2p_file = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/p2p/P2pStreamingEngine.ios.kt'

if 'actual val pluginsEnabled: Boolean = true' not in policy_path.read_text(encoding='utf-8'):
    raise SystemExit('Full plugins policy is not enabled')
if 'actual val p2pEnabled: Boolean = true' not in policy_path.read_text(encoding='utf-8'):
    raise SystemExit('Full P2P policy is not enabled')
if 'actual val heroTrailerPlaybackSupported: Boolean = true' not in policy_path.read_text(encoding='utf-8'):
    raise SystemExit('Hero trailer policy patch failed')
if 'PluginsSettingsPageContent' not in full_plugins_page.read_text(encoding='utf-8'):
    raise SystemExit('Real Full plugin settings page is missing')
if not p2p_file.is_file():
    raise SystemExit('iOS Full P2P engine implementation is missing')
if 'NuvioPlayerBridgeFactory.create()' not in hero_path.read_text(encoding='utf-8'):
    raise SystemExit('Dedicated Full iOS hero player patch failed')

print('Applied real iOS Full + Auto Trailer V2 patch. Plugins/P2P stay native Full implementations.')
