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
# 1) Persist trailer quality alongside the existing Meta Screen settings.
# ---------------------------------------------------------------------------
repo_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/details/MetaScreenSettingsRepository.kt'

replace_once(
    repo_path,
    '''    val heroTrailerPlayback: Boolean = false,
    val tabLayout: Boolean = false,''',
    '''    val heroTrailerPlayback: Boolean = false,
    val trailerQuality: TrailerQuality = TrailerQuality.Auto,
    val tabLayout: Boolean = false,''',
    'MetaScreenSettingsUiState trailer quality',
)

replace_once(
    repo_path,
    '''enum class MetaEpisodeCardStyle {''',
    '''enum class TrailerQuality(
    val persistedValue: String,
    val label: String,
    val maxHeight: Int?,
) {
    Auto("auto", "Auto", null),
    Highest("highest", "Highest", null),
    P1080("1080p", "1080p", 1080),
    P720("720p", "720p", 720),
    P480("480p", "480p", 480),
    P360("360p", "360p", 360),
    ;

    companion object {
        fun parse(raw: String?): TrailerQuality =
            entries.firstOrNull { it.persistedValue.equals(raw, ignoreCase = true) } ?: Auto
    }
}

enum class MetaEpisodeCardStyle {''',
    'TrailerQuality enum',
)

replace_once(
    repo_path,
    '''    @SerialName("hero_trailer_playback")
    val heroTrailerPlayback: Boolean = false,
    @SerialName("tvStyleLayout")''',
    '''    @SerialName("hero_trailer_playback")
    val heroTrailerPlayback: Boolean = false,
    @SerialName("trailer_quality")
    val trailerQuality: String = "auto",
    @SerialName("tvStyleLayout")''',
    'stored trailer quality',
)

replace_once(
    repo_path,
    '''    private var heroTrailerPlayback: Boolean = false
    private var tabLayout: Boolean = false''',
    '''    private var heroTrailerPlayback: Boolean = false
    private var trailerQuality: TrailerQuality = TrailerQuality.Auto
    private var tabLayout: Boolean = false''',
    'trailer quality repository field',
)

replace_once(
    repo_path,
    '''                heroTrailerPlayback = parsed.heroTrailerPlayback
                tabLayout = parsed.tabLayout''',
    '''                heroTrailerPlayback = parsed.heroTrailerPlayback
                trailerQuality = TrailerQuality.parse(parsed.trailerQuality)
                tabLayout = parsed.tabLayout''',
    'trailer quality load',
)

# There are three default-reset blocks: onProfileChanged, clearLocalState and
# resetToDefaults. Update all of them without relying on line numbers.
text = repo_path.read_text(encoding='utf-8')
old_reset = '''        heroTrailerPlayback = false
        tabLayout = false'''
new_reset = '''        heroTrailerPlayback = false
        trailerQuality = TrailerQuality.Auto
        tabLayout = false'''
if new_reset not in text:
    count = text.count(old_reset)
    if count < 3:
        raise SystemExit(f'Expected at least 3 trailer reset blocks, found {count}')
    text = text.replace(old_reset, new_reset)
    repo_path.write_text(text, encoding='utf-8')

replace_once(
    repo_path,
    '''    fun setHeroTrailerPlayback(enabled: Boolean) {
        ensureLoaded()
        heroTrailerPlayback = enabled
        publish()
        persist()
    }

    fun setTabLayout''',
    '''    fun setHeroTrailerPlayback(enabled: Boolean) {
        ensureLoaded()
        heroTrailerPlayback = enabled
        publish()
        persist()
    }

    fun setTrailerQuality(quality: TrailerQuality) {
        ensureLoaded()
        trailerQuality = quality
        publish()
        persist()
    }

    fun setTabLayout''',
    'trailer quality setter',
)

replace_once(
    repo_path,
    '''            heroTrailerPlayback = heroTrailerPlayback,
            tabLayout = tabLayout,''',
    '''            heroTrailerPlayback = heroTrailerPlayback,
            trailerQuality = trailerQuality,
            tabLayout = tabLayout,''',
    'trailer quality publish',
)

