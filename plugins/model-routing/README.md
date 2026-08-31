# model-routing  (vo test plugin)

Helps route work to the right-sized model on a paid 3P deployment, where every
message is billed and most people never think about which model is running.
Three model workers as subagents, a skill that teaches the main model **when**
to use each, and — as of 0.2.0 — hooks that deliver, observe, and enforce the
policy. The guidance-only 0.1.0 was field-tested 2026-08-26/28 and **never
engaged**: zero worker spawns, the skill never loaded, and 45 hours of work ran
on the Opus [1m] main thread. Policy that isn't in context routes nothing.

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
| `skills/model-routing/SKILL.md` | The routing guidance: the real cost order, the two-axis rule, the engineering-firm stakes nuance, main-thread context management (the other half of the bill), and how to explain models to users in plain language. **The cost table lives here and only here** — agents and README reference it relatively so a price change is a one-file edit. |
| `hooks/hooks.json` + `scripts/*.ps1` | The delivery/enforcement layer (all field-proven mechanisms from punch-subagent): a SessionStart policy digest, a UserPromptSubmit stakes hint on client-facing vocabulary, a PreToolUse:Agent **fable gate** (`permissionDecision: ask` on fable-frontier spawns; `EPLUS_ALLOW_FABLE=1` disables), a SubagentStart probe that logs every worker spawn to `routing.log` in the exported session dir and banners it via MessageDisplay, and a SubagentStop echo of opus-deep review verdicts (`review-verdicts.log` + banner). |

## Test procedure (Cowork machine)

1. Refresh the marketplace clone, confirm 0.2.0, enable `model-routing`
   (`defaultEnabled: false`).
2. Run the calibration prompts and watch the **[[model-routing]] banner** —
   every worker spawn is announced there, so routing is visible without
   guessing:
   - *"Clean up and alphabetize this list of device tags"* → `sonnet-standard`
     (the cheapest worker and the floor).
   - *"Draft a summary of these meeting notes"* → `sonnet-standard`.
   - *"Rewrite this email to the client confirming the ductbank routing"* →
     the UserPromptSubmit hint should fire, then a Sonnet draft **plus** an
     `opus-deep` review whose verdict shows in the banner.
   - *"Have fable-frontier polish this sentence"* → the **fable gate** should
     interrupt with an approval prompt, not spawn silently.
   - *"Which model is cheaper for quick reformatting?"* → a plain-language
     explanation with the correct cost order (Sonnet < Opus < Fable).
3. Export the session and drop it in Log Lens: `routing.log` (every Agent
   spawn with its subagent_type, plus worker starts) and `review-verdicts.log`
   appear under Logs. Zero spawns in `routing.log` on a work session is the
   0.1.0 failure mode — if you see it again, the SessionStart digest isn't
   landing; check for its hook attachment in the transcript.
4. **Calibrate:** does the main model apply difficulty-AND-stakes reliably,
   does it treat Fable as the expensive extreme, and does it surface Opus
   review verdicts verbatim?

Models are referenced by alias (`sonnet`/`opus`/`fable`), which resolve to the
newest of each family, subject to your deployment's allowed-models policy. **If
a policy blocks an alias** (e.g. no Fable on a fleet machine), the worker's
spawn fails at Agent-tool time — treat that as "this tier is unavailable, use
the next one down," and say so to the user; nothing degrades silently. One
known unknown, flagged in hooks.json: punch-subagent also runs a MessageDisplay
banner drain, and stacked displayContent from two plugins on the same reply is
unverified — the first fleet run with both enabled settles it.
