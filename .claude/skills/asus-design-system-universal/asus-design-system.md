# ASUS Internal System — Universal Design System & Component Specification

This document is the complete design system reference for ASUS internal system UIs. It covers colors, typography, shadows, layout grids, card hierarchy, dark mode rules, and 70+ component specifications. All components must support Light and Dark mode.

> **Usage Rule:** When generating or modifying ASUS internal system UI, strictly follow every rule in this document. Never guess or invent style values (e.g., button padding, grid spacing). All required values are documented here.

---

## 1. Visual Theme & Atmosphere

ASUS Internal System UI uses a professional, data-driven, high-functionality aesthetic designed for enterprise internal tools. It emphasizes clarity, structured information hierarchy, and high contrast. Full Light/Dark dual-mode theming is supported. AI features are visually distinguished with purple-blue gradient glows and rounded capsule-shaped borders.

---

## 2. Color System

### 2.1 Primary & Background Colors

| Token | Light | Dark | Usage |
|---|---|---|---|
| Primary | `#006CE1` | `#1389FC` | Primary interactive color |
| Secondary | `#002169` | — | Deep accent |
| Notice | `#005FD1` | `#37A2FC` | Secondary interactive color |
| Background White | `#FFFFFF` | `#0E1116` | Page base |
| Background Gray | `#F5F6F8` | `#17191D` | Secondary base |

### 2.2 Semantic Colors

| Role | Main | Light Tint |
|---|---|---|
| Informative | `#1389FC` | `#C4E4FF` |
| Positive | `#28A709` | `#BEEE9E` |
| Notice | `#EB6E00` | `#FFDD9A` |
| Negative | `#FF330B` | `#FFD6D6` |

> **Rule:** Semantic colors (Red / Orange / Green) do NOT change hue in Dark Mode.

### 2.3 Full Color Scale (Hues & Tints)

Each hue provides 11 steps from 900 to 050:

**Red**
900 `#5B0000` / 800 `#A10000` / 700 `#B61C1C` / 600 `#DB2828` / 500 `#FF330B` / 400 `#FF6E57` / 300 `#FFA79B` / 200 `#FFC7C7` / 100 `#FFD6D6` / 075 `#FFEBEB` / 050 `#FFF3F3`

**Orange**
900 `#401E00` / 800 `#7E3B00` / 700 `#A24B00` / 600 `#B75500` / 500 `#EB6E00` / 400 `#EF8624` / 300 `#F5AC5F` / 200 `#FBD299` / 100 `#FFEBC0` / 075 `#FFF1D1` / 050 `#FFF9E5`

**Yellow**
900 `#483300` / 800 `#5B4200` / 700 `#705200` / 600 `#856600` / 500 `#B59000` / 400 `#CAA500` / 300 `#E4C61F` / 200 `#F8D803` / 100 `#F8E96D` / 075 `#F9F4AF` / 050 `#F9F6D6`

**Chartreuse**
900 `#2A3800` / 800 `#3D5000` / 700 `#496000` / 600 `#628000` / 500 `#79A100` / 400 `#8AB800` / 300 `#A8D615` / 200 `#C1E83F` / 100 `#D8FB6B` / 075 `#E6FD9A` / 050 `#F4FFD4`

**Celery (Green-Yellow)**
900 `#0A3100` / 800 `#125A00` / 700 `#156C00` / 600 `#1A8400` / 500 `#28A709` / 400 `#53C22E` / 300 `#80D557` / 200 `#A2E57D` / 100 `#BEEE9E` / 075 `#DAF8C0` / 050 `#EEFFDF`

**Green**
900 `#073826` / 800 `#0A5236` / 700 `#0C6242` / 600 `#118357` / 500 `#15A36E` / 400 `#1CBF7C` / 300 `#72C8A8` / 200 `#95D6BD` / 100 `#ACDFCC` / 075 `#CFEDE2` / 050 `#E8F6F0`

**Seafoam**
900 `#013A34` / 800 `#03524B` / 700 `#03625B` / 600 `#058379` / 500 `#07A597` / 400 `#0EBCAC` / 300 `#69C8C1` / 200 `#8ED6D1` / 100 `#A8DFDB` / 075 `#CDEDE9` / 050 `#E6F6F4`

**Cyan**
900 `#013846` / 800 `#015066` / 700 `#015E79` / 600 `#017EA1` / 500 `#019ECA` / 400 `#0CB5E4` / 300 `#67C4DF` / 200 `#8CD4E8` / 100 `#A5DDED` / 075 `#CCEBF4` / 050 `#E6F4F9`

**Blue**
900 `#002169` / 800 `#1342CC` / 700 `#005FD1` / 600 `#006CE1` / 500 `#1389FC` / 400 `#37A2FC` / 300 `#7AC2FD` / 200 `#A5D6FE` / 100 `#C4E4FF` / 075 `#DDEFFF` / 050 `#EAF4FD`

**Indigo**
900 `#2B2D57` / 800 `#3F427E` / 700 `#4B4F97` / 600 `#6469CA` / 500 `#7E83FB` / 400 `#9C9EFD` / 300 `#B1B5FD` / 200 `#C4C8FD` / 100 `#D1D4FD` / 075 `#E4E6FD` / 050 `#F2F2FF`

**Purple**
900 `#3D2856` / 800 `#56387C` / 700 `#674495` / 600 `#8A5BC6` / 500 `#AE72F9` / 400 `#C497FF` / 300 `#CDAAFB` / 200 `#DBBFFB` / 100 `#E2CDFD` / 075 `#EFE2FD` / 050 `#F6F0FD`