replace_once(
    repo_path,
    '''                    heroTrailerPlayback = heroTrailerPlayback,
                    tabLayout = tabLayout,''',
    '''                    heroTrailerPlayback = heroTrailerPlayback,
                    trailerQuality = trailerQuality.persistedValue,
                    tabLayout = tabLayout,''',
    'trailer quality persistence',
)


# ---------------------------------------------------------------------------
# 2) Add a quality selector directly below the existing Hero Trailer switch.
# ---------------------------------------------------------------------------
settings_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/settings/MetaScreenSettingsPage.kt'
settings = settings_path.read_text(encoding='utf-8')

if 'import com.nuvio.app.features.details.TrailerQuality' not in settings:
    anchor = 'import com.nuvio.app.features.details.MetaScreenSettingsUiState\n'
    if anchor not in settings:
        raise SystemExit('Could not locate MetaScreen settings import anchor')
    settings = settings.replace(
        anchor,
        anchor + 'import com.nuvio.app.features.details.TrailerQuality\n',
        1,
    )

old_hero_block = '''                    SettingsSwitchRow(
                        title = stringResource(Res.string.settings_meta_hero_trailer_playback),
                        description = stringResource(Res.string.settings_meta_hero_trailer_playback_description),
                        checked = uiState.heroTrailerPlayback,
                        isTablet = isTablet,
                        onCheckedChange = { MetaScreenSettingsRepository.setHeroTrailerPlayback(it) },
                    )'''
new_hero_block = old_hero_block + '''
                    SettingsGroupDivider(isTablet = isTablet)
                    TrailerQualitySelector(
                        isTablet = isTablet,
                        selectedQuality = uiState.trailerQuality,
                        onQualitySelected = MetaScreenSettingsRepository::setTrailerQuality,
                    )'''
if 'TrailerQualitySelector(' not in settings:
    if old_hero_block not in settings:
        raise SystemExit('Could not locate Hero Trailer settings block')
    settings = settings.replace(old_hero_block, new_hero_block, 1)

selector_anchor = '''@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MetaBackgroundModeSelector('''
selector = '''@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TrailerQualitySelector(
    isTablet: Boolean,
    selectedQuality: TrailerQuality,
    onQualitySelected: (TrailerQuality) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = if (isTablet) 20.dp else 16.dp,
                vertical = if (isTablet) 18.dp else 14.dp,
            ),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                text = "Trailer quality",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.Medium,
            )
            Text(
                text = "Used by both Hero trailers and the normal Trailer player. Auto keeps adaptive HLS playback.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            TrailerQuality.entries.forEach { quality ->
                FilterChip(
                    selected = selectedQuality == quality,
                    onClick = { onQualitySelected(quality) },
                    label = {
                        Text(
                            text = if (quality == TrailerQuality.Auto) "Auto (Recommended)" else quality.label,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    border = FilterChipDefaults.filterChipBorder(
                        enabled = true,
                        selected = selectedQuality == quality,
                        borderColor = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f),
                        selectedBorderColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.7f),
                    ),
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f),
                        selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    ),
                )
            }
        }
        Text(
            text = when (selectedQuality) {
                TrailerQuality.Auto -> "Adaptive quality selected automatically by the player."
                TrailerQuality.Highest -> "Always use the highest quality offered by the trailer."
                else -> "Use ${selectedQuality.label} when available; otherwise use the nearest lower quality."
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MetaBackgroundModeSelector('''
if 'private fun TrailerQualitySelector(' not in settings:
    if selector_anchor not in settings:
        raise SystemExit('Could not locate MetaBackgroundModeSelector anchor')
    settings = settings.replace(selector_anchor, selector, 1)

settings_path.write_text(settings, encoding='utf-8')


