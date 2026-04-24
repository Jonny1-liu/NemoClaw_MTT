# ASUS Internal System — AI Chat Interface Patterns & Supplementary Specification

This document supplements `asus-design-system.md` with patterns not covered in the unified design system: AI Chat interface patterns, App Shell layout, icon system, motion/animation specs, accessibility/focus styles, and more. All specs must support both Light and Dark mode.

> **Positioning:** This document does NOT repeat content already defined in the unified design system. It only supplements what is missing. Both documents must be used together.

---

## 1. App Shell Layout

AI Chat applications use a three-column App Shell layout, used alongside the Side Navigation defined in the main design system §40.

### 1.1 Three-Column Architecture

```
┌──────┬────────────┬──────────────────────────┬────────────┐
│ Side │  Sidebar   │       Main Content       │   Right    │
│Header│   Nav      │                          │   Panel    │
│ 48px │  260px     │       flex: 1            │   280px    │
└──────┴────────────┴──────────────────────────┴────────────┘
```

| Region | Width | Min Width | Collapsible | Background (Light) | Background (Dark) |
|---|---|---|---|---|---|
| Side Header | 48px | 48px | No | `#002169` (Blue-900) | `#002169` |
| Sidebar Nav | 260px | 0px (collapsed) | Yes | `#FFFFFF` | `#0E1116` |
| Main Content | flex: 1 | 480px | No | `#FFFFFF` | `#0E1116` |
| Right Panel | 280px | 0px (collapsed) | Yes | `#FFFFFF` | `#0E1116` |

### 1.2 Collapse Behavior
- **Sidebar Nav collapse:** Width transitions from 260px to 0px, `overflow: hidden`
- **Right Panel collapse:** Width transitions from 280px to 0px, `overflow: hidden`
- **Transition:** `width 0.25s cubic-bezier(0.4, 0, 0.2, 1)`
- **Trigger:** Click collapse button in Side Header or Panel Header

### 1.3 Responsive Breakpoint Behavior

| Breakpoint | Side Header | Sidebar Nav | Right Panel |
|---|---|---|---|
| ≥ 1280px | Visible | Visible | Visible |
| 1025–1279px | Visible | Visible | Hidden |
| ≤ 1024px | Visible | Hidden (Overlay mode) | Hidden |

---

## 2. Chat / Messaging Components

### 2.1 Message Bubble

#### User Message
- **Alignment:** Right-aligned
- **Background:** Light `#006CE1` (Primary) / Dark `#1389FC`
- **Text color:** `#FFFFFF`
- **border-radius:** 16px 16px 4px 16px (bottom-right narrowed)
- **Max width:** 70% of container width
- **Padding:** 12px 16px
- **Font:** Body4 (14px / line-height 175%)

#### AI Response Message
- **Alignment:** Left-aligned
- **Background:** Light `#F5F6F8` (Gray-050) / Dark `#1D1F26` (Card Layer 1)
- **Text color:** Light `#23252C` / Dark `#D1D4E4`
- **border-radius:** 16px 16px 16px 4px (bottom-left narrowed)
- **Max width:** 80% of container width
- **Padding:** 12px 16px
- **AI identifier:** Left side shows AI avatar (32px circle, gradient background `#1389FC` → `#0CB5E4`)

#### Message Spacing
- **Same sender consecutive messages:** 4px gap
- **Different sender switch:** 16px gap
- **Timestamp:** Centered, font Body5 (12px), color `var(--text-tertiary)`, margin 12px top and bottom

### 2.2 Code Block

- **Background:** Light `#1D1F26` / Dark `#0E1116`
- **Text color:** Monospace font, light-colored syntax highlighting
- **Font:** `'Fira Code', 'Consolas', 'Monaco', monospace`, 13px, line-height 160%
- **border-radius:** 8px
- **Padding:** 16px
- **Header Bar:** Language label (left) + Copy button (right), background slightly darker than code block, padding 8px 16px
- **Copy button:** Click changes text from "Copy" to "Copied!", reverts after 2 seconds
- **Inline Code:** Background Light `#EEEFF5` / Dark `#26282F`, padding 2px 6px, border-radius 4px