**Fuchsia**
900 `#501C50` / 800 `#722874` / 700 `#892F8A` / 600 `#B83FBA` / 500 `#E650E8` / 400 `#EF95F0` / 300 `#F4AFF4` / 200 `#F6C1F6` / 100 `#F9DBF9` / 075 `#FDEDFD`

**Magenta**
900 `#541C34` / 800 `#792849` / 700 `#903159` / 600 `#C14175` / 500 `#F25093` / 400 `#FB7EAF` / 300 `#F697BF` / 200 `#F9B1CF` / 100 `#F9C1DA` / 075 `#FBDBE9` / 050 `#FDEDF4`

**Gray**
900 `#23252C` / 800 `#393C46` / 700 `#525665` / 600 `#676C7F` / 500 `#7D849B` / 400 `#A2A7BD` / 300 `#BBBFD4` / 200 `#D1D4E4` / 100 `#DFE1EF` / 075 `#EEEFF5` / 050 `#F5F6F8`

### 2.4 Transparent Black
Based on `#23252C`: 10% / 25% / 40% / 60% / 70% / 80% / 90% / 100%

---

## 3. Dark Mode — Complete Conversion Rules

Dark Mode is NOT a simple color inversion. Follow these precise mappings:

### 3.1 Backgrounds & Card Layers

| Light | → | Dark | Usage |
|---|---|---|---|
| `#FFFFFF` | → | `#0E1116` | Page base |
| `#F5F6F8` | → | `#17191D` | Secondary base / Canvas |
| Card Layer 1 (white) | → | `#1D1F26` | Card first layer ⭐ |
| Card Layer 2 (`#F5F6F8`) | → | `#26282F` | Card second layer / Floating elements |
| Drawer/Dialog inner | → | `#23252C` | Popup layer base |
| Mask/Overlay | → | `#000000` 80% opacity | Overlay mask |

### 3.2 Primary & Secondary Blues

| Light | → | Dark | Usage |
|---|---|---|---|
| `#006CE1` | → | `#006CE1` | Primary unchanged ⭐ |
| `#1389FC` | → | `#1389FC` | Unchanged |
| `#A5D6FE` | → | `#0B427F` | Light blue → deep blue ⭐ |
| `#C4E4FF` | → | `#0C2949` | Selected/highlight background |
| `#DDEFFF` | → | `#0C2949` | Very light blue |
| `#EAF4FD` | → | `#0E1116` | Extremely light blue |

### 3.3 Text & Icons

| Light | → | Dark | Usage |
|---|---|---|---|
| `#23252C` (Gray 900) | → | `#D1D4E4` | Primary text |
| `#676C7F` (Gray 600) | → | `#A2A7BD` | Secondary text |
| `#A2A7BD` (Gray 400) | → | `#676C7F` | Tertiary/weak text |
| `#7D849B` (Gray 500) | → | `#525665` | Disabled text |
| Pure white `#FFFFFF` | → | `#FFFFFF` | Stays unchanged |
| Disabled text/icon | → | `#0B427F` | Deep blue |

### 3.4 Neutral Grays & Borders (Inverted Scale)

| Light | → | Dark |
|---|---|---|
| `#F5F6F8` (Gray 50) | → | `#26282F` |
| `#EEEFF5` (Gray 75) | → | `#30333C` |
| `#DFE1EF` (Gray 100) | → | `#3F424D` / `#40434E` |
| `#D1D4E4` (Gray 200) | → | `#676C7F` |
| `#A2A7BD` (Gray 400) | → | `#7D849B` |
| `#7D849B` (Gray 500) | → | `#A2A7BD` |
| `#676C7F` (Gray 600) | → | `#BBBFD4` |
| `#525665` (Gray 700) | → | `#D1D4E4` |

