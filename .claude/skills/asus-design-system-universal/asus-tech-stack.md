# ASUS Internal System — Tech Stack & Implementation Guide

This document defines the default technology stack and implementation conventions for ASUS internal system UI projects. All design values in this file are derived directly from `asus-design-system.md`. When in conflict, `asus-design-system.md` is the single source of truth.

---

## 1. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Framework | React | 18.x |
| Language | JSX (not TypeScript unless requested) | — |
| Build Tool | Vite | 6.x |
| Styling | CSS Custom Properties + vanilla CSS | — |
| Font Loading | Google Fonts CDN | — |
| Package Manager | npm | — |

> **No Tailwind CSS.** All styling uses CSS custom properties (design tokens) and vanilla CSS. Dark mode is toggled via `data-theme="dark"` attribute, not Tailwind `dark:` prefix.

---

## 2. Project Structure

```
project-name/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── styles.css          # Design tokens + global styles
│   └── components/         # Only when needed
```

### Rules
- Small projects / prototypes: Everything in `App.jsx` + `styles.css`
- Extract to `src/components/` only when a component is reused or exceeds ~150 lines
- Do NOT create empty folders (`utils/`, `hooks/`, `services/`, `types/`)
- Single stylesheet: `styles.css`

---

## 3. Design Tokens (CSS Custom Properties)

All values below come from `asus-design-system.md`. Reference the section number for each group.

### 3.1 Light Mode (`:root`)

```css
:root {
  /* §2.1 Primary & Background */
  --primary: #006CE1;
  --secondary: #002169;
  --notice: #005FD1;
  --bg-white: #FFFFFF;
  --bg-gray: #F5F6F8;

  /* §2.2 Semantic Colors */
  --informative: #1389FC;
  --positive: #28A709;
  --notice-semantic: #EB6E00;
  --negative: #FF330B;
  --informative-light: #C4E4FF;
  --positive-light: #BEEE9E;
  --notice-light: #FFDD9A;
  --negative-light: #FFD6D6;

  /* §7.1 Surfaces & Card Layers */
  --surface: #FFFFFF;
  --surface-secondary: #F5F6F8;
  --card-l1: #FFFFFF;
  --card-l2: #F5F6F8;

  /* §3.3 Text & Icons */
  --text-primary: #23252C;    /* Gray 900 */
  --text-secondary: #676C7F;  /* Gray 600 */
  --text-tertiary: #A2A7BD;   /* Gray 400 */
  --text-disabled: #7D849B;   /* Gray 500 */

  /* §3.4 Borders */
  --border: #DFE1EF;          /* Gray 100 */

  /* §3.1 Overlay */
  --overlay: rgba(35, 37, 44, 0.60);  /* §2.4 Transparent Black 60% */

  /* §5 Shadow System — Depth 1–4 */
  --sh1: 0 1px 6px rgba(125, 132, 155, 0.10);   /* #7D849B 10% */
  --sh2: 0 1px 6px rgba(0, 33, 105, 0.30);       /* #002169 30% */
  --sh3: 0 6px 20px rgba(0, 33, 105, 0.25);      /* #002169 25% */
  --sh4: 0 15px 50px rgba(0, 33, 105, 0.35);     /* #002169 35% */
  --sh-float: 0 6px 20px rgba(0, 33, 105, 0.25); /* Floating Button */
  --sh-tooltip: 0 8px 6px rgba(0, 33, 105, 0.25);/* Tooltip */

  /* §2.3 Blue Scale (full 11-step) */
  --blue-900: #002169; --blue-800: #1342CC; --blue-700: #005FD1;
  --blue-600: #006CE1; --blue-500: #1389FC; --blue-400: #37A2FC;
  --blue-300: #7AC2FD; --blue-200: #A5D6FE; --blue-100: #C4E4FF;
  --blue-075: #DDEFFF; --blue-050: #EAF4FD;

  /* §2.3 Gray Scale (full 11-step) */
  --gray-900: #23252C; --gray-800: #393C46; --gray-700: #525665;
  --gray-600: #676C7F; --gray-500: #7D849B; --gray-400: #A2A7BD;
  --gray-300: #BBBFD4; --gray-200: #D1D4E4; --gray-100: #DFE1EF;
  --gray-075: #EEEFF5; --gray-050: #F5F6F8;

  /* §2.3 Purple Scale (for AI features — see §19 AI Button) */
  --purple-700: #674495; --purple-600: #8A5BC6;
  --purple-500: #AE72F9; --purple-400: #C497FF;

  /* §2.3 Other hue scales — add from asus-design-system.md §2.3 as needed */
  --cyan-500: #019ECA; --cyan-400: #0CB5E4;
  --red-500: #FF330B; --orange-500: #EB6E00; --celery-500: #28A709;
}
```

### 3.2 Dark Mode (`[data-theme="dark"]`)

All mappings from `asus-design-system.md` §3.1–§3.5:

