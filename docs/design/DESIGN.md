---
name: Operations Console
colors:
  canvas: '#F6F7F9'
  surface: '#FFFFFF'
  border: '#E3E6EA'
  divider: '#EEF0F3'
  text-primary: '#1F2933'
  text-secondary: '#616E7C'
  text-disabled: '#9AA5B1'
  accent: '#2554C7'
  accent-hover: '#1D44A6'
  accent-active: '#183A8F'
  accent-focus: 'rgba(37, 84, 199, 0.24)'
  status-active-bg: '#E6F4EC'
  status-active-text: '#1B7F4B'
  status-pending-bg: '#FFF4DB'
  status-pending-text: '#8A5A00'
  status-critical-bg: '#FDECEA'
  status-critical-text: '#B42318'
  status-neutral-bg: '#EEF0F3'
  status-neutral-text: '#52606D'
  error: '#B42318'
typography:
  display-page-title:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-section:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  headline-card:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  body-default:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-medium:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  table-cell:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  table-header:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  caption-regular:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  caption-medium:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  badge-label:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.01em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 16px
  gutter-desktop: 24px
  margin: 16px
  margin-desktop: 24px
  space-xs: 4px
  space-sm: 8px
  space-md: 16px
  space-lg: 24px
  space-xl: 32px
---

## Brand & Style

This design system establishes an ultra-efficient, dense internal control panel tailored for administrative consoles, multi-unit governance, and operational dashboards (`apps/platform-admin` and restaurant back-office management).

### Visual Archetype & Mood
- **Style:** High-density, utilitarian SaaS administrative interface drawn from the structural precision of Stripe Dashboard, Zendesk, and Shopify Admin.
- **Tone:** Methodical, neutral, unambiguous, and quiet. The interface acts as a silent frame for high-velocity operational data.
- **Mode:** Exclusively light mode for administrative portals. No dark themes, ambient glows, heavy drop shadows, decorative cards, glassmorphism, or expressive novelty elements.
- **Iconography:** Monoline 16px and 20px geometric icons exclusively, rendered in the secondary text tone `#616E7C` with a uniform 1.5px stroke. Never use emojis, saturated badges, or decorative graphic fills.
- **Utility Motion:** Subtle, composite-only CSS transitions (<= 150ms ease-out) are permitted for overlay enter states (slide-over drawers sliding from right, dialogs scaling 0.98 to 1.0, tab panels fading opacity). To maintain synchronous testability and immediate responsiveness, unmounting on close remains instantaneous with no delayed exit animations.

### Operational Exception: Live Service & Floor Operations (apps/business-manager)
The strict "Operations Console" light-mode and compact-geometry rules are waived for views that meet the criterion of **active, real-time service operations** (current examples include kitchen display station `KDSView.tsx`, floor plan table grid `TableSelectorGrid.tsx`, and handheld order entry `StaffOrdersView.tsx`):
1. **High-Contrast Dark Canvas:** Permitted a dark theme (`bg-slate-950` / `bg-slate-900` with `border-slate-800`) to maximize glanceability and minimize glare on kitchen displays and mobile tablets in diverse restaurant lighting.
2. **Urgency & Status Badges:** Time-critical items may use saturated status highlights (emerald, amber, red, purple) and motion cues (such as `animate-pulse` on kitchen tickets delayed >20m) to command immediate staff attention.
3. **Touch-First Sizing:** Interactive buttons, ticket bump actions, and table selector cells must maintain touch targets >= 44px (waiving the standard 32px desktop button limit) to ensure reliable tap input on tablets and touchscreens.

## Colors

Color is applied with surgical restraint. The base canvas remains cool and neutral, reserving high-contrast saturation strictly for primary actions, navigational indicators, and critical lifecycle alerts.

### Canvas & Structural Surfaces
- **App Canvas:** `#F6F7F9` (Strict neutral ground for all viewports).
- **Surface / Card Background:** `#FFFFFF` (Content containers, data tables, sheets, and drawers).
- **Base Border:** `#E3E6EA` (1px solid delimiter across all structural edges, cards, headers, and rows).
- **Divider Secondary:** `#EEF0F3` (Sub-element dividers within nested lists or forms).

