# model-routing  (vo test plugin)

Helps route work to the right-sized model on a paid 3P deployment, where every
message is billed and most people never think about which model is running.
Three model workers as subagents plus a skill that teaches the main model
**when** to use each. No hooks yet, by request.

## The actual cost order (this is the whole point)

Real Anthropic API rates (source: the `claude-api` reference), cheapest to most
expensive:

| Worker | Model | ~Cost /1M (in / out) | Role |
|---|---|---|---|
| `sonnet-standard` | Sonnet 5 | **$2 / $10** — cheapest here | the low-cost default for the bulk of work |
| `opus-deep` | Opus 5 | $5 / $25 | hard reasoning + review of consequential output |
| `fable-frontier` | Fable 5 | **$10 / $50 — most expensive (~2x Opus)** | the hardest / longest-horizon problems only |

**Fable 5 is the most expensive model, not the cheapest** — Anthropic's most
capable model, ~2x Opus per token. Routing routine work to it is the single most
expensive mistake this plugin exists to prevent.

**Why not Haiku 4.5?** It's cheaper (~$1/$5), but deliberately left out: its
context window is 128K vs. 1M on the other three, and it's being phased out of
Azure AI Foundry. Sonnet is the floor — better, and not much more expensive than
Haiku relative to the gap to Opus/Fable.

## The core idea: route on difficulty AND stakes

The trap is routing on difficulty alone. For an engineering firm that's
dangerous: a lot of ordinary-looking text is a professional communication where
a wrong number or misstated code section is a real liability. So the skill
routes on two axes:

- **Difficulty** → picks the worker (Sonnet default → Opus for hard → Fable for
  the very hardest).
- **Stakes** → can override it. High-stakes output gets an `opus-deep` review
  before it's final, even when Sonnet drafted it. "Important" means *Opus
  review*, not *Fable* — Fable is the extreme-difficulty tool, not the
  high-stakes tool.

Illustrative (applied as a principle): *"rewrite this email"* is a Sonnet job —
but a client-facing email stating a technical position needs Opus eyes on the
final. The stakes decide, not the word "email."

## What's here

| Path | Purpose |
|---|---|
| `agents/sonnet-standard.md` | Sonnet 5 — the cheapest worker and the default; flags high-stakes output for Opus review. |
| `agents/opus-deep.md` | Opus 5 — hard reasoning and review of consequential output. |
| `agents/fable-frontier.md` | Fable 5 — most expensive/most capable; reserved for the hardest problems, told to flag when it wasn't needed. |
| `skills/model-routing/SKILL.md` | The routing guidance: the real cost order, the two-axis rule, the engineering-firm stakes nuance, and how to explain models to users in plain language. |

## Test procedure (Cowork machine)

1. Enable `model-routing` (`defaultEnabled: false`).
2. Watch which worker the main model routes to:
   - *"Clean up and alphabetize this list of device tags"* → `sonnet-standard`
     (the cheapest worker and the floor).
   - *"Draft a summary of these meeting notes"* → `sonnet-standard`.
   - *"Rewrite this email to the client confirming the ductbank routing"* →
     Sonnet draft **plus** an `opus-deep` review, not a bare cheap draft.
   - *"Which model is cheaper for quick reformatting?"* → a plain-language
     explanation with the correct cost order (Sonnet < Opus < Fable).
3. **Calibrate:** does the main model apply difficulty-AND-stakes reliably, and
   does it correctly treat Fable as the expensive extreme (not a default)?

Models are referenced by alias (`sonnet`/`opus`/`fable`), which resolve to the
newest of each family and are checked against your deployment's allowed-models
policy. This is guidance, not enforcement — with no hooks, nothing forces a
route; the skill and the workers' escalation notes steer the main model.