### 2.3 Markdown Rendering

AI responses containing Markdown should render with these styles:

| Element | Style |
|---|---|
| `# H1` | H4 (20px, Bold) |
| `## H2` | H5 (18px, Semi-bold) |
| `### H3` | H6 (16px, Semi-bold) |
| `**Bold**` | font-weight: 600 |
| `*Italic*` | font-style: italic |
| `- List` | Left padding 20px, bullet color `var(--text-tertiary)` |
| `1. Ordered` | Left padding 20px, number color `var(--text-tertiary)` |
| `> Blockquote` | Left 3px solid `var(--primary)`, padding-left 16px, background `var(--surface-secondary)` |
| `[Link](url)` | Color `var(--primary)`, hover adds underline |
| `---` | 1px solid `var(--border)`, margin 16px 0 |
| Table | Follows main design system §9 Table spec (Minimum row 34px) |

### 2.4 Streaming Text Animation

- **Token-by-token appearance:** Each token fades in, `opacity 0→1`, duration 80ms
- **Cursor indicator:** Blinking blue block cursor `|` at text end
  - Width 2px, height matches line-height
  - Color `var(--primary)`
  - Animation `blink 1s step-end infinite`
- **After completion:** Cursor disappears, action button row appears (Copy / Regenerate / 👍 / 👎)

### 2.5 Thinking / Loading Indicator

- **Structure:** AI avatar + three bouncing dots
- **Dot size:** 6px diameter
- **Dot color:** `var(--primary)`
- **Animation:** Vertical bounce, stagger delay 0.15s, duration 0.6s, `ease-in-out`, infinite
- **Container:** Same background and border-radius as AI message bubble

### 2.6 Message Actions

Displayed below each AI response:

- **Buttons:** Copy / Regenerate / 👍 / 👎
- **Style:** Follows main design system §21 Action Button — Quiet type
- **Default:** Hidden, shown on message hover (fade-in 150ms)
- **Spacing:** Button gap 4px, margin 8px from message bottom

---

## 3. Icon System

The unified design system does not define an icon library. The following supplements that gap.