### Typography Tones
- **Primary Body & Headings:** `#1F2933` (High legibility, dark slate tone).
- **Secondary / Supporting Text:** `#616E7C` (Muted labels, metadata, captions, column headers).
- **Disabled Text:** `#9AA5B1` (Non-interactive elements and read-only placeholder states).

### Accent & Interaction
- **Brand Accent:** `#2554C7` (Restricted to primary button fills, text links, active navigation indicator bars, and keyboard focus outlines).
- **Accent Hover:** `#1D44A6` (Primary action hover state).
- **Focus Ring:** `rgba(37, 84, 199, 0.24)` (2px outer halo with 1px base offset).

### Semantic Status Palette
Status pills and indicators employ soft-tint surfaces with high-contrast text:
- **Active / Operational:** Surface `#E6F4EC`, Text `#1B7F4B`.
- **Trial / Pending / Past Due:** Surface `#FFF4DB`, Text `#8A5A00`.
- **Suspended / Failed / Critical:** Surface `#FDECEA`, Text `#B42318`.
- **Inactive / Neutral / Cancelled:** Surface `#EEF0F3`, Text `#52606D`.

## Typography

The typography is built entirely on `Inter` with fallback to native system sans-serif fonts. It prioritizes rapid scannability and structural density.

### Typographic Principles
- **Weights:** Strictly limited to `400` (Regular), `500` (Medium), and `600` (Semi-Bold). Weights outside this range (e.g. 300, 700, 800) are forbidden.
- **Numbers & Metrics:** Must consistently use tabular numeric figures (`font-feature-settings: 'tnum' on, 'cv05' on`) to ensure perfect vertical alignment in accounting lists, inventory counts, and data tables.
- **Financial Formatting:** Currencies are formatted in INR using the standard symbol `₹` without extra space before the integer (e.g., `₹14,580.00`). For values exceeding 1,00,000, use standard Indian numbering system grouping (`en-IN` format, e.g. `₹1,50,000.00`).
- **Date Formatting:** High-density tables display compact dates as `DD MMM YYYY` (e.g., `14 Oct 2026`) with tabular figures. Detail drawers, event audits, and inspection panels may display full timestamps as `DD MMM YYYY, HH:mm`.

## Layout & Spacing

A disciplined 8px baseline grid governs all screen layouts, with a 4px sub-grid reserved for tight component metrics (table cell padding, badge horizontal offsets, icon margins).

### Grid & Breakpoints
- **Shell Structure:** Persistent vertical navigation sidebar (fixed width: `240px`, collapsible to `64px` icon-only), persistent header bar (height: `48px`), and fluid content canvas.
- **Content Bounds:** Primary admin views fill 100% of available viewport width up to a max content boundary of `1440px` centered within the content viewport.
- **Desktop (≥ 1280px):** 12-column grid, `24px` margins, `24px` gutters.
- **Tablet (768px – 1279px):** 8-column grid, `16px` margins, `16px` gutters.
- **Mobile (< 768px):** 4-column fluid reflow, `16px` margins, `12px` gutters. Tables shift to horizontally scrollable viewports with sticky key columns.

## Elevation & Depth

Depth is established via structural nesting and clean linear division rather than cast shadows.

### Border Hierarchy
- Surface boundaries rely on a crisp `1px solid #E3E6EA`.
- Cards, table wrappers, search bars, and modals utilize this identical border value to create a unified, low-elevation plane.

### Elevation Levels
- **Level 0 (Flat):** Cards, content sections, and tables sitting flush on `#F6F7F9` background with `1px solid #E3E6EA` borders. Zero shadow.
- **Level 1 (Popover / Dropdown):** Action dropdowns, date pickers, filter menus.
  - Border: `1px solid #E3E6EA`
  - Shadow: `0px 2px 4px rgba(31, 41, 51, 0.04), 0px 4px 8px rgba(31, 41, 51, 0.06)`
- **Level 2 (Modal / Dialog / Slide-over Drawer):** Critical overlay tasks.
  - Border: `1px solid #E3E6EA`
  - Shadow: `0px 8px 16px rgba(31, 41, 51, 0.08), 0px 16px 24px rgba(31, 41, 51, 0.06)`
  - Scrim: `rgba(31, 41, 51, 0.40)` without blur.

## Shapes

The interface maintains a restrained, architectural aesthetic with controlled, small-radius corners across all interactive components.