```css
[data-theme="dark"] {
  /* §3.2 Primary */
  --primary: #1389FC;

  /* §3.1 Backgrounds & Card Layers */
  --bg-white: #0E1116;
  --bg-gray: #17191D;
  --surface: #0E1116;
  --surface-secondary: #17191D;
  --card-l1: #1D1F26;
  --card-l2: #26282F;

  /* §3.3 Text (inverted gray scale) */
  --text-primary: #D1D4E4;    /* was Gray 900 → Gray 200 */
  --text-secondary: #A2A7BD;  /* was Gray 600 → Gray 400 */
  --text-tertiary: #676C7F;   /* was Gray 400 → Gray 600 */
  --text-disabled: #525665;   /* was Gray 500 → Gray 700 */

  /* §3.4 Borders */
  --border: #3F424D;           /* was Gray 100 → custom dark */

  /* §3.1 Overlay */
  --overlay: rgba(0, 0, 0, 0.80);

  /* §3.5 Shadows — use pure black instead of #002169 */
  --sh1: none;
  --sh2: 0 1px 6px rgba(0, 0, 0, 0.30);
  --sh3: 0 15px 50px rgba(0, 0, 0, 0.50);
  --sh4: 0 15px 50px rgba(0, 0, 0, 1.00);
  --sh-float: 0 6px 20px rgba(0, 0, 0, 0.50);
  --sh-tooltip: 0 6px 8px rgba(0, 0, 0, 0.25);
}
```

### 3.3 Token Usage Rules
- Always use `var(--token)`, never hardcode hex in component CSS
- Add hue scale tokens (Red, Orange, Green, etc.) from §2.3 only when the component needs them
- Shadow tokens `--sh1`–`--sh4` map to Shadow Depth 1–4 from §5

---

## 4. Dark Mode Toggle

### 4.1 Mechanism
Use `data-theme` attribute on `<html>`:

```jsx
const [theme, setTheme] = useState('light');

useEffect(() => {
  document.documentElement.setAttribute('data-theme', theme);
}, [theme]);

const toggleTheme = () => setTheme(prev => prev === 'light' ? 'dark' : 'light');
```

### 4.2 System Preference Detection (Optional)
```jsx
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const [theme, setTheme] = useState(prefersDark ? 'dark' : 'light');
```

---

## 5. Base CSS Reset & Global Styles

From §4 Typography: font-family `Roboto` + `Microsoft JhengHei`, Body4 = 14px, CJK body line-height = 175%.
From `asus-ai-chat-patterns.md` §5: focus-visible keyboard-only ring.

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #root { height: 100%; }

/* §4.1 Typography — Body4 default, CJK line-height 175% */
body {
  font-family: 'Roboto', 'Microsoft JhengHei', sans-serif;
  background: var(--bg-gray);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 175%;
}

/* §5.1 Focus Ring — keyboard only (asus-ai-chat-patterns.md §5) */
*:focus { outline: none; }
*:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

/* Reduced motion — required by design system §71 */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 6. Typography CSS Classes

Derived from §4.1 (English) and §4.2 (Chinese):

```css
/* §4.1 Headings — Roboto, line-height 125% */
.h1 { font-size: 36px; font-weight: 700; line-height: 125%; }
.h2 { font-size: 30px; font-weight: 400; line-height: 125%; }
.h3 { font-size: 24px; font-weight: 400; line-height: 125%; }
.h4 { font-size: 20px; font-weight: 400; line-height: 125%; }
.h5 { font-size: 18px; font-weight: 400; line-height: 125%; }
.h6 { font-size: 16px; font-weight: 400; line-height: 125%; }
.h7 { font-size: 14px; font-weight: 400; line-height: 125%; }
.h8 { font-size: 12px; font-weight: 400; line-height: 125%; }

/* §4.1 Body — Roboto, line-height 150% */
.body1 { font-size: 20px; line-height: 150%; }
.body2 { font-size: 18px; line-height: 150%; }
.body3 { font-size: 16px; line-height: 150%; }
.body4 { font-size: 14px; line-height: 150%; }
.body5 { font-size: 12px; line-height: 150%; }

/* §4.2 CJK override — line-height 150% headings, 175% body */
:lang(zh) .h1, :lang(zh) .h2, :lang(zh) .h3,
:lang(zh) .h4, :lang(zh) .h5, :lang(zh) .h6,
:lang(zh) .h7, :lang(zh) .h8 { line-height: 150%; }

:lang(zh) .body1, :lang(zh) .body2, :lang(zh) .body3,
:lang(zh) .body4, :lang(zh) .body5 { line-height: 175%; }
```

---

## 7. Button CSS

From §18 Standard Button — capsule shape, 4 sizes, 4 variants, 5 states.

