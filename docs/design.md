# Design Foundations

**Status:** Phase 1 + 2 + 3. Describes the visual and interaction system actually implemented in `frontend/`, not aspirational later-phase UI (artifact rendering, real source citations, token streaming) which will extend this document as it ships.

## Visual direction

The product should read as a serious productivity tool with a distinct editorial identity - not a demo chatbot, and not a generic ChatGPT clone. Concretely, that meant deliberately avoiding:

- Purple/blue gradient "AI startup" hero treatments.
- Oversized rounded chat bubbles and cartoonish avatars.
- Decorative animation that doesn't communicate state.
- A literal audio-player UI as the nod to "podcast" - the product is about the *knowledge*, not about playing episodes.

And deliberately choosing:

- A neutral slate/warm-white base palette with a single confident accent (a deep teal/green, `--color-primary`), used sparingly for primary actions and active states - closer to the restraint of tools like Linear or Notion than to a consumer AI product. Validated against the UI Pro Max design-system tool's "Productivity Tool" palette match (teal primary + orange-adjacent accent family), rather than its default landing-page suggestion (an indigo/purple "Dark Mode (OLED)" pattern), which would have reintroduced the exact generic-AI-startup look the brief asks to avoid.
- A second, editorial display typeface (Fraunces, a soft-serif) layered on top of the Inter-based UI sans, used sparingly for moments that should feel written rather than "app-generated": the empty-state headline, the sidebar wordmark, and source-card episode titles. This follows the "Classic Elegant" serif+sans pairing pattern (serif headline, sans UI) rather than going all-serif, which would fight the density a chat/sidebar UI needs.
- Flat surfaces with a single subtle border/shadow language rather than heavy glassmorphism or skeuomorphism.

## Design tokens

All colors are defined as HSL channel triples in CSS custom properties (`frontend/src/index.css`) and exposed to Tailwind v4 via `@theme inline`. This means:

- Every color has a light-mode value on `:root` and a dark-mode override, both under `@media (prefers-color-scheme: dark)` and under an explicit `[data-theme="dark"]` attribute set by the in-app theme toggle.
- Components never hard-code hex values - they use semantic Tailwind classes like `bg-surface`, `text-muted`, `border-border` that resolve through the tokens.
- Radii (`--radius-sm` through `--radius-xl`), the two font stacks (`--font-sans`, `--font-mono`), and the Phase 2 editorial stack (`--font-serif`) are tokenized the same way, so a future rebrand is a token edit, not a find-and-replace across components.
- `--font-serif` (Fraunces, loaded via Google Fonts with `display=swap` so it never blocks text rendering) is applied narrowly via `font-serif` utility classes - it is not the default body font anywhere.

## UX principles

1. **Never fake functionality.** Where a feature isn't implemented yet (retrieval grounding, an artifact), the UI says so explicitly (composer helper text, the system prompt's own honesty about not having transcript access) rather than silently doing nothing or pretending to work. Suggested prompts are clearly interactive UI chips, not answers - clicking one populates the composer, it never displays canned "AI" output. The "thinking" state (below) communicates progress without ever exposing hidden model reasoning.
2. **Every state is designed, not accidental.** Empty, loading, disabled, generating, and error states are first-class components (`EmptyState`, `Skeleton`, `Spinner`, `ThinkingIndicator`, `GenerationErrorCard`), not afterthoughts - see "Loading and error states" below for the full inventory.
3. **Restraint over decoration.** Transitions are short (150-200ms) opacity/color changes tied to real state changes (hover, focus, open/close, active session, generating) - no motion added purely for spectacle. The "thinking" indicator is a static waveform glyph with a subtle pulse, not a spinner theatrics show.

## Editorial / podcast identity

Because the product is grounded in podcast/newsletter knowledge, a few restrained visual cues carry that identity without fabricating content that doesn't exist yet:

- **`WaveformIcon`** (`components/ui/waveform-icon.tsx`): a small, static bar-equalizer glyph used in the empty state instead of a generic sparkle/star icon. It's deliberately not animated and not a media control - it reads as an icon, not as "press play."
- **`SourceCard`** (`components/ui/source-card.tsx`): a real episode/newsletter citation (title, guest, source type, excerpt, link), now (Phase 4) rendered under any grounded assistant message via `MessageBubble`, driven entirely by the API's `Source[]` shape - no default props, so it still can't be wired up with placeholder/fabricated content. When the source repository has no URL for an episode, the card renders as a plain (non-link) card rather than fabricating a "View source" link.
- **Empty-state copy** ("Product thinking, growth, and leadership - in conversation") frames the product around expert conversations without claiming a specific episode, guest, or quote exists yet.
- **`ProviderIndicator`** (`components/layout/provider-indicator.tsx`): a small, always-honest "which model is answering this?" readout in the sidebar footer - a colored dot plus text (never color alone), reflecting the backend's real `GET /api/provider` response. It's deliberately subdued (text-xs, muted color) so it informs without competing with the conversation for attention.
- **Product-oriented copy discipline**: user-visible strings say "Thinking through that…" rather than "Calling agent…" or "Model invocation" - developer/implementation language never leaks into the product surface. The one exception is the composer's own honesty about scope ("Answers aren't grounded in Lenny's podcast archive yet"), which is a product-truth disclosure, not internal jargon.

## Information architecture

Three-pane shell, reflecting the target product (conversational assistant + artifact viewer):

