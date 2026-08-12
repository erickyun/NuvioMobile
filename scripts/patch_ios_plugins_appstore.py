from pathlib import Path
import shutil

root = Path('.')

appstore_plugins = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/features/plugins'
full_plugins = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/plugins'
ios_full_plugins = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/plugins'
appstore_settings = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/features/settings'
full_settings_page = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/settings/PluginsSettingsPage.kt'

appstore_plugins.mkdir(parents=True, exist_ok=True)
appstore_settings.mkdir(parents=True, exist_ok=True)

# Remove the App Store disabled PluginRepository implementation before copying
# the real Full implementation into the App Store source set.
disabled_repo = appstore_plugins / 'PluginRepository.ios.kt'
if disabled_repo.exists():
    disabled_repo.unlink()

# Copy the complete real plugin implementation/runtime/UI into the App Store
# iOS source set without enabling the full/P2P distribution.
for source in full_plugins.rglob('*'):
    if source.is_dir():
        continue
    relative = source.relative_to(full_plugins)
    target = appstore_plugins / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

# iOS-specific storage and crypto implementations used by the Full plugin runtime.
for name in ('PluginPlatform.ios.kt', 'PluginCrypto.ios.kt'):
    source = ios_full_plugins / name
    if not source.is_file():
        raise SystemExit(f'Missing iOS Full plugin platform file: {source}')
    shutil.copy2(source, appstore_plugins / name)

# IMPORTANT: App Store iOS intentionally ships an empty actual implementation:
#   actual fun LazyListScope.pluginsSettingsContent() = Unit
# Replace that stub with the real Full settings-page actual, otherwise the
# Plugins page shows only its header and a blank body.
if not full_settings_page.is_file():
    raise SystemExit(f'Missing Full plugin settings page: {full_settings_page}')
shutil.copy2(full_settings_page, appstore_settings / 'PluginsSettingsPage.kt')

# Expose Plugins in this custom App Store-based build. P2P remains disabled by
# the rest of the App Store policy; we deliberately do NOT switch distribution.
policy_path = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/core/build/AppFeaturePolicy.ios.kt'
policy = policy_path.read_text(encoding='utf-8')
old_policy = 'actual val pluginsEnabled: Boolean = false'
new_policy = 'actual val pluginsEnabled: Boolean = true'
if old_policy not in policy and new_policy not in policy:
    raise SystemExit('Could not locate pluginsEnabled policy')
policy_path.write_text(policy.replace(old_policy, new_policy, 1), encoding='utf-8')

# The Full plugin runtime needs QuickJS + Ksoup. The upstream Gradle file only
# wires those dependencies for iosDistribution=full. Add them to this custom
# App Store build without enabling the Nuvio Engine cinterop/P2P path.
gradle_path = root / 'composeApp/build.gradle.kts'
gradle = gradle_path.read_text(encoding='utf-8')
old_deps = '''            defaultSourceSet.dependencies {
                implementation(libs.ktor.client.darwin)
                if (iosDistribution == "full") {
                    implementation(libs.quickjs.kt)
                    implementation(libs.ksoup)
                }
            }'''
new_deps = '''            defaultSourceSet.dependencies {
                implementation(libs.ktor.client.darwin)
                implementation(libs.quickjs.kt)
                implementation(libs.ksoup)
            }'''
if old_deps in gradle:
    gradle = gradle.replace(old_deps, new_deps, 1)
elif new_deps not in gradle:
    raise SystemExit('Could not locate iOS dependency block for QuickJS/Ksoup')

# Full iOS also links the native C++/Apple system frameworks used by its native
# runtime. Keep these linker options for the custom plugin build as well. This
# is independent of Nuvio Engine and avoids a partially wired QuickJS/native
# runtime in the App Store-based build.
old_linker = '''            if (iosDistribution == "full") {
                linkerOpts(
                    "-lc++",
                    "-framework", "Security",
                    "-framework", "SystemConfiguration",
                    "-framework", "CoreFoundation",
                )
            }'''
new_linker = '''            linkerOpts(
                "-lc++",
                "-framework", "Security",
                "-framework", "SystemConfiguration",
                "-framework", "CoreFoundation",
            )'''
if old_linker in gradle:
    gradle = gradle.replace(old_linker, new_linker, 1)
elif new_linker not in gradle:
    raise SystemExit('Could not locate iOS framework linker block')

gradle_path.write_text(gradle, encoding='utf-8')

# Sanity checks: real repository/runtime/platform/settings must exist, disabled
# App Store stubs must not remain, and P2P must stay disabled.
settings_page = appstore_settings / 'PluginsSettingsPage.kt'
checks = [
    appstore_plugins / 'PluginRepository.kt',
    appstore_plugins / 'PluginManifestParser.kt',
    appstore_plugins / 'PluginsSettingsScreen.kt',
    appstore_plugins / 'runtime/PluginRuntime.kt',
    appstore_plugins / 'runtime/js/JsRuntime.kt',
    appstore_plugins / 'runtime/dom/DomBridge.kt',
    appstore_plugins / 'PluginPlatform.ios.kt',
    appstore_plugins / 'PluginCrypto.ios.kt',
    settings_page,
]
for check in checks:
    if not check.is_file():
        raise SystemExit(f'Missing patched plugin file: {check}')
if disabled_repo.exists():
    raise SystemExit('Disabled App Store PluginRepository stub still exists')
if 'PluginsSettingsPageContent' not in settings_page.read_text(encoding='utf-8'):
    raise SystemExit('Real Plugins settings UI was not installed')
patched_policy = policy_path.read_text(encoding='utf-8')
if 'actual val pluginsEnabled: Boolean = true' not in patched_policy:
    raise SystemExit('Plugin feature policy was not enabled')
if 'actual val p2pEnabled: Boolean = false' not in patched_policy:
    raise SystemExit('P2P unexpectedly enabled in plugin-only build')
patched_gradle = gradle_path.read_text(encoding='utf-8')
if 'implementation(libs.quickjs.kt)' not in patched_gradle or 'implementation(libs.ksoup)' not in patched_gradle:
    raise SystemExit('Plugin runtime dependencies were not enabled')
if '"-lc++"' not in patched_gradle or '"Security"' not in patched_gradle:
    raise SystemExit('Native plugin linker options were not enabled')

print('Applied real iOS plugin UI/runtime to App Store-based build; P2P remains disabled.')
