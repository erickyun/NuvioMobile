from pathlib import Path
import shutil

root = Path('.')

appstore_trailer_dir = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/features/trailer'
appstore_trailer_dir.mkdir(parents=True, exist_ok=True)

shutil.copy2(
    root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/trailer/InAppYouTubeExtractor.kt',
    appstore_trailer_dir / 'InAppYouTubeExtractor.kt',
)
shutil.copy2(
    root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/trailer/TrailerExtractionPlatform.ios.kt',
    appstore_trailer_dir / 'TrailerExtractionPlatform.ios.kt',
)
shutil.copy2(
    root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/trailer/TrailerPlaybackResolver.kt',
    appstore_trailer_dir / 'TrailerPlaybackResolver.ios.kt',
)

policy_path = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/core/build/AppFeaturePolicy.ios.kt'
policy = policy_path.read_text(encoding='utf-8')
policy = policy.replace(
    'actual val trailerPlaybackMode: TrailerPlaybackMode = TrailerPlaybackMode.EXTERNAL',
    'actual val trailerPlaybackMode: TrailerPlaybackMode = TrailerPlaybackMode.IN_APP',
)
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
if old_gate not in details:
    raise SystemExit('Could not locate hero trailer autoplay gate')
details_path.write_text(details.replace(old_gate, new_gate, 1), encoding='utf-8')

hero_path = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/features/details/components/HeroTrailerPlayerSurface.ios.kt'
hero_path.parent.mkdir(parents=True, exist_ok=True)
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
    val bridge = remember(sourceUrl, sourceAudioUrl) {
        NuvioPlayerBridgeFactory.create()
    }

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
        onDispose {
            bridge.destroy()
        }
    }

    // Dedicated hero surface: do NOT call syncVideoSurfaceLayout here.
    // UIKit owns the exact embedded view size and MPV's Metal layer follows view.bounds.
    Box(modifier = modifier) {
        UIKitViewController(
            factory = { bridge.createPlayerViewController() },
            modifier = Modifier.fillMaxSize(),
            onResize = { viewController, rect ->
                viewController.view.setFrame(rect)
            },
            interactive = false,
        )
    }
}
''', encoding='utf-8')

if 'TrailerPlaybackMode.IN_APP' not in policy_path.read_text(encoding='utf-8'):
    raise SystemExit('Trailer playback policy patch failed')
if 'heroTrailerPlaybackSupported: Boolean = true' not in policy_path.read_text(encoding='utf-8'):
    raise SystemExit('Hero trailer support patch failed')
if 'NuvioPlayerBridgeFactory.create()' not in hero_path.read_text(encoding='utf-8'):
    raise SystemExit('Dedicated iOS hero player patch failed')
if 'syncVideoSurfaceLayout' in hero_path.read_text(encoding='utf-8').replace('// Dedicated hero surface: do NOT call syncVideoSurfaceLayout here.', ''):
    raise SystemExit('Hero player must not use external surface sizing')

print('Applied isolated iOS Auto Trailer V2 patch.')