### 3.1 Icon Source
- **Primary:** Custom SVG icon set (consistent with Prisma Design System)
- **Fallback:** When no custom icon exists, use [Phosphor Icons](https://phosphoricons.com/) Regular weight

### 3.2 Icon Sizes

| Token | Size | Usage |
|---|---|---|
| Icon-XS | 12px | Inside badges, tiny markers |
| Icon-SM | 16px | Inside buttons, input leading icons, list items |
| Icon-MD | 20px | Navigation items, standard action buttons |
| Icon-LG | 24px | Next to page titles, emphasis actions |
| Icon-XL | 32px | Empty states, feature cards |

### 3.3 Icon-Text Alignment
- **Vertical alignment:** `vertical-align: -0.125em` (consistent with antd)
- **Icon-text spacing:** 6px (Small button) / 8px (Medium button) / 10px (Large button)
- **Icon-only buttons:** Square container, icon centered

### 3.4 Icon Color Rules
- **Default:** Inherits parent text color (`currentColor`)
- **Interactive states:** Syncs with text color changes (turns Primary Blue on hover together)
- **Disabled:** Syncs with text to `var(--text-disabled)`
- **Semantic icons:** Use corresponding semantic colors (Error red, Success green, Warning orange, Info blue)

---

## 4. Motion & Transition System

### 4.1 Duration Tokens

| Token | Duration | Usage |
|---|---|---|
| `--duration-fast` | 100ms | Tooltip appearance, button active feedback |
| `--duration-normal` | 200ms | Hover effects, button state changes, Tab switching |
| `--duration-moderate` | 300ms | Panel expand/collapse, Card lift, theme switching |
| `--duration-slow` | 500ms | Page transitions, Drawer open/close, Dialog appearance |

### 4.2 Easing Tokens

| Token | Curve | Usage |
|---|---|---|
| `--ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | General transitions (Material Standard) |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Element leaving screen |
| `--ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Element entering screen |
| `--ease-bounce` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Elastic effect (Toast, Badge appearance) |

### 4.3 General Transition Rules
- **Color changes (background, color, border-color):** `--duration-normal` + `--ease-default`
- **Size changes (width, height, padding):** `--duration-moderate` + `--ease-default`
- **Position (transform: translate):** `--duration-moderate` + `--ease-out`
- **Opacity:** `--duration-normal` + `linear`
- **Shadow (box-shadow):** `--duration-normal` + `--ease-default`

### 4.4 Special Animations

#### Loading Bars Animation (supplements main design system §56)
```css
@keyframes loadingBars {
  0%, 100% { height: 5px; y: 13; }
  50% { height: 21px; y: 5; }
}
/* Three bars stagger: 0s / 0.15s / 0.3s, duration 0.6s, infinite */
```

#### AI Button Gradient Animation (defined in main §19, CSS variables supplemented here)
```css
@keyframes gradientMove {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
/* duration: 7s, timing: linear, iteration: infinite */
```

#### Toast Enter/Exit Animation
```css
/* Enter — slide in from bottom */
@keyframes toastIn {
  from { transform: translateY(100%); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
/* Exit — slide out to right */
@keyframes toastOut {
  from { transform: translateX(0); opacity: 1; }
  to { transform: translateX(100%); opacity: 0; }
}
/* duration: --duration-moderate, easing: --ease-out / --ease-in */
```

---

## 5. Focus & Keyboard Navigation

### 5.1 Focus Ring Styles

| Scenario | Style |
|---|---|
| Default Focus Ring | `outline: 2px solid var(--primary); outline-offset: 2px;` |
| On dark backgrounds | `outline: 2px solid #FFFFFF; outline-offset: 2px;` |
| Input Focus | No outline; use `border-color: var(--primary)` + `box-shadow: 0 0 0 3px rgba(0,108,225,.15)` |
| Dark Mode Focus Ring | `outline: 2px solid #1389FC; outline-offset: 2px;` |

### 5.2 Focus Visibility Rules
- **Mouse interaction:** Hide focus ring (use `:focus-visible` not `:focus`)
- **Keyboard interaction:** Show focus ring
- **CSS implementation:** `*:focus { outline: none; }` + `*:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }`

### 5.3 Tab Order Rules
- **Side navigation:** Side Header icons → Sidebar Nav items → Main Content
- **Main Content:** Header controls → Chat body → Input area
- **Dialog / Drawer:** Focus trap when open, restore original focus on close
- **Dropdown:** Focus first option on open, ↑↓ key navigation, Enter to select, Escape to close

### 5.4 Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send message (in input) |
| `Shift + Enter` | New line (in input) |
| `Escape` | Close Dropdown / Dialog / Drawer |
| `Ctrl + /` | Focus input field |
| `Ctrl + Shift + N` | New conversation |

---

## 6. Rich Input Component (Contenteditable)

The main design system §31 Text Field only covers `<input>` and `<textarea>`. This supplements the `contenteditable` Rich Input specification.

### 6.1 Base Styles
- **Container:** `border-radius: 16px`, `border: 1px solid var(--border)`
- **Focus:** `border-color: var(--primary)`
- **Inner padding:** 12px 16px (top input area) / 4px 8px (bottom toolbar)
- **Min height:** 24px (single line)
- **Max height:** 120px (~5 lines), internal scrollbar when exceeded

### 6.2 Placeholder
- **Implementation:** CSS `::before` pseudo-element, `content: attr(data-placeholder)`
- **Condition:** Only shown when `:empty`
- **Color:** `var(--text-tertiary)`
- **Not selectable:** `pointer-events: none`

### 6.3 Bottom Toolbar
- **Structure:** Left side (AI magic button + mode selector) | Right side (Settings + Attachment + Divider + Send button)
- **Divider:** Vertical 1px, height 20px, color `var(--border)`
- **Send button:** 32px circle, Primary Blue background, white arrow icon
- **Disabled state:** When input is empty, send button `opacity: 0.4`, `cursor: not-allowed`

### 6.4 @Mention & /Command
- **Trigger:** Typing `@` or `/` opens a Popover menu
- **Popover style:** Follows main design system §45 Popover + §35 Dropdown Menu
- **Selected item:** Inserted as non-editable Tag (follows §62 Tag Picker — Default state)
- **Tag color:** `@mention` uses Primary Blue background / `/command` uses Gray-075 background

---

## 7. AI Visual Language Extensions

### 7.1 AI Gradient Palette
- **Primary gradient:** `linear-gradient(135deg, #9652FF, #006CE1, #0CB5E4)`
- **Usage:** AI avatar background, AI feature markers, AI Button (defined in main §19)
- **Glow effect:** `radial-gradient(circle, rgba(150,82,255,.08) 0%, transparent 65%)`, used for AI feature block backgrounds

### 7.2 AI Generated Content Marker
- **Marker method:** 2px gradient vertical bar on left side of AI response (using AI primary gradient)
- **Alternative:** AI avatar + "AI" text label (gradient background, white text, border-radius 30px, padding 2px 8px)

### 7.3 AI Feature Card
- **Background:** Dark scenes use `rgba(255,255,255,.03)` + `border: 1px solid rgba(255,255,255,.06)`
- **Hover:** Background brightens to `rgba(255,255,255,.06)` + border turns `rgba(150,82,255,.2)`
- **Lift:** `transform: translateY(-4px)`

---

## 8. Product / Tool Card Components

The main design system §7 Card only defines generic card layers. This supplements product showcase cards used in AI Hub tool catalogs.

### 8.1 Hero Tool Card

Used for core tool showcases like AI Hub Family, with gradient backgrounds and large icons.

- **Layout:** Horizontal, left icon area + right content area
- **Icon area:** Width 120px, height 100%, gradient background (unique per tool)
- **Icon size:** 40px (Icon-XL), centered
- **Content area:** Padding 16px, contains Title (H4), Description (Body2), Action button (Primary, Medium)
- **Card border-radius:** 12px
- **Card border:** Light = no border + Shadow Depth 1 / Dark = `1px solid var(--border)`
- **Hover:** Shadow Depth 2 + `transform: translateY(-2px)`

### 8.2 Compact Tool Card

Used for tool lists like AI Marketing Utilities, BI Agent Series.

- **Layout:** Horizontal, left icon (40px) + right content
- **Content:** Title (H4) + Badge row + Description (Body2)
- **Card padding:** 16px
- **Card border-radius:** 12px
- **Card border:** `1px solid var(--border)`
- **Hover:** Shadow Depth 2

### 8.3 Gradient Background Color Mapping

| Tool | Gradient Direction | Colors |
|---|---|---|
| AI Chat | 135deg | `#02CBFD` → `#133ED4` → `#17DADC` |
| AI Image Studio | 135deg | `#9652FF` → `#425BFF` → `#10DDFF` |
| AI Hub Mini | 135deg | `#1268FF` → `#00FFD4` |
| AI Notes | 135deg | `#6FEAF7` → `#52B9FF` |

---

## 9. Access Badge Component

Access restriction labels on tool cards. Not covered by main design system §51 Status or §54 Badge.

### 9.1 Structure
- **Composition:** Color dot (6px circle) + text label (H8, 12px)
- **Arrangement:** Horizontal inline-flex, gap 4px (dot to text) / gap 8px (between multiple badges)
- **Container:** No background, no border, pure inline element

### 9.2 Color Mapping

| Badge | Dot Color | Usage |
|---|---|---|
| PC Only | `#7E84FC` (Indigo-400) | Desktop browser only |
| Limited Access | `#F25194` (Magenta-500) | Requires special permissions |
| Office IP Only | `#1CBF7D` (Green-400) | Office network only |

### 9.3 Dark Mode
- Dot colors unchanged (400-step already has sufficient visibility on dark backgrounds)
- Text color uses `var(--text-secondary)`

---

## 10. Carousel / Banner Component

The main design system does not define a carousel component. This specifies the AI Hub top banner carousel.

### 10.1 Structure
- **Container:** Full width, border-radius 12px, `overflow: hidden`
- **Content:** Images or custom HTML content
- **Navigation buttons:** One circular button (28px) on each side, positioned at bottom-right of content
- **Button background:** `var(--primary)` (Primary Blue)
- **Button icon:** White arrows (‹ / ›)

### 10.2 Interaction
- **Auto-rotate:** Default 5-second interval, pauses on hover
- **Manual switch:** Click left/right buttons
- **Transition:** `opacity 0→1`, duration 300ms, `ease-out`

### 10.3 Indicators (Optional)
- **Type:** Bottom dots
- **Active:** `var(--primary)`, width 16px capsule shape
- **Inactive:** `var(--gray-400)`, 6px circle

---

## 11. Tab Anchor Scrolling

AI Hub Tab switching scrolls to corresponding sections. This supplements that behavior.

### 11.1 Behavior
- **Tab click:** Smooth scroll to corresponding section top, `scroll-behavior: smooth`
- **Scroll offset:** Reserve Header height (52px) as `scroll-margin-top`
- **Scroll listening:** Auto-update Active Tab on scroll (Intersection Observer)

### 11.2 Tab Indicator Animation
- **Active indicator bar:** Bottom 2px solid `var(--primary)`
- **Switch animation:** Indicator bar width and position use `transition: left 0.25s ease, width 0.25s ease`

---

## 12. My Space Page Components

My Space is a personal space page in the AI Chat sidebar, containing Assistant / Prompt / Document tabs.

### 12.1 Page Layout
- **Header:** Top-right Avatar + page title "My Space" (H1)
- **Tab Bar:** Follows main design system §16 Second Tab (Lite variant)
- **Action bar:** Below tabs, contains Create/Upload button + search field + sort button
- **Content area:** Scrollable, fills remaining height

### 12.2 Assistant Tab
- **Grouping:** "Shared from Others" collapsible group (with count, e.g., "(5)")
- **Collapse button:** Right-side arrow icon, `rotate(180deg)` indicates expanded
- **Card layout:** Vertical list, gap 12px

#### Assistant Card
- **Structure:** Left avatar (32px circle) + Title (H7) | Right More button (⋮)
- **Description:** Body4, max 2 lines, overflow `...` truncation
- **Author:** Body5, color `var(--text-tertiary)`, format "Created by {name}"
- **Avatar:** Image or AI icon (gradient background + white SVG)
- **Hover:** Shadow Depth 2, background unchanged
- **More button:** Hidden by default, shown on card hover (follows §27 Action Menu)

### 12.3 Prompt Tab
- **Action bar:** Create button (Primary) + search field + sort button
- **Empty state:** Follows main design system §14 Empty Status
  - Icon: Document + exclamation SVG
  - Title: "No Prompts Yet"
  - Description: "Create a prompt to get started."

### 12.4 Document Tab
- **Action bar:** Upload button (Primary) + New folder button (Secondary, with folder icon)
- **Search bar:** Search field + sort button + view toggle (Grid / List)
- **View toggle:** Follows main design system §20 Auxiliary Button — Selected behavior
  - Grid icon: 4-square grid
  - List icon: List
  - Active: `var(--primary)` fill
  - Inactive: `var(--text-tertiary)` stroke
- **Empty state:**
  - Title: "No Documents Yet"
  - Description: "Upload a document to get started."

### 12.5 General Rules
- **Search field:** Follows main design system §31 Text Field — Search variant, `max-width: 500px`
- **Sort button:** Quiet Action Button, click opens sort menu (follows §27 Action Menu)
- **Create/Upload button:** Primary Button, Medium (§18)
- **New folder button:** Secondary Button, Medium (§18), with folder + plus icon

---

## 13. Notes

- This document supplements `asus-design-system.md` and cannot be used independently
- Chat component Markdown rendering: recommend `marked.js` or `react-markdown` with custom renderers
- Code highlighting: recommend `highlight.js` or `Prism.js`
- Streaming text animation requires backend SSE (Server-Sent Events) or WebSocket
- All animations must respect `prefers-reduced-motion` user preference; disable non-essential animations when set to `reduce`
- Product Card gradient backgrounds are part of brand identity and must not be arbitrarily changed
- Access Badge color mappings are fixed rules; adding new badge types requires design review
