# Android Key Event Codes Reference

Complete list of key event codes for ADB input commands.

## Usage

```bash
adb shell input keyevent <code>
```

## Navigation Keys

| Code | Name | Description |
|------|------|-------------|
| 3 | KEYCODE_HOME | Home button |
| 4 | KEYCODE_BACK | Back button |
| 82 | KEYCODE_MENU | Menu button |
| 187 | KEYCODE_APP_SWITCH | Recent apps |
| 84 | KEYCODE_SEARCH | Search |

## Power & Volume

| Code | Name | Description |
|------|------|-------------|
| 26 | KEYCODE_POWER | Power button |
| 223 | KEYCODE_SLEEP | Sleep |
| 224 | KEYCODE_WAKEUP | Wake up |
| 24 | KEYCODE_VOLUME_UP | Volume up |
| 25 | KEYCODE_VOLUME_DOWN | Volume down |
| 164 | KEYCODE_VOLUME_MUTE | Mute |

## Media Keys

| Code | Name | Description |
|------|------|-------------|
| 85 | KEYCODE_MEDIA_PLAY_PAUSE | Play/Pause |
| 86 | KEYCODE_MEDIA_STOP | Stop |
| 87 | KEYCODE_MEDIA_NEXT | Next track |
| 88 | KEYCODE_MEDIA_PREVIOUS | Previous track |
| 89 | KEYCODE_MEDIA_REWIND | Rewind |
| 90 | KEYCODE_MEDIA_FAST_FORWARD | Fast forward |
| 126 | KEYCODE_MEDIA_PLAY | Play |
| 127 | KEYCODE_MEDIA_PAUSE | Pause |

## Keyboard Keys

| Code | Name | Description |
|------|------|-------------|
| 66 | KEYCODE_ENTER | Enter |
| 67 | KEYCODE_DEL | Backspace |
| 112 | KEYCODE_FORWARD_DEL | Delete |
| 61 | KEYCODE_TAB | Tab |
| 62 | KEYCODE_SPACE | Space |
| 111 | KEYCODE_ESCAPE | Escape |

## Cursor Navigation

| Code | Name | Description |
|------|------|-------------|
| 19 | KEYCODE_DPAD_UP | Up |
| 20 | KEYCODE_DPAD_DOWN | Down |
| 21 | KEYCODE_DPAD_LEFT | Left |
| 22 | KEYCODE_DPAD_RIGHT | Right |
| 23 | KEYCODE_DPAD_CENTER | Center/Select |
| 122 | KEYCODE_MOVE_HOME | Move to start |
| 123 | KEYCODE_MOVE_END | Move to end |
| 92 | KEYCODE_PAGE_UP | Page up |
| 93 | KEYCODE_PAGE_DOWN | Page down |

## Function Keys

| Code | Name | Description |
|------|------|-------------|
| 131-142 | KEYCODE_F1-F12 | Function keys F1-F12 |

## Alphabet Keys

| Code | Name |
|------|------|
| 29-54 | KEYCODE_A-Z |

## Number Keys

| Code | Name |
|------|------|
| 7-16 | KEYCODE_0-9 |

## Special Characters

| Code | Name | Character |
|------|------|-----------|
| 55 | KEYCODE_COMMA | , |
| 56 | KEYCODE_PERIOD | . |
| 69 | KEYCODE_MINUS | - |
| 70 | KEYCODE_EQUALS | = |
| 71 | KEYCODE_LEFT_BRACKET | [ |
| 72 | KEYCODE_RIGHT_BRACKET | ] |
| 73 | KEYCODE_BACKSLASH | \ |
| 74 | KEYCODE_SEMICOLON | ; |
| 75 | KEYCODE_APOSTROPHE | ' |
| 76 | KEYCODE_SLASH | / |
| 77 | KEYCODE_AT | @ |

## Modifier Keys

| Code | Name | Description |
|------|------|-------------|
| 57 | KEYCODE_ALT_LEFT | Left Alt |
| 58 | KEYCODE_ALT_RIGHT | Right Alt |
| 59 | KEYCODE_SHIFT_LEFT | Left Shift |
| 60 | KEYCODE_SHIFT_RIGHT | Right Shift |
| 113 | KEYCODE_CTRL_LEFT | Left Ctrl |
| 114 | KEYCODE_CTRL_RIGHT | Right Ctrl |
| 115 | KEYCODE_CAPS_LOCK | Caps Lock |

## Phone Keys

| Code | Name | Description |
|------|------|-------------|
| 5 | KEYCODE_CALL | Call/Answer |
| 6 | KEYCODE_ENDCALL | End call |
| 27 | KEYCODE_CAMERA | Camera |
| 80 | KEYCODE_FOCUS | Camera focus |

## Gamepad Keys

| Code | Name | Description |
|------|------|-------------|
| 96 | KEYCODE_BUTTON_A | A button |
| 97 | KEYCODE_BUTTON_B | B button |
| 98 | KEYCODE_BUTTON_C | C button |
| 99 | KEYCODE_BUTTON_X | X button |
| 100 | KEYCODE_BUTTON_Y | Y button |
| 101 | KEYCODE_BUTTON_Z | Z button |
| 102 | KEYCODE_BUTTON_L1 | L1 |
| 103 | KEYCODE_BUTTON_R1 | R1 |
| 104 | KEYCODE_BUTTON_L2 | L2 |
| 105 | KEYCODE_BUTTON_R2 | R2 |
| 106 | KEYCODE_BUTTON_THUMBL | Left thumb |
| 107 | KEYCODE_BUTTON_THUMBR | Right thumb |
| 108 | KEYCODE_BUTTON_START | Start |
| 109 | KEYCODE_BUTTON_SELECT | Select |

## System Keys

| Code | Name | Description |
|------|------|-------------|
| 120 | KEYCODE_SYSRQ | Screenshot |
| 121 | KEYCODE_BREAK | Break |
| 124 | KEYCODE_INSERT | Insert |
| 211 | KEYCODE_BRIGHTNESS_DOWN | Brightness down |
| 212 | KEYCODE_BRIGHTNESS_UP | Brightness up |

## Examples

```bash
# Press home
adb shell input keyevent 3

# Take screenshot
adb shell input keyevent 120

# Volume up 3 times
for i in 1 2 3; do adb shell input keyevent 24; done

# Type "hello" using keycodes (A=29, so h=36, e=33, l=40, o=43)
adb shell input keyevent 36 33 40 40 43
```