### 3.5 Dark Mode General Rules
- Shadows use pure black `#000000` instead of `#002169`
- Primary color in Dark Mode uses `#1389FC`
- Disabled state colors adjust opacity based on the current layer
- Border color: `#3F424D` (replaces Light's `#DFE1EF`)
- Collaboration user colors: use 400-step of each hue (13 colors, cycle if >13 users)

### 3.6 Dark Mode Card Border Rules
Since shadows are less effective in Dark Mode, all elements needing visual boundaries should add `1px solid var(--border)`:

| Scenario | Light Mode | Dark Mode |
|---|---|---|
| Card Layer 1 (on Background) | No border, Shadow Depth 1 | `1px solid #3F424D`, no shadow |
| Card Layer 2 (on Card L1) | No border, shadow or bg color | `1px solid #3F424D`, bg `#26282F` |
| Floating (Dropdown/Popover) | Shadow Depth 3–4 | `1px solid #3F424D` + Shadow (`#000`) |
| Input container | `1px solid #DFE1EF` | `1px solid #3F424D` |

---

## 4. Typography

### 4.1 English — Roboto

**Headings (Line-height: 125%)**

| Level | Size | Weight |
|---|---|---|
| H1 | 36px | Bold |
| H2 | 30px | Regular |
| H3 | 24px | Regular |
| H4 | 20px | Regular |
| H5 | 18px | Regular |
| H6 | 16px | Regular |
| H7 | 14px | Regular |
| H8 | 12px | Regular |

**Body (Line-height: 150%)**

| Level | Size | Weight |
|---|---|---|
| Body1 | 20px | Regular |
| Body2 | 18px | Regular |
| Body3 | 16px | Regular |
| Body4 | 14px | Regular |
| Body5 | 12px | Regular |

### 4.2 Chinese — Microsoft JhengHei

**Headings (Line-height: 150%)**
Same sizes as English. H1 Bold, all others Regular.

**Body (Line-height: 175%)**
Same sizes as English. All Regular.

> **Rule:** In mixed CJK/Latin text, line-height follows the current language system standard. English text still uses Roboto.

---

## 5. Shadow System

| Depth | Usage | Light (X/Y/Blur/Color/Opacity) | Dark (X/Y/Blur/Color/Opacity) |
|---|---|---|---|
| 0 | Dialog inner | None | None |
| 1 | Normal | 0/1/6 `#7D849B` 10% | None |
| 2 | Hover | 0/1/6 `#002169` 30% | 0/1/6 `#000` 30% |
| 3 | Strong Hover | 0/6/20 `#002169` 25% | 0/15/50 `#000` 50% |
| 4 | Suspension | 0/15/50 `#002169` 35% | 0/15/50 `#000` 100% |

| Special Element | Light | Dark |
|---|---|---|
| Floating Button | 0/6/20 `#002169` 25% | 0/6/20 `#000` 50% |
| Tooltip | 0/8/6 `#002169` 25% | 0/6/8 `#000` 25% |

---

## 6. Grid & Layout System

### 6.1 Responsive 12-Column Grid

| Breakpoint | Viewport | Grid Margins (top-bottom / left-right) |
|---|---|---|
| XS | 320–730px | 16px / 16px |
| S | 731–1024px | 16px / 16px |
| M | 1025–1279px | 16px / 16px |
| L | 1280–1580px | 24px / 28px or 16px |
| XL | 1581–2560px | 24px / 28px |
| XXL | 2561px+ | 24px / 28px |

### 6.2 Column & Spacing Rules
- Grid Template: Always 12-column CSS Grid (`grid-cols-12`)
- Gutter (Gap): XS–M use 16px (`gap-4`); L–XXL use 24px (`gap-6`)
- Supports Fluid / Fixed / Offset layouts
- Main content grid is independent of Sidebar; 12 columns are based on remaining width after Sidebar

---

## 7. Card Hierarchy & Depth Semantics

The system uses strict physical layer stacking: **Background < Card Layer 1 < Card Layer 2**

### 7.1 UI Layer Architecture
- **Background (Level 0):** Light `#F5F6F8` / Dark very dark
- **Card Layer 1 (Level 1):** Light white / Dark `#1D1F26`
- **Card Layer 2 (Level 2):** Light `#F5F6F8` / Dark `#26282F`

### 7.2 Depth Semantic Mapping

| Depth | Usage | Light | Dark |
|---|---|---|---|
| 0 | Dialog (with overlay) | Flat card | Card Layer 1 |
| 1 | General content block | Shadow Depth 1 | Card Layer 1 |
| 2 | Hover effect | Shadow Depth 2 | Card Layer 2 |
| 3 | Clickable card / Toast / Tooltip | Shadow Depth 3 | Card Layer 2 |
| 4 | Floating (Lightbox / Popup / Nav) | Shadow Depth 4 | Card Layer 2 |

> In Dark Mode, layers are distinguished by surface brightness (Layer 2 is brighter than Layer 1), not just shadows.

---

## 8. Collaborative Editing Colors

- **Current user:** 2px solid `#005EFF` (Blue-500) border
- **Other users:** 2px solid random collaboration color (e.g., `#F56A41`, `#8BBD2E`, `#9C6ADE`), with white text name badge at top-right
- 13 hue-400 step colors for different users; cycles if >13 users

---

## 9. Table System

### 9.1 Row Height Specifications

| Type | Row Height | Font | Line-height | Padding | Ratio |
|---|---|---|---|---|---|
| Relaxed (Standard) | 70px | 14px | 1.5 (21px) | 24px | 1.7x |
| Standard (Compact) | 50px | 14px | 1.5 (21px) | 14px | 1.0x |
| Compact (Mini) | 40px | 14px | 1.5 (21px) | 10px | 0.7x |
| Minimum | 34px | 12px | 1.5 (18px) | 8px | 0.7x |

> When table cells contain controls (input/button), shrink to 0.75x. Column overflow uses 0.75x height.

### 9.2 Table Container & Header
- **Container:** Rounded corners, soft diffused shadow, white background
- **Dual-layer header:** Column Groups (centered) + Column Titles (light gray background, left-aligned)
- **Data rows:** White background, near-black text, thin light gray horizontal dividers
- **Hover:** Full row highlight
- **Overflow:** Text truncation with ellipsis

### 9.3 Column Resize
- **Normal:** 1px solid `#E6E6E6`, cursor Default
- **Hover:** 2px solid `#4094F7`, cursor `col-resize`
- **Dragging:** Maintains Hover style, real-time width adjustment
- Content overflow uses CSS `text-overflow: ellipsis`

### 9.4 Freeze Panes
- Supports freezing action column fixed to table right side
- Frozen column has vertical divider/shadow
- Divider disappears when scrolled to far right

### 9.5 Dark Mode Table
- Background: Deep charcoal (#121212 approx), row backgrounds slightly brighter
- Border Radius: Container ~12px, Input ~6px, Status Pill fully rounded
- Checkbox Active color is Azure Blue, supports Indeterminate state

---

## 10. Draggable List

### Structure & Style
- **Container:** White `#FFFFFF`, 1px solid `#E0E0E0`, border-radius ~8px
- **Header row:** Medium gray text `#8A8A8A`, bottom 1px solid `#E0E0E0`
- **Item rows:** White, 1px solid `#E0E0E0` horizontal dividers
- **Status Pill:** border-radius 100px, white text on green `#52C41A`
- **Table Input:** White, 1px solid `#CCCCCC`, ~4px radius

### Drag Interaction
- **Normal:** Standard white background
- **Hover:** Row background turns light gray
- **Click & Drag:** 2px solid blue outline
- **Dragging:** Semi-transparent + shadow, blue outline maintained, 2px solid blue horizontal line indicates insertion point, original position shows dashed border placeholder
- **Drag constraint:** Only triggered from first column drag handle (`⋮⋮`), other columns do not trigger drag

---

## 11. Tree Structure Table

- **Level 1 (Parent):** Main category, expand/collapse arrow on right
- **Level 2 (Sub-group):** Nested group
- **Level 3 (Item):** Final data level
- **Indentation:** 24–32px per level
- **Connector lines:** Vertical and L-shaped lines connecting child rows to parent
- **Drag sorting:** Same-level only, cross-level forbidden. Drag and column sorting cannot coexist
- **Light:** Parent rows white, child rows light gray `#F0F2F5`
- **Dark:** Parent rows `#1E1E1E`, child rows `#252525`

---

## 12. Multiple Select Editing Table

- **Current selection:** Solid blue border
- **Copied:** Dashed blue border
- **Multi-select box:** Solid blue border surrounding group
- **Selection background:** Semi-transparent light blue fill
- **Drag handle:** Bottom-right 4–6px blue square
- **Drag-to-Fill:** Drag handle vertically applies values, solid blue frame previews range

---

## 13. Bulk Editing Table

- **Trigger:** Click header Checkbox (select all) or row Checkbox
- **Control bar (Sticky):** Bulk editing toolbar fixed at top of viewport
- **Close:** Click "X" or non-selected area
- **Default state:** Toolbar dropdown defaults to "Select"

---

## 14. Empty State

- **Content max-width:** 400px, wraps if exceeded
- **Popover / Drawer:** Horizontally and vertically centered, padding 24px (top-bottom) / 28px (left-right)
- **Table:** Horizontally and vertically centered, min-height 300px, padding 24px (top-bottom) / 28px (left-right)

---

## 15. Scrollbar

| Size | Sensor Area | Usage |
|---|---|---|
| Medium | 12px | Small containers, Popup, Menu |
| Large | 16px | Main content area, full page scroll |

- **Normal:** Hidden or very faint
- **Mouse over content / Scrolling:** Visible (thin bar)
- **Mouse over scrollbar / Holding:** Thicker (high contrast)
- **Start spacing:** Menu/Popup 10px, Content/Table/Full page 0px
- Supports Vertical / Horizontal

---

## 16. Segmented Control / Tabs Bar

### Types
- **Main Tab:** Primary navigation, Active = blue text + thick blue underline
- **Second Tab:** Secondary navigation, all-caps, Active = blue text + thin blue underline
- **Editable Tab:** Custom tabs, supports Add (+), Rename (Min width 65px), Duplicate, Delete, Set as Default

### States & Limits
- **States:** Default (gray text) / Hover (blue text) / Selected (blue text + indicator bar)
- **Text limit:** Max 30 characters, overflow `...` truncation, hover shows full text
- **Notification Badge:** Solid blue circle + white text, positioned right of tab
- **Extend:** When tabs exceed container width, provide Options dropdown

---

## 17. Tabs Tools

- **Sizes:** 1x (Standard) / 0.75x (Small)
- **Types:** Icon Only / Icon + Text / Text Only
- **Limit:** Use Segmented Control when >10 options
- **States:** Default / Hover / Active / Disabled

---

## 18. Standard Button

### Variants
- **Primary:** Solid blue background, white text
- **Secondary:** Blue outline, blue text, transparent/white background
- **Secondary White:** White outline, white text — only used on solid blue backgrounds
- **Tertiary:** Text + icon only, no border, no background

### Sizes

| Size | Height | Padding | Font |
|---|---|---|---|
| Small (0.75x) | 32px | 16px horizontal | 14px |
| Medium (1x) | 40px | 24px horizontal | 16px |
| Large (1.25x) | 48px | 32px horizontal | 18px |
| Extra-Large (1.5x) | 56px | 40px horizontal | 20px |

> Extra-Large is restricted to Login/Authentication pages only.

### Interaction States
- **Normal:** Standard colors
- **Hover:** Primary blue darkens; Secondary/Tertiary get very light blue background
- **Active:** Deepest blue
- **Disabled:** ~40% opacity, light gray background, gray-blue text, cursor `not-allowed`
- **Loading:** Text disappears, replaced by three animated height-varying loading bars, button not clickable

### Dark Mode Buttons
- **Normal:** Maintains high-contrast Primary Blue
- **Disabled:** Converts to deep gray-blue `#0B427F` or `#40434E`
- **Loading:** Light gray/white animated indicator

### Layout Rules
- **Flexible Width:** Default auto-fits text width
- **Full-Width:** Can use `w-full` to fill parent container
- **Text Overflow:** Fixed-width buttons wrap text, no ellipsis
- **border-radius:** 30px (capsule shape)

---

## 19. AI Button

> **Rule:** AI Primary Button and Standard Primary Button must NEVER appear on the same screen.

### Variants
- **Primary:** Solid gradient fill
- **Secondary:** Outline (ghost) style

### Sizes
- Small (0.75x) / Medium (1x, Default) / Large (1.25x)

### CSS Specification
```css
.btn-glowing {
  border-radius: 30px;
  padding: 10px;
  color: #FFFFFF;
  background-image: linear-gradient(to right, #9652FF, #006CE1, #9652FF, #9652FF);
  background-size: 400%;
}
.btn-glowing:hover {
  animation: gradientMove 7s linear infinite;
}
@keyframes gradientMove {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
```

---

## 20. Auxiliary Button

- **Primary:** Solid dark gray fill
- **Secondary:** Gray outline
- **Selected:** Toggle behavior (turns blue), must include "cancel this state" functionality
- **Sizes:** Small (0.75x, Default) / Medium (1x)
- **Overflow:** Wrap to new line or Collapse to "..." menu when space is insufficient

---

## 21. Action Button

- **Highlight:** Icon inside circular background
- **Quiet:** Standalone icon, no background (Table / Normal)
- **Reverse:** For use on dark UI elements
- **Sizes:** Small (0.75x) / Medium (1x, Default)
- **Highlight states:** Normal = light gray circle + black icon → Hover = very light blue circle + blue icon → Active = light blue circle + blue icon

---

## 22. Close Button

- **Sizes:** Medium (1x, Default) / Extra-Large (1.5x)
- **Light:** Dark icon (Normal/Hover), light gray icon (Disabled)
- **Dark:** White icon (Normal/Hover), gray icon (Disabled)

---

## 23. Floating Button

- **Types:** Normal (circular "+") / With label and icon (capsule) / With label (capsule)
- **Light:** Circular = blue background + white icon; Capsule = white background + blue text + shadow
- **Dark:** Circular = blue background + white icon; Capsule = transparent/dark gray background + Primary Blue text
- **Hover:** Blue deepens and saturates
- **Shadow:** Depth 3

---

## 24. Text Link

- Underline only when link is not sufficiently obvious
- **Types:** Standard / With Icon (Forward: Text > / Backward: < Text)
- **Light:** Primary Blue text, Hover adds underline
- **Dark:** Light cyan/blue text, Hover adds underline

---

## 25. Floating Actions

- Table row hover reveals action buttons
- **Order:** Most common action on left
- **Limit:** Max 2 primary function buttons + 1 "More" button
- **Scenario A (overlapping content):** No column header, fixed right, overlaps existing column content
- **Scenario B (non-overlapping):** Appears when scrolled to far right, creates dedicated space
- **Button Hover:** Icon turns Primary Blue, shows Tooltip (Light = dark background / Dark = light background)

---

## 26. Freeze Actions

- Action column fixed to table right side
- **Limit:** Max 2 function buttons + 1 "More" button
- Frozen column has vertical divider/shadow, disappears when scrolled to far right
- **Button Hover:** Circular background (Light = light blue / Dark = deep blue) + Tooltip

---

## 27. Action Menu

- **Types:** Icon only / Mix (icon + text)
- Uses Popover presentation, NOT dropdown menu
- **Icon consistency:** Items with and without icons must be separated by horizontal dividers
- **Hover (Delete):** Text and icon turn red
- **Disabled:** ~40% opacity

---

## 28. Switch / Toggle

- **Label position:** Right title / Left title / Standalone
- **States:** Open (blue track, white ball right) / Close (gray track, white ball left) / Focus (blue outer glow) / Disabled
- **Sizes:** Medium (1x, Default) / Small (0.75x)
- **Dark Mode Disabled Off special rule:** Ball color replaces with Layer 1 background color

---

## 29. Checkbox

- **States:** Unchecked (empty square) / Checked (solid blue + white checkmark) / Indeterminate (solid blue + white dash) / Focus (light blue halo)
- **Sizes:** Small (0.75x) / Medium (1x, Default)
- **Label position:** Top / Left
- **Arrangement:** Vertical / Horizontal
- **Validation:** Required red asterisk / Error red text
- **Group:** Supports Select All parent logic (Indeterminate when partially selected)

---

## 30. Radio Button

- **States:** Normal = gray circle outline (unselected) / Blue filled circle (selected) / Focus = light blue halo
- **Sizes:** Small (0.75x) / Medium (1x, Default)
- **Label position:** Top / Left
- **Arrangement:** Vertical / Horizontal
- **Validation:** Required red asterisk / Error red text
- **Alignment:** Vertical options must left-align with title text start position

---

## 31. Text Field

- **Label position:** Top / Left
- **States:** Normal / Focus / Typing / Has Value / Disabled / Not editable
- **Types:** Standard / With icon / Search
- **Sizes:** Small (0.75x) / Medium (1x, Default) / Extra-Large (1.5x, Login only)
- **Dynamic width:** Single input can expand width based on placeholder character count
- **Search mode:** Automatic (instant) / Manual (requires Enter/button)
- **Character limit:** Counter placed at far right of label row (e.g., /200)
- **Error:** Red border + red asterisk + red text
- **Search placeholder:** Width adapts to input field width
- **Clear:** Press Enter or click clear button

---

## 32. Floating Text Field

- Used for inline editing within tables
- Press Enter or click outside to confirm
- **Horizontal limit (Editable Tab):** Normal max 30 characters, overflow `...`; Typing expands horizontally to browser edge
- **Vertical limit (Complex forms):** Normal fixed width, no height limit, text wraps and expands vertically

---

## 33. Text Area

- **Label position:** Top / Left
- **States:** Normal / Focus / Typing / Has Value / Disabled / Not editable
- **Features:** Scrollbar / Help text / Drag resize / Word Restriction / Required / Error Message
- **Error:** Red border + red error text

---

## 34. Dropdown Bar

- **Label position:** Top / Left / No label
- **Variants:** Standard / Quiet / With icon / With Tags / Time Variant
- **States:** Normal / Hover / Open/Focus / Has Value / Disabled
- **Sizes:** Small (0.75x) / Medium (1x, Default)
- **Width rules:** Standalone dropdown expands dynamically; grouped/inline dropdown has fixed width
- **Icon color:** Arrow and leading icon must sync color changes with text
- **Error:** Red border + red error text

---

## 35. Dropdown Menu

- **Option height:** min-height 42px
- **Option padding:** 8px (top-bottom) / 20px (left-right)
- **Menu width:** Min 140px / Max 400px, width follows longest text
- **Text overflow:** Auto-wraps beyond 400px, line-height 18px
- **Max height:** 440px, scrollbar appears when exceeded
- **Menu top-bottom padding:** 28px (24px top when search bar present)
- **Option spacing:** 24px
- **Alignment:** Default left-aligned to dropdown bar
- **Browser edge protection:** Min 28px horizontal / 24px vertical spacing from edge; right-aligns or opens upward when necessary
- **Hover:** Light blue-gray background
- **Selected/Active:** Solid blue background + white text, arrow points up

---

## 36. Nested Dropdown Menu

- Supports Tag + Search bar
- **Search:** Keyword search for Level 1 / Number search for Level 2
- **Width:** Level 1 Min 230px / Max 400px, Level 2 width matches Level 1
- **Scrollbar:** Level 1 max 8 items / Level 2 max 9 items
- **Positioning:** Level 2 defaults to right of Level 1, opens left when hitting edge
- **Tag format:** #Number [Content] gray rounded frame

---

## 37. Pinned Dropdown Menu

- **Unpinned:** Star icon hidden
- **Hover:** Gray outline star appears
- **Pinned:** Item moves to top above divider, star turns solid blue
- Contains search/filter input, selected items get light blue background

---

## 38. Multiple Dropdown Menu

- Contains Checkbox multi-select + Search bar + Scroll bar
- **Sorting:** Selected items auto-move to top
- **Truncation:** Selected names in dropdown bar truncate when too wide
- **Select All:** Checkbox placed below search bar
- **Search Bar:** Fixed at top, scrollbar starts below search bar
- **Width:** Min 250px / Max 400px
- **Height:** Max 400px
- **Uneven distribution warning:** Orange text, Assign button enabled, disappears after 3 seconds
- **Invalid selection:** Red text, Assign button Disabled

---

## 39. Accordion

- **Types:** Title Inside (self-contained) / Title Outside (grouped multi-card)
- **Spacing:** 40px between groups / 24px between main title and first card / 24px between cards in same group
- **Expanded:** Up arrow (∧), content visible
- **Collapsed:** Down arrow (∨), content hidden

---

## 40. Side Headers & Navigation

This pattern completely replaces top navigation bars as the primary layout backbone for complex internal systems.

### Dual-Column Side Navigation Architecture
1. **Side Header (dark blue narrow left rail):** System logo, user avatar, notification bell, cross-system switch icons
2. **Navigation Menu (main menu):** Current site's primary content menu

### Expand/Collapse
- **Expanded:** Full width, shows site name, search/filter, icons with text
- **Collapsed:** Text hidden, hover icon shows dark Tooltip, dark blue side header remains visible

### Hierarchy
- Single level (icon + text)
- Single level with headers (gray non-clickable title grouping)
- Multi-level (accordion expand, sub-level light blue background)

### Interaction States
- **Normal:** Standard layout
- **Hover:** Row background turns light gray
- **Selected/Active:** Icon and text turn blue, light blue highlight background, left solid blue vertical indicator bar
- **Text overflow:** Must wrap, NEVER use ellipsis, max two lines
- **Popup trigger:** Click notification/search triggers Popover

---

## 41. Top Headers & Navigation

### Architecture
- **Pattern A (low option count):** Top horizontal navigation only
- **Pattern B (high option count):** Top + standard sidebar (L-shaped layout; this Sidebar does NOT include the dark blue Side Header)

### Global Function Order (right side, left to right)
Search → Notification bell (red dot badge) → Language/Region → User avatar

### Dropdown Menus
- **Single level:** Standard vertical list
- **Multi-level (Fly-out):** Right arrow hint, hover/click expands second level (text only, not e-commerce image Mega Menu)
- **Width:** Min 140px / Max 400px, wraps if exceeded, line-height 18px
- **Selected/Active:** Solid blue background + white text
- **Browser edge protection:** Reverses direction (opens left) when near right edge

---

## 42. Fullscreen Bar

### Components (left to right)
Back to Home → Page Title → Form Input → Status Indicator → Secondary Actions (Outline) → Primary Action (Solid Blue)

### Responsive Spacing
- **XL (1581–2560px):** Left-right margin 28px, element gap 14px
- **L (1280–1580px):** Left-right margin 16px, element gap 10px

---

## 43. Pagination

- **≤9 pages:** Show all, edge arrows Disabled
- **≥10 pages:** Start `1 2 3 4 5 ... N` / Middle `1 ... X-1 X X+1 ... N` / End `1 ... N-4 N-3 N-2 N-1 N`
- **Ellipsis:** Not clickable
- **Normal:** Black text, blue arrows
- **Hover:** Turns Primary Blue
- **Selected:** Primary Blue text + light blue background (10–15% opacity)

---

## 44. Sort

- Table header dual-arrow icon
- **Normal:** Dual arrows neutral color
- **Ascending:** Up arrow blue
- **Descending:** Down arrow blue
- **Disabled:** Gray
- **Sort logic:** Text abc < xyz / Numbers 0 < 9 / Dates past < present < future

---

## 45. Popover

- Non-modal container, anchored to source element
- **Alignment:** Top-Left/Right or Bottom-Left/Right
- **Border-radius:** 12px–16px
- **Shadow:** Soft diffused
- **Content:** Header (avatar/name/role) + Divider + Action Items

---

## 46. Drawer

- **Direction:** Push left / Push right
- **Header & Footer fixed:** Footer fixed at bottom, Header can scroll away
- **Overlay min margin:** 100px
- **Dark Mode:** Uses Layer 1 background color `#23252C`
- **Scrollbar:** Follows Scrollbar guideline

---

## 47. Dialog

- **Width:** Min 450px / Max 700px
- **Background overlay:** Dark semi-transparent
- **Close:** Top-right "X"
- **Button limit:** Max 3
- **Button position:** Primary on far right
- **Button hierarchy:** Primary (solid blue) / Secondary/Tertiary (outline blue)
- **Overflow stacking:** Buttons stack vertically, Primary at bottom

---

## 48. Tooltip

- **Max width:** 140px, wraps if exceeded
- **Sizes:** Small (0.75x) / Medium (1x, Default)
- **Trigger delay:** hover 500ms
- **Position:** Top / Bottom / Left / Right, auto-flips when insufficient space
- **Light:** Dark gray background `#212121`, white text
- **Dark:** Light gray background `#E0E0E0`, dark text

---

## 49. Tutorial

- **Min width:** 150px, dynamic height
- **Content:** Description + Buttons (required), Title + Image (optional)
- **Buttons:** Max 2 (Back + Next), with step indicator (e.g., "1/2")
- **First step: Next only. Last step: Back only.**
- **Trigger:** 500ms delay
- **Position:** Same as Tooltip logic, supports auto-flip

---

## 50. Toast Notification

- **Types:** Text (Icon + Title + multi-line description + Close) / Actionable (Icon + single line + text action + Close)
- **Semantic variants:** Informative (Blue) / Positive (Green) / Notice (Orange) / Negative (Red)
- **Position:** Bottom Center (default) / Bottom Right / Top Center / Top Right
- **Margin:** 40px from screen edge
- **Stacking:** Bottom appearance pushes upward, top appearance pushes downward
- **Limit:** Max 2 visible simultaneously
- **Auto-dismiss:** 5000ms (hover pauses timer, 1000ms after mouse leaves)
- **With close button:** Manual close
- **Consecutive triggers:** Previous toast disappears immediately, new one delays 1000ms

---

## 51. Status Label

### Types
- **Clickable:** Solid capsule background + text
- **Non-clickable:** Color dot + text

### Semantic Colors
- **Active (Blue):** Online, Published
- **Approved (Green):** Success, Complete
- **Testing (Orange):** Pending, Planned
- **Error (Red):** Failed, Rejected
- **Offline (Gray):** Draft, Paused, Deleted

### Non-semantic Variants
Use hues from the color system

- **Sizes:** Small (0.75x) / Medium (1x, Default)
- **Layout:** Flexible width / Justified
- **Dark Mode:** Clickable uses dark semi-transparent background + brightened text/dot
- Supports Disabled state

---

## 52. Alert Banner

- **Semantic variants:** Informative / Positive / Notice / Negative
- **Structure:** Status Icon (left) + Message + Close "X" (right)
- **Alignment:** All elements vertically centered
- **Overflow:** Container height expands with multi-line text, icon stays vertically centered
- **Dark Mode:** Banner background keeps light pastel to maintain high contrast

---

## 53. Stepper

- **Types:** Editing (numbered steps) / Checking (checkmark/error icons)
- **Current step:** "Double Circle" (outer halo) indicator
- **Active:** Primary Blue or status color + halo, bold text
- **Completed:** Green checkmark `#28C76F`
- **Alert/Warning:** Red exclamation `#FF3B30`
- **Inactive:** Light = light gray `#D1D1D6` / Dark = dark gray `#3A3A3C`

---

## 54. Badges

- **Basic:** Circular, single digit
- **Maximum Width:** Capsule shape, cap at "99+"
- **Warning:** Circular white exclamation mark
- **Position:** Anchored to parent container top-right
- **Color:** Count = red background / Warning = orange background / White text
- **Static Variant:** Light blue background + white text (for use on blue elements)

---

## 55. Avatar

- **Sizes:** 75 / 100 / 125 / 150 / 175 / 200 / 250 / 300 (commonly 75 / 100 / 200)
- **Display:** Image / Name initials
- **Self (current user):** Fixed Blue 500
- **Other users:** Randomly assigned from 13 hue-400 colors, cycles if >13
- **Group display:** Horizontal overlapping stack, white stroke separator (Dark Mode = dark stroke)

---

## 56. Loading Indicator

- Three vertical bars with height-varying animation + "Basic motion"
- **Medium (1x):** Buttons, tables, single objects
- **Extra-Large (1.5x, Default):** Full page, Dialog, Popup
- **Default:** Blue bars on transparent background
- **Over Background:** Blue bars inside solid blue block (buttons only)
- **Single Object:** Light blue/low-saturation bars (table/list rows)

---

## 57. Help Text

- **Types:** General description (light gray text) / Error text only (red text) / Error Icon + text (red triangle exclamation + red text)
- **Sizes:** Small (0.75x, Default) / Medium (1x)
- **Icon position:** Immediately left of text

---

## 58. Breadcrumbs

- **Level 1 is not displayed**
- **Separator:** ">"
- **Current page (last level):** Disabled light gray, not clickable
- **Hover:** Active links turn blue

---

## 59. Slider

- **Track:** ~4px height, fully rounded
- **Thumb:** Circular ~16–20px, 1px stroke
- **Text Field (optional):** Placed on right, ~4px radius
- **Active Track / Hover Thumb:** `#0056D2`
- **Inactive Track:** Light `#EAECF0` / Dark `#333333`
- **Behavior:** Real-time update, bidirectional sync with Text Field, click-to-jump

---

## 60. Divider

- 1px solid line
- **Types:** Fixed/Partial Width / Full Width/Fluid
- **Direction:** Horizontal (standard) / Vertical
- **Light:** Light gray (high transparency/low saturation)
- **Dark:** Gray-white (high contrast)

---

## 61. Mandatory Symbol

- Asterisk * marks required fields
- **Min size:** 18px (asterisk stays 18px even when text is 14px)
- **Spacing:** Fixed 2px from text
- **Color:** Red in both Light and Dark modes

---

## 62. Tag Picker

### Single Tag
- **States:** Default (dark background + white text + "X") / Hover (background brightens) / Suggest (light gray background + dark text, no "X") / All Tags (Disabled grayed out)
- **Sizes:** Standard (1x) / Small (0.75x)
- **Special variants:** With Avatar / Label (non-interactive)
- **Dark:** Default = dark gray background + white text / Suggest = darker gray outline + light text

### Dropdown Container
- **Capacity:** Max 4 tags (x/4)
- **Input behavior:** Enter adds tag / ESC closes but retains text
- **Duplicate prevention:** "+ Add new tag" Disabled when matching existing tag
- **Text limit:** Max 68 characters (2 lines), overflow `...` + hover tooltip
- **Search Bar:** Fixed at top (sticky)
- Supports drag-to-reorder

### Tag Picker in Table
- Supports selection limit (e.g., Select up to 4 tags)
- Contains Scrollbar, Search bar fixed at top

---

## 63. Drop Files or Images

- **Border:** Dashed in all states
- **Default:** Light = light gray border/text / Dark = dark gray border/text
- **Dragging:** Border and background turn Primary Blue
- **Disabled:** Reduced opacity
- **Required:** Red asterisk
- **Help Text:** Size/format/file size/quantity limits
- **Detailed specs:** border-radius 8px, main padding ~40px, file item spacing 8–12px, thumbnail ~48x48px 4px radius

---

## 64. File Upload Progress (Loading Bar)

- **Choose File:** Filename + size + Close (X), hover darkens background
- **Uploading:** Blue progress bar left-to-right, percentage text, Close (X) cancels
- **Done:** Progress bar disappears, hover shows Delete (Trash)
- **Error:** Red progress bar + "Upload Failed" red text, Retry & Cancel (hover turns blue)
- **Wrong Format:** 0% red/gray progress bar + red warning text
- **Padding:** 12–16px, progress bar 2–4px height

---

## 65. Add Assets

### Simple Version
- **Default:** Dashed gray border + gray "+" icon
- **Hover:** Dashed blue border + blue "+", uploaded images show "X" delete button
- **Disabled:** Low opacity dashed, thumbnail covered with semi-transparent overlay
- **Uploading:** Blue vertical progress bar
- **Dragging:** Blue vertical line indicates drop position
- **Aspect ratio:** 1:1 square, border-radius 8–10px
- **Video thumbnail:** Centered Play icon

### Multi-function Version
- **Width:** 288px (example)
- **Structure:** Image area + input fields + bottom action bar
- **Single upload only**
- **Hover:** Dark semi-transparent overlay + action buttons (Edit / Preview / Delete)
- **Buttons:** Max 3, min 1
- **Dragging:** Card lifts + shadow, light blue placeholder

---

## 66. Progress Ring

- **Full Size:** Large ring + percentage + main value (e.g., 325/500) + label
- **Table Size:** Single-line inline (value/total > mini ring > percentage)
- **Color rules:** Use non-semantic colors only (Blue / Cyan / Teal / Indigo / Purple), NEVER use Red / Green / Orange
- **Animation:** Use react-motion transitions

---

## 67. Version Control

- **Minor Versions:** Auto-save every 5 minutes
- **Major Versions:** Grouped every 10 minutes
- **Restore:** Creates new entry marked "Restore version"
- **Author display:** 1 person = full name / 2 = both names / 3–10 = first name + "and X users" / 11+ = first name + "and 10+ users"
- **10 history entries per page**
- **Active State:** Left thick blue vertical bar + solid blue icon + Overflow menu

---

## 68. Date Picker

- **Types:** Pick date (single) / Pick range (dual segment, ">" separator)
- **Focus:** Border and calendar icon turn blue, placeholder becomes `0000/00/00`
- **Active:** Light = black text / Dark = white text, calendar icon stays blue
- **Width:** Default Fixed, can Fill to adapt
- **Format:** `YYYY/MM/DD`

---

## 69. Color Picker

- **Fill types:** Solid / Gradient
- **Container:** White background, border-radius ~24px, inner ~8px, input ~4–6px
- **Drag handle:** 6-dot (2x3) at top
- **Padding:** ~20–24px
- **Tab Switcher:** Solid vs Gradient, Active = light gray background `#EDF2F7`
- **Gradient Angle Slider:** Active blue `#007AFF`
- **Color selection area:** Saturation/brightness square + Hue rainbow slider + Opacity checkerboard slider
- **Footer:** Eyedropper tool + Hex input + Alpha percentage

---

## 70. Universal Size Scale

Most components support these sizes:
- **Small / 0.75x:** Compact scenarios
- **Medium / 1x:** Default size
- **Large / 1.25x:** Emphasis scenarios
- **Extra-Large / 1.5x:** Special scenarios only (full-page Loading, Login buttons, etc.)

---

## 71. Notes

- This document was extracted from design PDF files; some visual details (exact border-radius, icon styles, animation curves) should reference the original Figma/design files
- Color values may have ±1 variance due to color space conversion (e.g., `#006CE1` vs `#006BE1`)
- All component Dark mode styles are mandatory and must not be omitted
- When generating code, both Light and Dark mode must be implemented simultaneously (e.g., Tailwind `dark:` prefix)
- Non-compliance with this document will result in UI/QA review failure