```css
/* §18 Layout Rules — border-radius 30px capsule */
.btn {
  border-radius: 30px;
  font-family: inherit;
  cursor: pointer;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 200ms cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* §18 Sizes */
.btn--small  { height: 32px; padding: 0 16px; font-size: 14px; }  /* 0.75x */
.btn--medium { height: 40px; padding: 0 24px; font-size: 16px; }  /* 1x */
.btn--large  { height: 48px; padding: 0 32px; font-size: 18px; }  /* 1.25x */
.btn--xl     { height: 56px; padding: 0 40px; font-size: 20px; }  /* 1.5x — Login only */

/* §18 Primary — solid blue, white text */
.btn--primary {
  background: var(--primary);
  color: #FFFFFF;
}
.btn--primary:hover { background: var(--blue-700); }  /* §18 Hover: blue darkens */
.btn--primary:active { background: var(--blue-900); } /* §18 Active: deepest blue */

/* §18 Secondary — blue outline, blue text */
.btn--secondary {
  background: transparent;
  color: var(--primary);
  border: 1px solid var(--primary);
}
.btn--secondary:hover { background: var(--blue-050); } /* §18 Hover: very light blue bg */

/* §18 Tertiary — text + icon only */
.btn--tertiary {
  background: transparent;
  color: var(--primary);
  border: none;
}
.btn--tertiary:hover { background: var(--blue-050); }

/* §18 Disabled — ~40% opacity, light gray bg, gray-blue text, not-allowed */
.btn:disabled {
  opacity: 0.4;
  background: var(--gray-075);
  color: var(--text-disabled);
  cursor: not-allowed;
  border-color: transparent;
}

/* §19 AI Button — gradient, NEVER on same screen as Primary */
.btn--ai {
  border-radius: 30px;
  color: #FFFFFF;
  background-image: linear-gradient(to right, #9652FF, #006CE1, #9652FF, #9652FF);
  background-size: 400%;
  border: none;
}
.btn--ai:hover {
  animation: gradientMove 7s linear infinite;
}
@keyframes gradientMove {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
```

---

## 8. Scaffold Templates

### 8.1 index.html

From §4.1: Roboto font via Google Fonts CDN.

```html
<!DOCTYPE html>
<html lang="zh-Hant">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PROJECT_NAME</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### 8.2 package.json

```json
{
  "name": "project-name",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.0"
  }
}
```

### 8.3 vite.config.js

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
```

### 8.4 src/main.jsx

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

---

## 9. Naming Conventions

### 9.1 Files
- Components: `PascalCase.jsx` (e.g., `ChatMessage.jsx`, `Sidebar.jsx`)
- Styles: single `styles.css`, or `kebab-case.css` if split
- No `.tsx` unless TypeScript is explicitly requested

### 9.2 CSS Classes
- `kebab-case` (e.g., `.chat-message`, `.sidebar-nav`)
- Prefix with component name (e.g., `.toast-container`, `.toast-text`)
- BEM-like modifiers when needed (e.g., `.btn--primary`, `.btn--small`)

### 9.3 React Components
- Functional components only (no class components)
- Hooks: `useState`, `useEffect`, `useRef`
- Props destructuring in function signature
- Event handlers: `handle` prefix (e.g., `handleClick`, `handleSubmit`)

### 9.4 CSS Custom Property Naming
- Semantic: `--primary`, `--text-primary`, `--border`, `--surface`
- Scale: `--{hue}-{step}` (e.g., `--blue-500`, `--gray-100`)
- Shadow: `--sh{depth}` (e.g., `--sh1`, `--sh2`)
- Component-specific (if needed): `--{component}-{property}` (e.g., `--btn-radius: 30px`)

---

## 10. Additional Libraries

Add only when the feature requires it. Do NOT pre-install.

| Need | Library | Design System Reference |
|---|---|---|
| Markdown rendering | `react-markdown` + `remark-gfm` | `asus-ai-chat-patterns.md` §2.3 |
| Code highlighting | `highlight.js` or `prism-react-renderer` | `asus-ai-chat-patterns.md` §2.2 |
| Animation | `framer-motion` | `asus-ai-chat-patterns.md` §4 |
| Icons | `@phosphor-icons/react` (Regular weight) | `asus-ai-chat-patterns.md` §3.1 |
| Date picking | `react-datepicker` | `asus-design-system.md` §68 |
| Charts | `recharts` | `asus-design-system.md` §66 |

---

## 11. Pre-Generation Checklist

Before delivering generated code, verify:

- [ ] `index.html` loads Roboto from Google Fonts (§4.1)
- [ ] `styles.css` contains full `:root` and `[data-theme="dark"]` token sets (§2, §3)
- [ ] Base CSS reset included (§4)
- [ ] `prefers-reduced-motion` media query included (§71)
- [ ] `focus-visible` styles included (`asus-ai-chat-patterns.md` §5)
- [ ] All colors use `var(--token)`, zero hardcoded hex in component CSS
- [ ] Dark mode toggle uses `data-theme` attribute (§3)
- [ ] `border-radius: 30px` on all standard buttons (§18)
- [ ] Both Light and Dark mode visually correct (§3)
- [ ] AI Button and Standard Primary Button never on same screen (§19)
