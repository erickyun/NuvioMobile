from pathlib import Path
import shutil

root = Path('.')

appstore_plugins = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/features/plugins'
full_plugins = root / 'composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/plugins'
ios_full_plugins = root / 'composeApp/src/iosFull/kotlin/com/nuvio/app/features/plugins'

appstore_plugins.mkdir(parents=True, exist_ok=True)

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

# Expose the Plugins UI in this custom App Store-based build.
policy_path = root / 'composeApp/src/iosAppStore/kotlin/com/nuvio/app/core/build/AppFeaturePolicy.ios.kt'
policy = policy_path.read_text(encoding='utf-8')
old_policy = 'actual val pluginsEnabled: Boolean = false'
new_policy = 'actual val pluginsEnabled: Boolean = true'
if old_policy not in policy and new_policy not in policy:
    raise SystemExit('Could not locate pluginsEnabled policy')
policy_path.write_text(policy.replace(old_policy, new_policy, 1), encoding='utf-8')

# The plugin runtime needs QuickJS and Ksoup. Normally these dependencies are
# only wired when NUVIO_IOS_DISTRIBUTION=full, which also requires Nuvio Engine.
# For this custom build, add only the plugin runtime dependencies while keeping
# NUVIO_IOS_DISTRIBUTION=appstore so no P2P/Nuvio Engine XCFramework is needed.
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
if old_deps not in gradle and new_deps not in gradle:
    raise SystemExit('Could not locate iOS dependency block for QuickJS/Ksoup')
gradle_path.write_text(gradle.replace(old_deps, new_deps, 1), encoding='utf-8')

# Sanity checks: real repository/runtime/platform must exist, disabled stub must not.
checks = [
    appstore_plugins / 'PluginRepository.kt',
    appstore_plugins / 'PluginManifestParser.kt',
    appstore_plugins / 'runtime/PluginRuntime.kt',
    appstore_plugins / 'runtime/js/JsRuntime.kt',
    appstore_plugins / 'runtime/dom/DomBridge.kt',
    appstore_plugins / 'PluginPlatform.ios.kt',
    appstore_plugins / 'PluginCrypto.ios.kt',
]
for check in checks:
    if not check.is_file():
        raise SystemExit(f'Missing patched plugin file: {check}')
if disabled_repo.exists():
    raise SystemExit('Disabled App Store PluginRepository stub still exists')
if 'actual val pluginsEnabled: Boolean = true' not in policy_path.read_text(encoding='utf-8'):
    raise SystemExit('Plugin feature policy was not enabled')
patched_gradle = gradle_path.read_text(encoding='utf-8')
if 'implementation(libs.quickjs.kt)' not in patched_gradle or 'implementation(libs.ksoup)' not in patched_gradle:
    raise SystemExit('Plugin runtime dependencies were not enabled')

print('Applied real iOS plugin runtime to App Store-based custom build without Nuvio Engine/P2P.')
