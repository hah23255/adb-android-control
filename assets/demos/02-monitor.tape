# VHS tape — real-time monitor demo
# Render with: vhs assets/demos/02-monitor.tape

Output assets/demos/02-monitor.gif
Set FontSize 18
Set Width 1200
Set Height 600
Set TypingSpeed 40ms
Set Theme "Catppuccin Mocha"

# ── prologue ──────────────────────────────────────────────────────────
Type "# Real-time logcat with level filtering"
Enter
Sleep 1.5s

# ── start logcat at WARN+ ──────────────────────────────────────────────
Type "adb-control monitor logcat -l W"
Enter
Sleep 1s

# Stream pretend-output for 6 seconds
Sleep 6s

# Stop with Ctrl+C
Ctrl+C
Sleep 1s

# ── then crash detector ────────────────────────────────────────────────
Type "# Crash detector — only ERROR/FATAL with crash keywords"
Enter
Type "adb-control monitor crash"
Enter
Sleep 4s
Ctrl+C
Sleep 1s

# ── perf monitor ──────────────────────────────────────────────────────
Type "# Performance snapshot every 5 seconds"
Enter
Type "adb-control monitor perf -i 5"
Enter
Sleep 6s
Ctrl+C
