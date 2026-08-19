from pathlib import Path
import re

root = Path('.')


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'Could not locate {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


# ---------------------------------------------------------------------------
# 1) Carry playback request headers with the resolved trailer source.
# ---------------------------------------------------------------------------
source_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/trailer/TrailerPlaybackSource.kt'
replace_once(
    source_path,
    '''data class TrailerPlaybackSource(
    val videoUrl: String,
    val audioUrl: String? = null,
)''',
    '''data class TrailerPlaybackSource(
    val videoUrl: String,
    val audioUrl: String? = null,
    val headers: Map<String, String> = emptyMap(),
)''',
    'TrailerPlaybackSource headers',
)


# ---------------------------------------------------------------------------
# 2) Harden the Kotlin YouTube extractor.
# ---------------------------------------------------------------------------
extractor_path = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/trailer/InAppYouTubeExtractor.kt'
extractor = extractor_path.read_text(encoding='utf-8')

extractor = extractor.replace(
    'private const val PREFERRED_SEPARATE_CLIENT = "android_vr"',
    'private const val PREFERRED_SEPARATE_CLIENT = "mweb"',
)

mweb_block = '''    YouTubeClient(
        key = "mweb",
        id = "2",
        version = "2.20260708.05.00",
        userAgent = "Mozilla/5.0 (iPad; CPU OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 " +
            "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1,gzip(gfe)",
        context = jsonObjectOf(
            "clientName" to "MWEB",
            "clientVersion" to "2.20260708.05.00",
            "userAgent" to "Mozilla/5.0 (iPad; CPU OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1,gzip(gfe)",
            "platform" to "MOBILE",
            "hl" to "en",
            "gl" to "US",
        ),
        priority = -10,
    ),
'''
clients_anchor = 'private val CLIENTS = listOf(\n'
if 'key = "mweb"' not in extractor:
    if clients_anchor not in extractor:
        raise SystemExit('Could not locate YouTube clients list')
    extractor = extractor.replace(clients_anchor, clients_anchor + mweb_block, 1)

# Refresh the secondary Android/iOS client metadata.
extractor = extractor.replace('version = "20.10.35"', 'version = "21.26.364"')
extractor = extractor.replace(
    'userAgent = "com.google.android.youtube/20.10.35 (Linux; U; Android 14; en_US) gzip"',
    'userAgent = "com.google.android.youtube/21.26.364 (Linux; U; Android 11) gzip"',
)
extractor = extractor.replace('"clientVersion" to "20.10.35"', '"clientVersion" to "21.26.364"')
extractor = extractor.replace('"osVersion" to "14"', '"osVersion" to "11"')
extractor = extractor.replace('"androidSdkVersion" to 34', '"androidSdkVersion" to 30')

extractor = extractor.replace('version = "20.10.1"', 'version = "21.26.4"')
extractor = extractor.replace(
    'userAgent = "com.google.ios.youtube/20.10.1 (iPhone16,2; U; CPU iOS 17_4 like Mac OS X)"',
    'userAgent = "com.google.ios.youtube/21.26.4 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)"',
)
extractor = extractor.replace('"clientVersion" to "20.10.1"', '"clientVersion" to "21.26.4"')
extractor = extractor.replace('"osVersion" to "17.4.0.21E219"', '"osVersion" to "18.3.2.22D82"')

old_sort = '''        return items.sortedWith(
            compareByDescending<StreamCandidate> { it.score }
                .thenBy { if (it.hasN) 1 else 0 }
                .thenBy { containerPreference(it.ext) }
                .thenBy { it.priority },
        )'''
new_sort = '''        return items.sortedWith(
            compareBy<StreamCandidate> { if (it.hasN) 1 else 0 }
                .thenByDescending { it.score }
                .thenBy { containerPreference(it.ext) }
                .thenBy { it.priority },
        )'''
if new_sort not in extractor:
    if old_sort not in extractor:
        raise SystemExit('Could not locate candidate sorting block')
    extractor = extractor.replace(old_sort, new_sort, 1)

old_manifest_choice = '''                if (
                    bestManifest == null ||
                    candidate.height > bestManifest.height ||
                    (candidate.height == bestManifest.height && candidate.bandwidth > bestManifest.bandwidth)
                ) {
                    bestManifest = candidate
                }'''
