# Design Foundations

**Status:** Phase 1. Describes the visual and interaction system actually implemented in `frontend/`, not aspirational later-phase UI (chat bubbles, artifact rendering, citations) which will extend this document as it ships.

## Visual direction

The product should read as a serious productivity tool, not a demo chatbot. Concretely, that meant deliberately avoiding:

- Purple/blue gradient "AI startup" hero treatments.
- Oversized rounded chat bubbles and cartoonish avatars.
- Decorative animation that doesn't communicate state.

And deliberately choosing:

- A neutral slate/warm-white base palette with a single confident accent (a deep teal/green, `--color-primary`), used sparingly for primary actions and active states - closer to the restraint of tools like Linear or Notion than to a consumer AI product.
- System font stack (`ui-sans-serif, system-ui, ...`) for fast, native-feeling text rendering without an external font request.
- Flat surfaces with a single subtle border/shadow language rather than heavy glassmorphism or skeuomorphism.

## Design tokens

All colors are defined as HSL channel triples in CSS custom properties (`frontend/src/index.css`) and exposed to Tailwind v4 via `@theme inline`. This means:

- Every color has a light-mode value on `:root` and a dark-mode override, both under `@media (prefers-color-scheme: dark)` and under an explicit `[data-theme="dark"]` attribute set by the in-app theme toggle.
- Components never hard-code hex values - they use semantic Tailwind classes like `bg-surface`, `text-muted`, `border-border` that resolve through the tokens.
- Radii (`--radius-sm` through `--radius-xl`) and the two font stacks (`--font-sans`, `--font-mono`) are tokenized the same way, so a future rebrand is a token edit, not a find-and-replace across components.

## UX principles

1. **Never fake functionality.** Where a feature isn't implemented yet (sending a message, viewing an artifact), the UI says so explicitly (tooltip, empty-state copy) rather than silently doing nothing or pretending to work.
2. **Every state is designed, not accidental.** Empty, loading, disabled, and error states are first-class components (`EmptyState`, `Spinner`, disabled variants on `Button`/`Textarea`), not afterthoughts.
3. **Restraint over decoration.** Transitions are short (150-200ms) opacity/color changes tied to real state changes (hover, focus, open/close) - no motion added purely for spectacle.

## Information architecture

Three-pane shell, reflecting the target product (conversational assistant + artifact viewer) from day one, even though the middle two panes are placeholders in Phase 1:

- **Left - Navigation**: product identity, "new conversation," conversation history (empty state today), and secondary navigation (knowledge base, settings - both marked "Later phase" and disabled) plus the theme toggle.
- **Center - Chat workspace**: welcome/empty state with suggested prompts (fill the composer, do not send), and the message composer itself.
- **Right - Artifact panel**: reserved, styled, and labeled for the artifact viewer that ships in a later phase, so it never feels bolted on when it arrives.

## Responsive strategy

Built mobile-first with Tailwind's `lg` (1024px) breakpoint as the split between "all three panes visible" and "single-column with slide-over panels":

- **Desktop (≥1024px)**: sidebar, chat, and artifact panel all visible simultaneously in a fixed three-column grid. The artifact panel can be collapsed via a header toggle to give the conversation more room.
- **Tablet / mobile (<1024px)**: sidebar and artifact panel become accessible Radix `Dialog`-based slide-over sheets, triggered from a header hamburger and panel-toggle button respectively, so navigation and artifact access remain one tap away without permanently consuming screen space from the conversation.

## Accessibility principles

- All interactive elements are real `<button>`/`<input>`/`<textarea>` elements with visible `:focus-visible` rings (a 2px ring using the `--color-ring` token, contrast-checked against both themes).
- Icon-only buttons (hamburger, panel toggle, dialog close) carry `aria-label`; toggle buttons expose `aria-pressed` where they represent a binary state.
- The mobile sidebar/artifact sheets are Radix `Dialog` primitives, which provide focus trapping, `Escape`-to-close, and `aria-modal` semantics for free; each sheet has a (visually hidden) `DialogTitle` so screen readers announce its purpose.
- Disabled controls (e.g. the send button) remain perceivable and explain themselves via an accessible tooltip rather than disappearing or offering no explanation.
- Color is never the only signal: status badges pair a dot with text; disabled state pairs reduced opacity with `disabled`/`aria-disabled` semantics.

## Interaction quality

- **Composer**: always typeable; suggested prompts populate it directly so the empty state and the composer feel connected, not like two separate widgets.
- **Send button**: disabled with an explanatory tooltip ("Sending connects once the agent layer ships in a later phase") - honest about Phase 1 scope rather than simulating a response.
- **Panel toggles**: desktop artifact-panel collapse and mobile sheets both use the same underlying components (`Dialog` for mobile, conditional render for desktop), keeping the codebase from needing two separate systems for "showing" a panel.
