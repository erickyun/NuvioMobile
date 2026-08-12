from pathlib import Path

root = Path('.')


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'Could not locate {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


# ---------------------------------------------------------------------------
# Full iOS + Auto Trailer V2
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Configurable plugin QuickJS concurrency
# 0 = unlimited. Any positive Int = that many concurrent plugin executions.
# The value is persisted in the existing per-profile plugin state.
# ---------------------------------------------------------------------------
models_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/plugins/PluginModels.kt'
replace_once(
    models_path,
    '''data class PluginsUiState(
    val pluginsEnabled: Boolean = true,
    val groupStreamsByRepository: Boolean = false,
    val repositories: List<PluginRepositoryItem> = emptyList(),''',
    '''data class PluginsUiState(
    val pluginsEnabled: Boolean = true,
    val groupStreamsByRepository: Boolean = false,
    val maxConcurrentScrapers: Int = 4,
    val repositories: List<PluginRepositoryItem> = emptyList(),''',
    'PluginsUiState concurrency field',
)
replace_once(
    models_path,
    '''internal data class StoredPluginsState(
    val pluginsEnabled: Boolean = true,
    val groupStreamsByRepository: Boolean = false,
    val repositories: List<StoredPluginRepository> = emptyList(),''',
    '''internal data class StoredPluginsState(
    val pluginsEnabled: Boolean = true,
    val groupStreamsByRepository: Boolean = false,
    val maxConcurrentScrapers: Int = 4,
    val repositories: List<StoredPluginRepository> = emptyList(),''',
    'StoredPluginsState concurrency field',
)
replace_once(
    models_path,
    '''    StoredPluginsState(
        pluginsEnabled = pluginsEnabled,
        groupStreamsByRepository = groupStreamsByRepository,
        repositories = repositories.map { repository ->''',
    '''    StoredPluginsState(
        pluginsEnabled = pluginsEnabled,
        groupStreamsByRepository = groupStreamsByRepository,
        maxConcurrentScrapers = maxConcurrentScrapers,
        repositories = repositories.map { repository ->''',
    'stored concurrency persistence',
)

expect_repo_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/plugins/PluginRepository.kt'
replace_once(
    expect_repo_path,
    '''    fun setGroupStreamsByRepository(enabled: Boolean)

    fun getEnabledScrapersForType(type: String): List<PluginScraper>''',
    '''    fun setGroupStreamsByRepository(enabled: Boolean)

    fun setMaxConcurrentScrapers(limit: Int)

    fun getEnabledScrapersForType(type: String): List<PluginScraper>''',
    'PluginRepository concurrency setter expect',
)

full_repo_path = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/plugins/PluginRepository.kt'
replace_once(
    full_repo_path,
    '''            _uiState.value = PluginsUiState(
                pluginsEnabled = _uiState.value.pluginsEnabled,
                groupStreamsByRepository = _uiState.value.groupStreamsByRepository,
                repositories = nextRepos,''',
    '''            _uiState.value = PluginsUiState(
                pluginsEnabled = _uiState.value.pluginsEnabled,
                groupStreamsByRepository = _uiState.value.groupStreamsByRepository,
                maxConcurrentScrapers = _uiState.value.maxConcurrentScrapers,
                repositories = nextRepos,''',
    'pullFromServer concurrency preservation',
)
replace_once(
    full_repo_path,
    '''    actual fun setGroupStreamsByRepository(enabled: Boolean) {
        initialize()
        _uiState.update { it.copy(groupStreamsByRepository = enabled) }
        persist()
    }

    actual fun getEnabledScrapersForType(type: String): List<PluginScraper> {''',
    '''    actual fun setGroupStreamsByRepository(enabled: Boolean) {
        initialize()
        _uiState.update { it.copy(groupStreamsByRepository = enabled) }
        persist()
    }

    actual fun setMaxConcurrentScrapers(limit: Int) {
        initialize()
        if (limit < 0) return
        _uiState.update { it.copy(maxConcurrentScrapers = limit) }
        persist()
    }

    actual fun getEnabledScrapersForType(type: String): List<PluginScraper> {''',
    'PluginRepository concurrency setter actual',
)
replace_once(
    full_repo_path,
    '''            state = PluginsUiState(
                pluginsEnabled = stored?.pluginsEnabled ?: true,
                groupStreamsByRepository = stored?.groupStreamsByRepository ?: false,
                repositories = stored?.repositories''',
    '''            state = PluginsUiState(
                pluginsEnabled = stored?.pluginsEnabled ?: true,
                groupStreamsByRepository = stored?.groupStreamsByRepository ?: false,
                maxConcurrentScrapers = stored?.maxConcurrentScrapers ?: 4,
                repositories = stored?.repositories''',
    'stored concurrency restore',
)

