# VHS tape — quickstart demo
# Render with: vhs assets/demos/01-quickstart.tape
# https://github.com/charmbracelet/vhs

Output assets/demos/01-quickstart.gif
Set FontSize 18
Set Width 1200
Set Height 600
Set TypingSpeed 40ms
Set Theme "Catppuccin Mocha"
Set PlaybackSpeed 1.5

# ── prologue ──────────────────────────────────────────────────────────
Type "# adb-android-control — 30-second tour"
Enter
Sleep 1.5s

# ── version + connected device ─────────────────────────────────────────
Type "adb-control --version"
Enter
Sleep 800ms
Type "adb-control devices"
Enter
Sleep 1.5s

# ── one-shot device snapshot ──────────────────────────────────────────
Type "adb-control info"
Enter
Sleep 2.5s

# ── screenshot ─────────────────────────────────────────────────────────
Type "adb-control shot ~/demo-shot.png"
Enter
Sleep 1.5s

# ── workflow ──────────────────────────────────────────────────────────
Type "adb-control workflow ./examples/launch-and-screenshot.json"
Enter
Sleep 3s

# ── radio status ──────────────────────────────────────────────────────
Type "adb-control radio wifi bluetooth"
Enter
Sleep 2.5s

# ── epilogue ──────────────────────────────────────────────────────────
Type "# 273 tests · 1.76:1 ratio · MIT"
Enter
Sleep 2s
