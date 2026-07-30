# RetailOps AI — Design Spec

Constraints for any session building UI. Read this before writing a component.

---

## 0. How to use this file

Do not ask a build session to make the UI "premium," "luxury," or "professional."
Adjectives produce the default look. Constraints produce the intended one.

Instead: point the session at this file and require that every color, size, and
spacing value comes from the tokens below. If a value is not in this file, it is
not allowed in the code.

---

## 1. What premium means in this category

This is an operations console for people who look at numbers all day. In this
category, premium reads as **precision and restraint**, not richness.

Premium here is:
- numbers that align perfectly in a column, at every zoom level
- one accent color, used rarely enough that it still means something
- empty, loading, and error states that were designed, not defaulted
- 150ms transitions that you notice only when they're missing
- hairlines instead of shadows
- consistent radius, consistent spacing, no exceptions

Premium here is **not**: gold, gradients, glassmorphism, glow, 3D, hero
animations, emoji, or a dark theme with neon. Those read as cheap in a tool that
claims every number is auditable.

The rule: **the data is the decoration.** Nothing else competes with it.

---

## 2. Signature idea

**Anything measured is monospaced. Anything explained is not.**

Every number, ID, tool name, endpoint, timestamp, SKU, and duration renders in
the mono face — at every size, including large dashboard figures. Prose,
labels, and headings render in the sans face.

This is the one memorable typographic decision. It maps directly onto the
product thesis: machine facts look like machine facts, LLM prose looks like
prose, and you can tell them apart without reading.

Do not break this rule for aesthetic reasons.

---

## 3. Color tokens

Defined in Tailwind v4 via `@theme` in the global stylesheet. No `tailwind.config.js`.

Dark is the default theme. Light mode must be supported and must not be an
inverted afterthought.

```css
@theme {
  /* dark — canonical */
  --color-canvas:      #0B0B0C;  /* app background */
  --color-surface:     #141416;  /* cards, panels */
  --color-raised:      #1C1C1F;  /* drawers, popovers, hover */
  --color-hairline:    rgba(255,255,255,0.08);
  --color-hairline-hi: rgba(255,255,255,0.14);

  --color-text-hi:     #E8E8E6;  /* primary */
  --color-text-mid:    #9A9A96;  /* labels, secondary */
  --color-text-low:    #6A6A67;  /* disabled, meta */

  --color-accent:      #BE8A3D;  /* brass — interactive + active state ONLY */
  --color-accent-dim:  rgba(190,138,61,0.14);

  --color-danger:      #B4463C;  /* desaturated brick, not red-500 */
}
```

Light theme uses the same structure: canvas `#FAFAF8`, surface `#FFFFFF`,
raised `#F4F4F1`, hairline `rgba(0,0,0,0.10)`, text-hi `#17171A`,
text-mid `#5F5F5C`, text-low `#8A8A86`. Accent and danger unchanged.

### Color rules

1. **Accent is for interaction and the currently-running agent node. Nothing else.**
   Not for headings, not for icons, not for emphasis, not for charts.
2. **There is no success green and no warning amber.** Status is communicated by
   text and shape, never hue. This is deliberate — see §5.
3. **Danger is the only other saturated color**, and only for destructive
   actions and validation failures.
4. **Grays carry the entire structure.** If a layout only works once you add
   color, the layout is wrong.
5. Chart series use a neutral sequence derived from the gray ramp plus accent as
   the single highlight. Forecast bands are gray, never colored.

---

## 4. Type, space, shape, motion

**Faces**
- Sans: Geist Sans — UI, prose, labels
- Mono: Geist Mono — all numerics and machine identifiers (see §2)
- No third face. No serif.

**Scale** (only these values)
`11 / 12 / 13 / 14 / 16 / 20 / 28 / 40`

- Table and dense rows: 13px, line-height 1.45
- Body prose: 14px, line-height 1.6, max-width 68ch
- Section headings: 16px medium
- Dashboard hero figures: 40px mono, weight 500

**Required globally**

```css
font-variant-numeric: tabular-nums;
font-feature-settings: "tnum" 1;
```

All numeric table columns are right-aligned. Currency is **£**. Never render a
currency symbol the dataset doesn't use.

**Spacing** — 4px base, 8px rhythm. Only `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`.

**Radius** — one value: `6px`. Everything. No pill buttons, no `rounded-2xl`
cards. Exception: status dots are circles.

**Elevation** — hairline borders only. `box-shadow` is permitted **only** on
overlays that float above the page (popover, dropdown, modal), and then only as
a soft ambient shadow. Cards never have shadows.

**Motion** — 120–180ms, `ease-out`. Permitted on: state change, drawer open,
node status transition, streaming text. Forbidden on: page load, scroll, hover
of static content, chart entrance. Respect `prefers-reduced-motion`.

---

## 5. Component rules

