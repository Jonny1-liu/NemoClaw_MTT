---
name: asus-design-system-universal
description: "Apply this skill whenever the user asks to build, generate, modify, or review any ASUS internal system UI, ASUS component, ASUS design system element, AOCC interface, or ASUS AI Chat / AI Hub interface. Trigger on any mention of: ASUS UI, ASUS design system, ASUS internal tool, AOCC, ASUS AI Chat, ASUS component, ASUS button, ASUS color token, ASUS dark mode. Also trigger when the user shares a design spec or mockup and asks to implement it in React/CSS for an ASUS product. Use this skill for ALL such requests — do not attempt ASUS UI generation without it."
---

# ASUS Internal System UI — Design System Skill

This skill provides the complete specification for generating ASUS internal system UI. Always read the relevant spec files before writing any code or styles.

---

## File Reference

All specifications are bundled alongside this SKILL.md:

| File | When to Read |
|---|---|
| `asus-design-system.md` | **Always** — single source of truth for all design values (colors, typography, spacing, shadows, layout, 70+ components, dark mode) |
| `asus-tech-stack.md` | **Always** — tech stack conventions (React 18 + Vite 6 + CSS Custom Properties), design tokens as `:root` CSS variables, scaffold templates |
| `asus-ai-chat-patterns.md` | **Additionally**, when building any AI Chat interface, AOCC, or AI Hub with messaging/streaming UI |

> **Priority rule:** `asus-design-system.md` is the single source of truth. `asus-tech-stack.md` implements it as code — never overrides it. `asus-ai-chat-patterns.md` only adds what the core file does not cover.

---

## How to Apply This Skill

### Step 1 — Read the spec files

Before writing any code, read:
1. `asus-design-system.md` (full design spec)
2. `asus-tech-stack.md` (implementation conventions + CSS token templates)
3. `asus-ai-chat-patterns.md` (if building a chat interface)

### Step 2 — Follow these non-negotiable rules

1. **Never guess style values.** Every color hex, spacing value, font size, shadow, and border-radius is defined in the spec. Look it up — do not invent values.
2. **Light + Dark mode required.** Every component must implement both themes. Use `[data-theme="dark"]` selector, not Tailwind `dark:`.
3. **Respect layer hierarchy.** Background → Card Layer 1 → Card Layer 2. Never skip a layer.
4. **Capsule buttons.** All standard buttons use `border-radius: 30px`.
5. **AI vs Standard buttons.** Never place AI Primary Button and Standard Primary Button on the same screen.
6. **No Tailwind CSS.** All styling uses CSS Custom Properties (design tokens) + vanilla CSS.
7. **Motion preference.** Must support `prefers-reduced-motion: reduce`.

### Step 3 — Use the CSS token template

The full `:root` (Light) and `[data-theme="dark"]` (Dark) CSS token sets are in `asus-tech-stack.md`. Always paste these into `styles.css` as-is, then add component styles on top.

### Step 4 — Use the scaffold template

`asus-tech-stack.md` provides `index.html`, `package.json`, `vite.config.js`, and `main.jsx` scaffolds. Use them for new projects.

---

## Common Component Lookup

| Component | Section in asus-design-system.md |
|---|---|
| Button (Standard / AI / Icon / Text) | §18, §19 |
| Input / Textarea | §20 |
| Dropdown / Select | §21 |
| Table | §25 |
| Dialog / Modal | §30 |
| Toast / Notification | §31 |
| Tag / Badge | §32 |
| Side Navigation | §40 |
| Card (L1 / L2) | §10–§12 |
| Color tokens (full scale) | §2 |
| Typography scale | §4 |
| Shadow system | §5 |
| Grid layout | §6 |

For AI Chat-specific components (message bubbles, streaming, rich input, code blocks), refer to `asus-ai-chat-patterns.md`.
