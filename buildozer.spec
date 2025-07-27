[app]
title = My Activity Logger
package.name = myactivitylogger
package.domain = com.alamin
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.1
requirements = python3,kivy,kivymd,google-generativeai,pillow
orientation = portrait
fullscreen = 0

# --- Android Permissions ---
# Internet for AI, and special permission for usage stats
android.permissions = android.permission.INTERNET, android.permission.PACKAGE_USAGE_STATS

# --- Android API Levels ---
android.api = 31
android.minapi = 21
android.sdk = 24
android.ndk = 25b

# --- Architecture to build for ---
android.archs = arm64-v8a, armeabi-v7a

# (bool) Enable AndroidX support
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1