# ---------------------------------------------------------------------------
# 3) Make the Kotlin YouTube extractor honor the setting.
#    Auto     -> pass the HLS master URL to MPV (adaptive).
#    Highest  -> resolve and pass the highest HLS variant.
#    1080/etc -> highest variant <= requested height; if none exists, use the
#                lowest available variant rather than failing playback.
# ---------------------------------------------------------------------------
extractor_path = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/trailer/InAppYouTubeExtractor.kt'
extractor = extractor_path.read_text(encoding='utf-8')

if 'import com.nuvio.app.features.details.MetaScreenSettingsRepository' not in extractor:
    package_anchor = 'package com.nuvio.app.features.trailer\n\n'
    if package_anchor not in extractor:
        raise SystemExit('Could not locate extractor package anchor')
    extractor = extractor.replace(
        package_anchor,
        package_anchor +
        'import com.nuvio.app.features.details.MetaScreenSettingsRepository\n' +
        'import com.nuvio.app.features.details.TrailerQuality\n',
        1,
    )

video_id_anchor = '''        val videoId = extractVideoId(youtubeUrl) ?: return null

        val watchUrl ='''
video_id_replacement = '''        val videoId = extractVideoId(youtubeUrl) ?: return null
        MetaScreenSettingsRepository.ensureLoaded()
        val trailerQuality = MetaScreenSettingsRepository.uiState.value.trailerQuality

        val watchUrl ='''
if 'val trailerQuality = MetaScreenSettingsRepository.uiState.value.trailerQuality' not in extractor:
    if video_id_anchor not in extractor:
        raise SystemExit('Could not locate extractor videoId anchor')
    extractor = extractor.replace(video_id_anchor, video_id_replacement, 1)

extractor = extractor.replace(
    'val variant = parseHlsManifest(manifestUrl) ?: return@runCatching',
    'val variant = parseHlsManifest(manifestUrl, trailerQuality.maxHeight) ?: return@runCatching',
    1,
)

old_candidate = '''                    manifestUrl = manifestUrl,
                    selectedVariantUrl = variant.url,'''
new_candidate = '''                    manifestUrl = if (trailerQuality == TrailerQuality.Auto) manifestUrl else variant.url,
                    selectedVariantUrl = variant.url,'''
if new_candidate not in extractor:
    if old_candidate not in extractor:
        raise SystemExit('Could not locate manifest candidate URL block')
    extractor = extractor.replace(old_candidate, new_candidate, 1)

old_best = '''        val bestProgressive = sortCandidates(progressive).firstOrNull()
        val bestVideo = pickBestForClient(adaptiveVideo, PREFERRED_SEPARATE_CLIENT)
        val bestAudio = pickBestForClient(adaptiveAudio, PREFERRED_SEPARATE_CLIENT)'''
new_best = '''        val bestProgressive = pickCandidateForQuality(progressive, trailerQuality)
        val preferredVideo = adaptiveVideo.filter { it.client == PREFERRED_SEPARATE_CLIENT }
            .ifEmpty { adaptiveVideo }
        val bestVideo = pickCandidateForQuality(preferredVideo, trailerQuality)
        val bestAudio = pickBestForClient(adaptiveAudio, PREFERRED_SEPARATE_CLIENT)'''
if new_best not in extractor:
    if old_best not in extractor:
        raise SystemExit('Could not locate best stream selection block')
    extractor = extractor.replace(old_best, new_best, 1)

old_parse_signature = '    private suspend fun parseHlsManifest(manifestUrl: String): ManifestBestVariant? {'
new_parse_signature = '''    private suspend fun parseHlsManifest(
        manifestUrl: String,
        maxHeight: Int?,
    ): ManifestBestVariant? {'''
if new_parse_signature not in extractor:
    if old_parse_signature not in extractor:
        raise SystemExit('Could not locate parseHlsManifest signature')
    extractor = extractor.replace(old_parse_signature, new_parse_signature, 1)

