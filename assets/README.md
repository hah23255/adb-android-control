# Project assets

Source files for the project's visual identity. Rendered output (`.png`,
`.gif`) is regenerated from sources, not stored in git long-term — keep
the renderer commands here documented and reproducible.

## Layout

```
assets/
├── logo/
│   └── logo.svg              # 512×512 square logo (terminal + droid)
├── social/
│   └── og-banner.svg         # 1280×640 GitHub social-preview banner
├── demos/
│   ├── 01-quickstart.tape    # VHS recipe → 30s tour
│   ├── 02-monitor.tape       # VHS recipe → real-time monitor
│   ├── 03-reconnect.tape     # VHS recipe → wireless reconnect
│   └── *.gif                 # generated; gitignored
└── README.md                 # this file
```

## Rendering

### Logos / banners (SVG → PNG)

Need [`rsvg-convert`](https://gitlab.gnome.org/GNOME/librsvg) or
[`inkscape`](https://inkscape.org/):

```bash
# Square logo at 512×512
rsvg-convert assets/logo/logo.svg -o assets/logo/logo.png -w 512 -h 512

# Avatar-sized variant (256×256)
rsvg-convert assets/logo/logo.svg -o assets/logo/logo-256.png -w 256 -h 256

# Social-preview banner at 1280×640 (GitHub setting size)
rsvg-convert assets/social/og-banner.svg -o assets/social/og-banner.png -w 1280 -h 640

# Inkscape alternative
inkscape assets/logo/logo.svg --export-filename=assets/logo/logo.png --export-width=512
```

The SVG sources are the source of truth — edit those, regenerate
PNGs, never edit PNGs by hand.

### Demo GIFs

[VHS](https://github.com/charmbracelet/vhs) records terminal sessions
to `.gif` deterministically. Install once:

```bash
brew install vhs                              # macOS
sudo apt install ffmpeg && go install …       # Linux (see VHS repo)
```

Render:

```bash
vhs assets/demos/01-quickstart.tape    # → 01-quickstart.gif
vhs assets/demos/02-monitor.tape       # → 02-monitor.gif
vhs assets/demos/03-reconnect.tape     # → 03-reconnect.gif
```

The `.tape` files use placeholder commands (real `adb-control`
invocations against a non-routable RFC 5737 IP `192.0.2.42`) so the
demos are reproducible without a real device. For production GIFs,
swap the placeholder IP for `<DEVICE_IP>` and record against your
own hardware — but **never commit the rendered GIF if it shows
real device data**.

## Where these are used

| Asset | Used by |
|---|---|
| `logo/logo.png` (256×256) | GitHub repo avatar; PyPI page (Phase 7) |
| `logo/logo.png` (512×512) | README hero (Phase 6 README polish — pending PNG) |
| `social/og-banner.png` (1280×640) | GitHub repo settings → "Social preview" |
| `demos/01-quickstart.gif` | README "Quickstart" section embed |
| `demos/02-monitor.gif` | README "Real-time monitor" section embed |
| `demos/03-reconnect.gif` | `docs/TROUBLESHOOTING.md` § C |

## Design tokens

Colour palette (from `logo.svg`):

| Role | Hex | Use |
|---|---|---|
| Deep background | `#0d1b2a` | logo bg, banner bg |
| Mid background | `#1b263b` | terminal frame |
| Border / dim text | `#415a77` | borders, grid |
| Muted foreground | `#778da9` | secondary text |
| Accent | `#83c5be` | prompt `$`, highlights |
| Bright accent | `#a8dadc` | droid silhouette |
| Foreground | `#e0fbfc` | main text |
| Alert | `#e63946` | error / warning |
| Success | `#2ecc71` | OK / done |
| Caution | `#f1c40f` | warning |

## Future assets (Phase 7+)

- `assets/diagrams/architecture.png` — exported from
  `docs/ARCHITECTURE.md` Mermaid blocks for non-Markdown surfaces
  (PyPI, presentations)
- `assets/charts/coverage-trend.svg` — Codecov badge graphics
- `assets/diagrams/connection-state-machine.png` — same source as
  ARCHITECTURE.md's `stateDiagram-v2` block