### Radius Specifications
- **Standard Radius:** `6px` (`roundedness: 1`). Applied uniformly across cards, buttons, text inputs, dropdown menus, filter bars, and modal containers.
- **Status Pills:** `4px` or `9999px` strictly allowed for small badges. For compact rectangular table badges, `4px` is preferred to maintain rigid vertical data alignment.
- **Prohibited:** Any radius exceeding `8px` is strictly banned for functional containers and surfaces. Circular avatars are limited strictly to user profiles at `24px` or `32px` dimensions.

## Components

### Buttons
All buttons have a strict fixed height of `32px` with horizontal padding of `12px` and a corner radius of `6px`. Font is `13px` weight `500`.
- **Primary:** Background `#2554C7`, text `#FFFFFF`, border `none`. Hover: `#1D44A6`. Active: `#183A8F`.
- **Secondary / Default:** Background `#FFFFFF`, text `#1F2933`, border `1px solid #E3E6EA`. Hover: `#F6F7F9` background, `#E3E6EA` border.
- **Destructive:** Background `#FFFFFF`, text `#B42318`, border `1px solid #FDECEA`. Hover: `#FDECEA` background.
- **Ghost / Tertiary:** Background `transparent`, text `#616E7C`, border `none`. Hover: `#F6F7F9` background, text `#1F2933`.

### Data Tables
The central operational component for restaurant management.
- **Row Height:** Exact `40px` height.
- **Padding:** `0 12px` horizontal padding per cell.
- **Header:** Height `36px`, background `#F6F7F9`, border bottom `1px solid #E3E6EA`. Text is `12px`, weight `600`, color `#616E7C`.
- **Cell Content:** Typography `13px` Inter, color `#1F2933`.
- **Row Hover:** Background `#F6F7F9` transition 100ms ease.
- **Dividers:** `1px solid #E3E6EA` bottom border per row.
- **Cell Overflow:** Data cells must preserve the exact 40px row height without multi-line expansion. Text columns subject to overflow (e.g. tenant or outlet names) must use single-line CSS truncation (`truncate`) and supply the complete string in a native `title` attribute for native browser hover inspection.

### Status Badges & Pills
- **Geometry:** Height `20px`, horizontal padding `6px`, corner radius `4px`.
- **Typography:** `11px` Inter, weight `500`, uppercase tracking disabled. Labels should be rendered in Title Case for uniform readability.
- **States:**
  - *Active:* Text `#1B7F4B`, Background `#E6F4EC`.
  - *Trial / Past Due:* Text `#8A5A00`, Background `#FFF4DB`.
  - *Suspended / Failed:* Text `#B42318`, Background `#FDECEA`.
  - *Inactive / Cancelled:* Text `#52606D`, Background `#EEF0F3`.

### Input Fields & Controls
- **Text Inputs:** Fixed height `32px`, padding `0 10px`, font `13px` Inter, background `#FFFFFF`, border `1px solid #E3E6EA`, corner radius `6px`.
  - Focus state: Border `#2554C7`, outer box-shadow `0 0 0 2px rgba(37, 84, 199, 0.24)`.
- **Checkboxes & Radios:** `16px × 16px`, border `1px solid #CBD2D9`, background `#FFFFFF`. Checked state: background `#2554C7`, border `#2554C7`. Radius: `3px` for checkbox, `50%` for radio.

### Cards & Surfaces
- **Card Styling:** Background `#FFFFFF`, border `1px solid #E3E6EA`, radius `6px`, padding `16px`. Shadows are omitted by default.
- **Card Header:** Height `40px`, bottom border `1px solid #EEF0F3`, padding `0 16px`, featuring `14px` weight `600` title.

### Metric / KPI Blocks
- Condensed summary blocks used in operational dashboards.
- Layout: Subdued caption title (`12px` `#616E7C`), metric value (`20px` weight `600` `#1F2933`, tabular figures), supporting change badge (`11px` status pill) arranged with an `8px` vertical gap.

### Technical Metadata & Payloads
- Raw JSON or technical traces (such as audit log metadata) must be rendered in 12px monospace (`font-mono text-xs`), contained in a `#F6F7F9` surface with a `1px solid #E3E6EA` border, with CSS `whitespace-pre-wrap break-all` and a constrained max-height scroll viewport.