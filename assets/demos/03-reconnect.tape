# VHS tape — wireless ADB auto-reconnect demo
# Render with: vhs assets/demos/03-reconnect.tape

Output assets/demos/03-reconnect.gif
Set FontSize 18
Set Width 1200
Set Height 600
Set TypingSpeed 40ms
Set Theme "Catppuccin Mocha"

# ── prologue ──────────────────────────────────────────────────────────
Type "# Wireless ADB port has rotated — find it again"
Enter
Sleep 1.5s

# ── status: device offline ─────────────────────────────────────────────
Type "adb devices"
Enter
Sleep 1.5s

# ── scan for adb port ──────────────────────────────────────────────────
Type "adb-control scan-port 192.0.2.42 --start 30000 --end 45000"
Enter
Sleep 4s

# ── reconnect ──────────────────────────────────────────────────────────
Type "adb connect 192.0.2.42:42891"
Enter
Sleep 1.5s

Type "adb-control devices"
Enter
Sleep 1.5s

Type "# back online ✓"
Enter
Sleep 2s