### Provenance badges
Four states: **Observed / Derived / Predicted / Inferred**.
Encoded by **shape and text**, not hue — all four use `--color-text-mid`.

- Observed — solid dot + label
- Derived — hollow dot + label
- Predicted — hollow dot with center bar + label
- Inferred — dashed ring + label

The label text is always present and always readable by a screen reader. A
badge that communicates only by color is a bug.

Confidence values carry the Derived or Predicted badge. Never Observed.

### Citation chip
Every figure produced by a tool call renders as a chip: the value in mono,
followed by a 10px superscript reference marker. Hover raises the background to
`--color-raised`. Click opens the provenance drawer.

A figure with no resolvable tool call renders with a `MISSING SOURCE` label in
`--color-danger`. Never silently render it as normal text.

### Tables
13px rows, 32px row height, hairline row separators, no zebra striping, no
vertical grid lines. Header row: 11px, uppercase, `--color-text-mid`, letter
spacing 0.04em. Sticky header. Numbers right-aligned and monospaced.

### Recommendation card
Order: priority label → title → impact figures (mono, with citation chips) →
provenance badge → actions.

Wording must never imply the system acted. `Pending review`, `Accepted by you`,
`Rejected by you`. Never a checkmark next to a recommendation that was only
generated.

Actions: `Accept` / `Reject` / `Snooze`. Full keyboard operation required.

### Execution graph
React Flow + Dagre. Node states: idle (hairline), running (accent border +
accent-dim fill), complete (hairline-hi), error (danger border), replanned
(dashed border, 60% opacity).

Nodes carry: agent name (sans), duration in ms (mono), tool name (mono).
Recompute layout only when the node or edge set changes — never per token.

A replan appends a branch and dims what it superseded. It never clears the canvas.

### App chrome
Persistent, always visible:
`Online Retail II · as-of 2011-12-09`
Dataset name and as-of date in mono, `--color-text-mid`. This is a statement of
fact, not a mode toggle.

---

## 6. States — build all four, every time

The single largest difference between a portfolio UI and a product UI. No
component ships with only its happy path.

For every data surface:
- **Loading** — skeleton blocks matching final layout dimensions. Never a spinner
  as the only loading state. Never layout shift on resolve.
- **Empty** — one sentence saying what will appear here and one action. Not an
  illustration. Not "No data."
- **Error** — what failed, in the interface's voice, plus a retry. Errors do not
  apologize and are never vague.
- **Streaming** — partial content renders immediately; incomplete markdown and
  tables buffer until closeable; a `Stop` control that sends a real cancel event
  is present the entire time a run is in flight.

---

## 7. Forbidden

Reject any of these in review:

- Tailwind default palette classes on surfaces or text (`slate-*`, `blue-600`,
  `emerald-500`, `red-500`, `amber-500`) — use the theme tokens
- shadcn defaults left unmodified: `rounded-lg` cards, `shadow-sm`, default
  border colors
- Gradients of any kind, including text gradients
- Glassmorphism, backdrop blur as decoration, glow effects
- Emoji in the interface
- Drop shadows on non-overlay elements
- More than one accent color
- Color as the sole carrier of meaning
- Animated chart entrances
- A number rendered in the sans face
- Currency symbols other than £
- Icon-only buttons without accessible labels
- Hover-only affordances with no keyboard equivalent
- Any hex value not in §3

---

## 8. Acceptance checklist

A screen is done when all of these pass:

- [ ] Every hex, size, and spacing value traces to §3–4
- [ ] Numerics are monospaced and tabular; columns align at 90% and 150% zoom
- [ ] Loading, empty, error, and streaming states exist and were designed
- [ ] Full keyboard path; visible focus ring on every interactive element
- [ ] Contrast ≥ 4.5:1 text, ≥ 3:1 non-text; verified in both themes
- [ ] `prefers-reduced-motion` honored
- [ ] Usable at 1280px and at 768px
- [ ] No provenance or status conveyed by color alone
- [ ] Every displayed figure opens a provenance drawer, or is flagged MISSING SOURCE
- [ ] Nothing on screen implies the system took an action on its own

---

## 9. Paste-ready session brief

> Build <component> for RetailOps AI.
>
> Read `docs/DESIGN-SPEC.md` first and follow it exactly. Every color, font size,
> spacing, and radius value must come from the tokens defined there — if a value
> isn't in the spec, don't use it.
>
> Hard requirements: numerics in Geist Mono with tabular figures; a single accent
> used only for interaction and active state; hairline borders, no card shadows;
> 6px radius everywhere; loading, empty, error, and streaming states all built;
> full keyboard operation with visible focus.
>
> Do not use Tailwind default palette colors, shadcn default card styling,
> gradients, glow, emoji, or any second accent color.
>
> When you're done, walk the §8 acceptance checklist and report which items pass
> and which don't. Don't claim a checklist item passes without verifying it.