old_best_var = '        var bestVariant: ManifestBestVariant? = null\n'
new_best_var = '''        var bestVariant: ManifestBestVariant? = null
        var lowestVariant: ManifestBestVariant? = null
'''
if 'var lowestVariant: ManifestBestVariant? = null' not in extractor:
    if old_best_var not in extractor:
        raise SystemExit('Could not locate bestVariant declaration')
    extractor = extractor.replace(old_best_var, new_best_var, 1)

old_variant_selection = '''            if (
                bestVariant == null ||
                candidate.height > bestVariant.height ||
                (candidate.height == bestVariant.height && candidate.bandwidth > bestVariant.bandwidth) ||
                (
                    candidate.height == bestVariant.height &&
                        candidate.bandwidth == bestVariant.bandwidth &&
                        candidate.width > bestVariant.width
                    )
            ) {
                bestVariant = candidate
            }
        }

        return bestVariant'''
new_variant_selection = '''            if (
                lowestVariant == null ||
                candidate.height < lowestVariant.height ||
                (candidate.height == lowestVariant.height && candidate.bandwidth < lowestVariant.bandwidth)
            ) {
                lowestVariant = candidate
            }

            val withinLimit = maxHeight == null || candidate.height <= maxHeight
            if (
                withinLimit && (
                    bestVariant == null ||
                    candidate.height > bestVariant.height ||
                    (candidate.height == bestVariant.height && candidate.bandwidth > bestVariant.bandwidth) ||
                    (
                        candidate.height == bestVariant.height &&
                            candidate.bandwidth == bestVariant.bandwidth &&
                            candidate.width > bestVariant.width
                    )
                )
            ) {
                bestVariant = candidate
            }
        }

        return bestVariant ?: lowestVariant'''
if 'return bestVariant ?: lowestVariant' not in extractor:
    if old_variant_selection not in extractor:
        raise SystemExit('Could not locate HLS variant selection block')
    extractor = extractor.replace(old_variant_selection, new_variant_selection, 1)

# Add a reusable quality-aware selector just before the existing client picker.
picker_anchor = '    private fun pickBestForClient('
quality_picker = '''    private fun pickCandidateForQuality(
        items: List<StreamCandidate>,
        quality: TrailerQuality,
    ): StreamCandidate? {
        val sorted = sortCandidates(items)
        if (sorted.isEmpty()) return null
        val maxHeight = quality.maxHeight ?: return sorted.firstOrNull()
        return sorted.firstOrNull { candidate ->
            candidate.height <= 0 || candidate.height <= maxHeight
        } ?: sorted.minByOrNull { candidate ->
            if (candidate.height <= 0) Int.MAX_VALUE else candidate.height
        }
    }

'''
if 'private fun pickCandidateForQuality(' not in extractor:
    if picker_anchor not in extractor:
        raise SystemExit('Could not locate pickBestForClient anchor')
    extractor = extractor.replace(picker_anchor, quality_picker + picker_anchor, 1)

extractor_path.write_text(extractor, encoding='utf-8')


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
checks = {
    repo_path: [
        'val trailerQuality: TrailerQuality = TrailerQuality.Auto',
        '@SerialName("trailer_quality")',
        'fun setTrailerQuality(quality: TrailerQuality)',
        'trailerQuality = trailerQuality.persistedValue',
    ],
    settings_path: [
        'private fun TrailerQualitySelector(',
        'Auto (Recommended)',
        'MetaScreenSettingsRepository::setTrailerQuality',
    ],
    extractor_path: [
        'val trailerQuality = MetaScreenSettingsRepository.uiState.value.trailerQuality',
        'parseHlsManifest(manifestUrl, trailerQuality.maxHeight)',
        'if (trailerQuality == TrailerQuality.Auto) manifestUrl else variant.url',
        'private fun pickCandidateForQuality(',
        'return bestVariant ?: lowestVariant',
    ],
}
for path, markers in checks.items():
    text = path.read_text(encoding='utf-8')
    for marker in markers:
        if marker not in text:
            raise SystemExit(f'Trailer quality verification failed: {marker} missing from {path}')

print('Added persistent Trailer Quality setting: Auto / Highest / 1080p / 720p / 480p / 360p.')
