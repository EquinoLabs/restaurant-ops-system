# Agent Guidelines & Frontend Skills Scoping

UI work in platform-admin is visual only: do not change API calls, data logic, or behavior unless asked.

## 1. Design System Authority & Scope
- `docs/design/DESIGN.md` is the absolute source of truth for UI and styling. On any conflict between a skill's recommendations and `docs/design/DESIGN.md`, **DESIGN.md always wins**.
- **Live Operations Exception:** In `apps/business-manager`, views meeting the operational criterion of active, real-time floor or kitchen service (current examples: `KDSView.tsx`, `TableSelectorGrid.tsx`, `StaffOrdersView.tsx`) are permitted a high-contrast dark theme (`bg-slate-950`), pulse urgency badges, and touch targets >= 44px per `docs/design/DESIGN.md`.

---

## 2. Installed Skills Matrix

| Skill | `customer-web` | `business-manager` | `platform-admin` |
| :--- | :--- | :--- | :--- |
| **`animate`** | **USE** (drawer slides, quantity pops, modal entries) | **LIMITS** (<= 200ms, KDS bumps & tabs, no bounce) | **LIMITS** (<= 150ms enter-only CSS slide/fade on mount; synchronous unmount on close preserved; no bouncy springs) |
| **`animation-performance`** | **USE** (60fps on budget Android phones) | **USE** (KDS 1s timer ticks & 10s auto-refresh) | **NO** (near-static admin tables) |
| **`apple-design`** | **LIMITS** (fluid touch momentum & sheets; no blur/glass) | **LIMITS** (tablet POS ergonomics only; no glassmorphism) | **NO** (conflicts with flat light-mode rules) |
| **`break-ui`** | **USE** (long dish names, 0-item carts, emojis) | **USE** (large KDS queues, 50+ table grids, long notes) | **USE** (visual layout stress-testing only: long tenant names, audit logs, extreme INR) |
| **`emil-design-eng`** | **USE** (tactile buttons, drawer mechanics, optical balance) | **USE** (tablet tactile feel, active states, focus halos) | **LIMITS** (focus rings, tnum figures, active states; no novelty/flair) |
| **`mobile-native`** | **USE** (100vh fix, iOS Safari <16px zoom fix, tap flash) | **LIMITS** (touch targets >= 44px, tap highlight; tablets only) | **NO** (desktop-only governance console) |
| **`pick-ui-library`** | **LIMITS** (lightweight helpers like carousels; no UI suites) | **LIMITS** (charts for sales/settlement, drag-and-drop tables) | **NO** (pure CSS visual work only; no external UI or chart libraries) |

---

## 3. On-Demand Skills
Not installed; copy from the global skills folder when needed. Same DESIGN.md limits per app apply: `ask-sonner`, `prototype`, `review-animations`, `improve-animations`, `find-animation-opportunities`, `animation-vocabulary`.

---

## 4. Incompatible Skills (Do Not Use in This Repository)
- **`animate-expo`:** Targets React Native / Expo. This codebase is entirely Vite + React web applications.
- **`write-swift`:** Targets Swift / SwiftUI. This codebase contains only TypeScript and Python.
- **`reverse-engineer-anything`:** Binary decompilation tool. This is a first-party source code repository.