plugins_screen_path = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/plugins/PluginsSettingsScreen.kt'
replace_once(
    plugins_screen_path,
    '''    var configuringScraper by remember { mutableStateOf<PluginScraper?>(null) }
    var configuringLayout by remember { mutableStateOf<String?>(null) }

    val sortedRepos = remember(uiState.repositories) {''',
    '''    var configuringScraper by remember { mutableStateOf<PluginScraper?>(null) }
    var configuringLayout by remember { mutableStateOf<String?>(null) }
    var concurrencyText by rememberSaveable { mutableStateOf(uiState.maxConcurrentScrapers.toString()) }

    LaunchedEffect(uiState.maxConcurrentScrapers) {
        if (concurrencyText.toIntOrNull() != uiState.maxConcurrentScrapers) {
            concurrencyText = uiState.maxConcurrentScrapers.toString()
        }
    }

    val sortedRepos = remember(uiState.repositories) {''',
    'plugin settings concurrency state',
)
replace_once(
    plugins_screen_path,
    '''                Switch(
                    checked = uiState.groupStreamsByRepository,
                    onCheckedChange = { PluginRepository.setGroupStreamsByRepository(it) },
                )
            }
        }

        NuvioSectionLabel(stringResource(Res.string.plugins_section_add_repo))''',
    '''                Switch(
                    checked = uiState.groupStreamsByRepository,
                    onCheckedChange = { PluginRepository.setGroupStreamsByRepository(it) },
                )
            }

            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "Eşzamanlı QuickJS scraper sayısı",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = "Aynı anda çalışacak plugin sağlayıcı sayısını sen belirle. 0 = sınırsız. Yüksek değerler daha hızlı olabilir ancak iOS belleği aşılırsa uygulama kapanabilir.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(10.dp))
            NuvioInputField(
                value = concurrencyText,
                onValueChange = { raw ->
                    val digits = raw.filter { it.isDigit() }
                    concurrencyText = digits
                    digits.toIntOrNull()?.let(PluginRepository::setMaxConcurrentScrapers)
                },
                placeholder = "4",
            )
        }

        NuvioSectionLabel(stringResource(Res.string.plugins_section_add_repo))''',
    'plugin settings concurrency UI',
)

streams_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/streams/StreamsRepository.kt'
streams = streams_path.read_text(encoding='utf-8')
if 'import kotlinx.coroutines.sync.Semaphore' not in streams:
    anchor = 'import kotlinx.coroutines.launch\n'
    if anchor not in streams:
        raise SystemExit('Could not locate StreamsRepository coroutine import anchor')
    streams = streams.replace(
        anchor,
        anchor + 'import kotlinx.coroutines.sync.Semaphore\nimport kotlinx.coroutines.sync.withPermit\n',
        1,
    )

provider_anchor = '''        val pluginProviderGroups = pluginScrapers.toPluginProviderGroups(
            repositories = pluginUiState.repositories,
            groupByRepository = pluginUiState.groupStreamsByRepository,
        )'''
provider_replacement = provider_anchor + '''
        val pluginExecutionSemaphore = pluginUiState.maxConcurrentScrapers
            .takeIf { it > 0 }
            ?.let(::Semaphore)'''
if 'val pluginExecutionSemaphore = pluginUiState.maxConcurrentScrapers' not in streams:
    if provider_anchor not in streams:
        raise SystemExit('Could not locate pluginProviderGroups block')
    streams = streams.replace(provider_anchor, provider_replacement, 1)

old_plugin_execute = '''                        val completion = PluginRepository.executeScraper(
                            scraper = scraper,
                            tmdbId = pluginContentId(
                                videoId = videoId,
                                season = season,
                                episode = episode,
                            ),
                            mediaType = type,
                            season = season,
                            episode = episode,
                        ).fold('''
new_plugin_execute = '''                        suspend fun executeCurrentScraper() = PluginRepository.executeScraper(
                            scraper = scraper,
                            tmdbId = pluginContentId(
                                videoId = videoId,
                                season = season,
                                episode = episode,
                            ),
                            mediaType = type,
                            season = season,
                            episode = episode,
                        )
                        val scraperResult = if (pluginExecutionSemaphore == null) {
                            executeCurrentScraper()
                        } else {
                            pluginExecutionSemaphore.withPermit { executeCurrentScraper() }
                        }
                        val completion = scraperResult.fold('''
if new_plugin_execute not in streams:
    if old_plugin_execute not in streams:
        raise SystemExit('Could not locate plugin scraper execution block')
    streams = streams.replace(old_plugin_execute, new_plugin_execute, 1)
streams_path.write_text(streams, encoding='utf-8')


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
full_plugins_page = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/settings/PluginsSettingsPage.kt'
p2p_file = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/p2p/P2pStreamingEngine.ios.kt'
full_plugin_runtime = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/plugins/runtime/PluginRuntime.kt'

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
if 'maxConcurrentScrapers: Int = 4' not in models_path.read_text(encoding='utf-8'):
    raise SystemExit('Configurable plugin concurrency model was not installed')
if 'setMaxConcurrentScrapers' not in full_repo_path.read_text(encoding='utf-8'):
    raise SystemExit('Configurable plugin concurrency repository setter was not installed')
if '0 = sınırsız' not in plugins_screen_path.read_text(encoding='utf-8'):
    raise SystemExit('Configurable plugin concurrency UI was not installed')
patched_streams = streams_path.read_text(encoding='utf-8')
if 'pluginUiState.maxConcurrentScrapers' not in patched_streams or 'withPermit' not in patched_streams:
    raise SystemExit('Dynamic plugin concurrency limiter was not installed')
if 'executionSemaphore = Semaphore(4)' in full_plugin_runtime.read_text(encoding='utf-8'):
    raise SystemExit('Old fixed QuickJS concurrency limiter is still present')

print('Applied real iOS Full + Auto Trailer V2 + P2P with user-configurable plugin concurrency (0 = unlimited).')