new_manifest_choice = '''                if (
                    bestManifest == null ||
                    candidate.priority < bestManifest.priority ||
                    (
                        candidate.priority == bestManifest.priority &&
                            candidate.height > bestManifest.height
                    ) ||
                    (
                        candidate.priority == bestManifest.priority &&
                            candidate.height == bestManifest.height &&
                            candidate.bandwidth > bestManifest.bandwidth
                    )
                ) {
                    bestManifest = candidate
                }'''
if new_manifest_choice not in extractor:
    if old_manifest_choice not in extractor:
        raise SystemExit('Could not locate manifest selection block')
    extractor = extractor.replace(old_manifest_choice, new_manifest_choice, 1)

extractor_path.write_text(extractor, encoding='utf-8')


# ---------------------------------------------------------------------------
# 3) iOS resolver: MWEB-style request headers + HLS first. Reject a URL that
#    has just been proven to return 403 before handing it to MPV.
# ---------------------------------------------------------------------------
platform_path = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/trailer/TrailerExtractionPlatform.ios.kt'
platform = platform_path.read_text(encoding='utf-8')

old_default_headers = '''    val defaultHeaders: Map<String, String> = mapOf(
        "accept-language" to "en-US,en;q=0.9",
        "user-agent" to
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 " +
            "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    )'''
new_default_headers = '''    val defaultHeaders: Map<String, String> = mapOf(
        "accept-language" to "en-US,en;q=0.9",
        "referer" to "https://www.youtube.com/",
        "origin" to "https://www.youtube.com",
        "user-agent" to
            "Mozilla/5.0 (iPad; CPU OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 " +
            "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1,gzip(gfe)",
    )'''
if new_default_headers not in platform:
    if old_default_headers not in platform:
        raise SystemExit('Could not locate iOS trailer default headers')
    platform = platform.replace(old_default_headers, new_default_headers, 1)

build_to_gethost_pattern = re.compile(
    r'''    suspend fun buildPlaybackSource\(\n.*?\n    private fun getHost\(url: String\): String\? \{''',
    re.DOTALL,
)
new_build = '''    private val youtubePlaybackHeaders: Map<String, String> = mapOf(
        "User-Agent" to "Mozilla/5.0 (iPad; CPU OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1,gzip(gfe)",
        "Referer" to "https://www.youtube.com/",
        "Origin" to "https://www.youtube.com",
        "Accept-Language" to "en-US,en;q=0.9",
    )

    suspend fun buildPlaybackSource(
        bestManifest: ManifestCandidate?,
        bestProgressive: StreamCandidate?,
        bestVideo: StreamCandidate?,
        bestAudio: StreamCandidate?,
    ): TrailerPlaybackSource? = withContext(Dispatchers.Default) {
        bestManifest?.manifestUrl?.let { manifestUrl ->
            resolveReachableUrl(manifestUrl, youtubePlaybackHeaders)?.let { reachable ->
                return@withContext TrailerPlaybackSource(
                    videoUrl = reachable,
                    headers = youtubePlaybackHeaders,
                )
            }
        }

        bestProgressive?.url?.let { progressiveUrl ->
            resolveReachableUrl(progressiveUrl, youtubePlaybackHeaders)?.let { reachable ->
                return@withContext TrailerPlaybackSource(
                    videoUrl = reachable,
                    headers = youtubePlaybackHeaders,
                )
            }
        }

        val videoUrl = bestVideo?.url?.let {
            resolveReachableUrl(it, youtubePlaybackHeaders)
        }
        if (videoUrl != null) {
            val audioUrl = bestAudio?.url?.let {
                resolveReachableUrl(it, youtubePlaybackHeaders)
            }
            if (bestAudio == null || audioUrl != null) {
                return@withContext TrailerPlaybackSource(
                    videoUrl = videoUrl,
                    audioUrl = audioUrl,
                    headers = youtubePlaybackHeaders,
                )
            }
        }

        null
    }

    private suspend fun resolveReachableUrl(
        url: String,
        headers: Map<String, String>,
    ): String? {
        if (isUrlReachable(url, headers)) return url
        if (!url.contains("googlevideo.com")) return null

        val mnParam = getQueryParameter(url, "mn") ?: return null
        val servers = mnParam.split(',').map { it.trim() }.filter { it.isNotBlank() }
        if (servers.isEmpty()) return null

        val host = getHost(url) ?: return null
        val candidates = servers.mapIndexedNotNull { index, server ->
            val altHost = host
                .replaceFirst(Regex("^rr\\\\d+---"), "rr${index + 1}---")
                .replaceFirst(Regex("sn-[a-z0-9]+-[a-z0-9]+"), server)
            if (altHost != host) url.replace(host, altHost) else null
        }.distinct()

        if (candidates.isEmpty()) return null

        return coroutineScope {
            val probes = candidates.map { candidate ->
                async {
                    if (isUrlReachable(candidate, headers)) candidate else null
                }
            }
            withTimeoutOrNull(5_000L) {
                probes.awaitAll().firstOrNull { !it.isNullOrBlank() }
            }
        }
    }

    private suspend fun isUrlReachable(
        url: String,
        headers: Map<String, String>,
    ): Boolean {
        val response = runCatching {
            performRequest(
                url = url,
                method = "GET",
                headers = buildMap {
                    putAll(headers)
                    put("Range", "bytes=0-0")
                },
                body = null,
                timeoutMillis = 5_000L,
            )
        }.getOrNull() ?: return false

        return response.status in 200..299
    }

    private fun getHost(url: String): String? {'''

