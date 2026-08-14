# Oneremit Design Audit

Audited live at https://oneremit.co/ (home page and `/_astro/global.CSLfihcW.css`).
The tokens below were verified against the shipped stylesheet and markup.

## Typography

- `--font-sans: "Albert Sans", sans-serif`. Weights used on site: 400, 500, 600, 700, 800
  (`--font-weight-normal/medium/semibold/bold/extrabold`).
- Display headings: bold, tight tracking (`tracking-[-2px]` mobile, `[-4px]` desktop),
  e.g. `text-[46px]/[54px]` mobile → `text-[90px]/[90px]` desktop.
- Sub-headings: semibold-to-bold `text-[36px]` → `text-[40px]/[56px]`.
- Body/subtitles: `text-muted` (`--color-muted: #fbfbfb82`) on dark canvas,
  `text-lg`–`text-xl`, medium weight.

## Color palette (verified)

| Token | Value | Use |
| --- | --- | --- |
| `--color-primary-600` | `#032620` | page canvas |
| `--color-primary-500` | `#043028` | primary buttons, dark surfaces, headings |
| `--color-primary-400` | `#365953` | soft-on-light text |
| `--color-primary-300` | `#68837e` | muted green text |
| `--color-primary-100` | `#cdd6d4` | borders / lines |
| `--color-accent-green` | `#beffc4` | accent buttons, brand gradient start |
| `--color-accent-green-bright` | `#92ff9d` | accent highlights, borders |
| `--color-accent-green-dark` | `#1b623a` | dark accent (processing) |
| `--color-off-white` | `#fbfbfb` | cards, light surfaces, button text |
| `--color-light-teal` | `#ecf6f4` | subtle light surfaces / rows |
| `--color-text-green` | `#4e756e` | muted labels on light |
| `--color-text-link` | `#679b92` | links / focus ring |
| `--color-muted` | `#fbfbfb82` | muted text on dark |
| `--color-muted-dark` | `#043028b3` | muted text on light |
| Glow/success green | `#05bb6c` | glow shadows, success |

## Radii

- Controls/inputs: ~8px (`rounded-[8px]`)
- Buttons: 8–10px (`rounded-[10px]`)
- Cards: ~20px (`rounded-[20px]`)
- Pills: full — eyebrow pills use `rounded-[20px]`
- Rows/tiles: 12px (`rounded-[12px]`)

## Pills / eyebrow badges

Verified markup (`bg-gradient-to-b from-[#f6f9fc] to-[#92ff9d]`):

```
rounded-[20px] border border-accent-green-bright
shadow-[0px_6px_24px_0px_rgba(5,187,108,0.12)]
bg-gradient-to-b from-[#f6f9fc] to-[#92ff9d]
```

- Text: `text-primary-500`, medium/semibold. Border: `#92ff9d`.
- Glow shadow: `0 6px 24px rgba(5,187,108,0.12)` (the `#05bb6c1f` shadow token).
- Dark variant swaps the gradient for `bg-primary-500` with `text-off-white`.

## Buttons

- Primary: `bg-primary-500` (`#043028`), `text-white/off-white`, `px-6 py-4`,
  `rounded-[10px]`, medium weight.
- Accent: `bg-accent-green` (`#beffc4`), text `#043028`, hover `#92ff9d`.
- Ghost: transparent, `border-primary-100`, dark text on light cards,
  hover `bg-light-teal`.
- Disabled: opacity ~0.5, `cursor: not-allowed`. Min tap target 44px.

## Cards

- Light: `bg-off-white` (`#fbfbfb`), text `primary-500`, radius ~20px, padding
  24–28px, soft forest shadow.
- Rows/tiles: `bg-light-teal` (`#ecf6f4`), radius 12px.

## Status semantics

Soft pill backgrounds with strong text (always include the text label):

| Status | bg | text |
| --- | --- | --- |
| pending | `#ecf6f4` | `#365953` |
| processing | `#e0f0ea` | `#1b623a` (animated pulse dot) |
| completed | `#d8f5dc` | `#14532d` |
| failed | `#fbeae7` | `#b4473a` |
| cancelled | `#e8e6e0` | `#5c5750` |

## Design motifs

- **Dark forest canvas**: `#032620` body with mint radial glow top-right and a
  soft teal glow bottom-left.
- **Mint pills with glow**: `#beffc4 → #92ff9d` gradient pills with the
  `rgba(5,187,108,0.12)` glow.
- **Off-white cards** floating on the dark canvas.
- **Sticky blurred header**: translucent `rgba(4,48,40,…)` + backdrop blur,
  brand mark = mint gradient rounded square with a bold "O".

## Responsive

- Dashboard grid stacks to one column under ~960px.
- Display type scales down on mobile; inputs render at 16px to prevent iOS zoom.
- Generous 24–32px section spacing; tap targets ≥ 44px.
- `prefers-reduced-motion` honored.
