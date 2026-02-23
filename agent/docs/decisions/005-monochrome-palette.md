# ADR-005: Monochrome Zinc Palette with Single Accent Color

## Status: Accepted
## Date: 2026-02-21

## Context

The email digest uses color to communicate tier priority. Initial design used traffic-light colors (green/yellow/red). Alternative: monochrome palette with a single accent.

## Decision

Zinc monochrome (#f4f4f5 to #27272a) with orange (#e97316) as the sole accent color, used only on CTAs and the top tier border.

## Rationale

- **Accessibility.** ~8% of men have red-green color vision deficiency (deuteranopia). Traffic-light tiers are invisible to them. Monochrome + orange works for all vision types.
- **Information hierarchy through typography, not color.** Tier A gets 4px border + full card with strengths/gaps. Tier B gets 2px border + compact row. Tier C gets a single muted line. The structure communicates priority without relying on color.
- **Professional appearance.** Monochrome reads as intentional design, not "default Bootstrap." Single accent prevents visual noise.
- **Email client compatibility.** Some clients strip or override colors. Monochrome degrades gracefully. Traffic lights in a client that strips CSS become three identical sections.

## Consequences

- Tier differentiation relies on layout and typography, which requires more design effort than "paint it red"
- Orange accent must be used sparingly (only CTAs and Tier A border) or it loses its signal value
- Dark mode: zinc palette inverts cleanly. Traffic lights in dark mode often clash