if 'private val youtubePlaybackHeaders' not in platform:
    platform, count = build_to_gethost_pattern.subn(lambda _match: new_build, platform, count=1)
    if count != 1:
        raise SystemExit('Could not patch iOS trailer playback source selection')
platform_path.write_text(platform, encoding='utf-8')


# ---------------------------------------------------------------------------
# 4) Pass resolver headers into the normal trailer MPV surface.
# ---------------------------------------------------------------------------
popup_path = root / 'composeApp/src/commonMain/kotlin/com/nuvio/app/features/details/components/TrailerPlayerPopup.kt'
replace_once(
    popup_path,
    '''                            sourceUrl = playbackSource.videoUrl,
                            sourceAudioUrl = playbackSource.audioUrl,
                            useYoutubeChunkedPlayback = true,''',
    '''                            sourceUrl = playbackSource.videoUrl,
                            sourceAudioUrl = playbackSource.audioUrl,
                            sourceHeaders = playbackSource.headers,
                            useYoutubeChunkedPlayback = true,''',
    'trailer popup playback headers',
)


# ---------------------------------------------------------------------------
# 5) The custom hero surface talks directly to the iOS MPV bridge.
# ---------------------------------------------------------------------------
hero_path = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/details/components/HeroTrailerPlayerSurface.ios.kt'
hero = hero_path.read_text(encoding='utf-8')
old_headers = '            headersJson = null,\n'
new_headers = '''            headersJson = """{"User-Agent":"Mozilla/5.0 (iPad; CPU OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1,gzip(gfe)","Referer":"https://www.youtube.com/","Origin":"https://www.youtube.com","Accept-Language":"en-US,en;q=0.9"}""",
'''
if new_headers not in hero:
    if old_headers not in hero:
        raise SystemExit('Could not locate hero MPV headersJson')
    hero = hero.replace(old_headers, new_headers, 1)
hero_path.write_text(hero, encoding='utf-8')


# ---------------------------------------------------------------------------
# Sanity checks: also reject accidental literal \" sequences outside JSON
# strings, which caused the first V3 patch to fail.
# ---------------------------------------------------------------------------
checks = {
    extractor_path: [
        'key = "mweb"',
        'PREFERRED_SEPARATE_CLIENT = "mweb"',
        'compareBy<StreamCandidate> { if (it.hasN) 1 else 0 }',
        'candidate.priority < bestManifest.priority',
    ],
    platform_path: [
        'private val youtubePlaybackHeaders',
        'return response.status in 200..299',
        'Regex("^rr\\\\d+---")',
    ],
    popup_path: ['sourceHeaders = playbackSource.headers'],
    source_path: ['val headers: Map<String, String> = emptyMap()'],
    hero_path: ['"Referer":"https://www.youtube.com/"'],
}
for path, markers in checks.items():
    text = path.read_text(encoding='utf-8')
    for marker in markers:
        if marker not in text:
            raise SystemExit(f'Trailer V3 verification failed: {marker} missing from {path}')

print('Applied Kotlin YouTube Trailer V3: MWEB-first, HLS-first, reachability probes, MPV headers.')