- **Left - Navigation**: product identity, "New conversation," and now a **real conversation history** grouped into Today / Yesterday / Earlier (`lib/session-grouping.ts`), each item showing its title and a relative timestamp, with an active-session indicator. Secondary navigation (knowledge base, settings - both marked "Later phase" and disabled) and the theme toggle remain below it.
- **Center - Chat workspace**: the product-specific welcome state (with suggested prompts) when no conversation is active, or the message log + composer for the active conversation. Switching sessions swaps this content instantly - see "Frontend state model" in `docs/architecture.md` for how stale messages are prevented from flashing during the switch.
- **Right - Artifact panel**: still reserved and styled for the artifact viewer that ships in Phase 5 - unchanged from Phase 1, so it doesn't feel bolted on whenever it arrives.

## Responsive strategy

Unchanged from Phase 1, still built mobile-first with Tailwind's `lg` (1024px) breakpoint as the split between "all three panes visible" and "single-column with slide-over panels":

- **Desktop (≥1024px)**: sidebar, chat, and artifact panel all visible simultaneously. The artifact panel can be collapsed via a header toggle to give the conversation more room.
- **Tablet / mobile (<1024px)**: sidebar and artifact panel become accessible Radix `Dialog`-based slide-over sheets, triggered from a header hamburger and panel-toggle button respectively. The sidebar sheet now carries real, scrollable session history rather than a static empty state, and selecting a session or starting a new one closes the sheet automatically so the conversation is immediately visible.

## Loading and error states

Every network-backed surface has three states beyond its populated one, per the UI Pro Max loading-feedback guidance (stable skeletons over spinners for content the user is about to read, disable-and-spin for buttons that trigger a single action):

| Surface | Loading | Empty | Error |
|---|---|---|---|
| Sidebar session list | Three pulsing `Skeleton` rows | "No conversations yet" | "Couldn't load conversations" + Try again |
| Conversation (messages) | Three pulsing message-shaped `Skeleton`s | "This conversation is empty" | "Couldn't load this conversation" + Try again |
| Sending a message (the request itself) | Composer's send button shows a spinner and disables; the textarea disables to prevent a second submit mid-flight | n/a | An inline `role="alert"` message under the composer ("Your message couldn't be sent. Please try again.") and the drafted text is restored so nothing is lost |
| Assistant generation (the model call) | `ThinkingIndicator` - a bubble reading "Thinking through that…", `role="status"`/`aria-live="polite"`, `aria-busy="true"` on the message log | n/a (a fresh session shows the empty-conversation state until the first send) | `GenerationErrorCard` in place of the reply - `role="alert"`, the safe backend message, and a "Try again" button. The user's own message above it is untouched. |

None of these states leak a stack trace or raw HTTP status - `lib/api.ts`'s `ApiError` always carries the backend's safe, human-readable message from the shared error envelope, and `GenerationError` carries the backend's `AgentError` message the same way, with a generic fallback for network failures the backend never got to respond to.

## Accessibility principles

- All interactive elements are real `<button>`/`<input>`/`<textarea>` elements with visible `:focus-visible` rings (a 2px ring using the `--color-ring` token, contrast-checked against both themes) - including every session item in the sidebar, which is a real `<button>` with `aria-current="true"` when active, not a styled `<div>`.
- Icon-only buttons (hamburger, panel toggle, dialog close, send) carry `aria-label`; toggle buttons expose `aria-pressed` where they represent a binary state.
- The mobile sidebar/artifact sheets are Radix `Dialog` primitives, which provide focus trapping, `Escape`-to-close, and `aria-modal` semantics for free; each sheet has a (visually hidden) `DialogTitle` so screen readers announce its purpose.
- The message log is a `role="log"` region with `aria-live="polite"` and `aria-busy` (true while generating) so a screen reader announces new messages - and the fact that one is coming - without re-announcing the entire history.
- Send-failure and generation-failure feedback both use `role="alert"` so assistive technology picks either up immediately, matching the "never fake functionality" principle above - a screen reader user is never left waiting on a reply that silently failed.
- The "thinking" state is `role="status"`/`aria-live="polite"`, announced once, and never exposes anything beyond "a response is being generated" - no hidden reasoning, no internal step names.
- Retry (`GenerationErrorCard`'s button) is a real, labeled `<button>` reachable by keyboard like any other action - not a link styled as a button, not icon-only.
- The provider indicator pairs a colored dot with text ("Local · llama3.2:3b") - color is never the only signal for which provider is active.
- Color is never the only signal generally: the active session is marked with both a background tint *and* a left accent border *and* `aria-current`; status badges pair a dot with text.

## Interaction quality

- **Composer**: always typeable, including from the empty state - sending with no active conversation transparently creates one first (see `ConversationsProvider.sendMessage` in `docs/architecture.md`), so there's no artificial "click New conversation first" requirement. `Enter` sends, `Shift+Enter` inserts a newline. Disabled (with the textarea greyed out) only while a reply is being generated, to prevent overlapping turns in one conversation.
- **Send button**: disabled only when there's nothing to send or a reply is already generating (spinner shown). The helper text under the composer is honest about the one thing still missing - real transcript grounding - rather than claiming replies don't work at all, since now they do.
- **Suggested prompts**: clicking one fills the composer (creating a session first if needed) rather than displaying a pretend answer - consistent with "never fake functionality" above.
- **Assistant replies**: render as Markdown (headings, lists, bold/italic, code, links) through custom-styled `react-markdown` components matching the design system's type scale and color tokens - never a raw, unstyled dump of the model's text, and never raw HTML execution (see `docs/architecture.md`).
- **Generation failure**: never silently swallowed and never retried automatically - a visible card, in the position where the reply would have gone, with one clear recovery action.
- **Panel toggles**: desktop artifact-panel collapse and mobile sheets both use the same underlying components (`Dialog` for mobile, conditional render for desktop), keeping the codebase from needing two separate systems for "showing" a panel.
