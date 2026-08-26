---
name: model-routing
description: Use when deciding how to handle a user's request on this paid 3P deployment — whether to answer directly or delegate the work to a model worker (Sonnet, Opus, or Fable) to control cost while protecting quality. Load it for any non-trivial task, whenever the user asks about models / speed / cost / "which is cheaper", and before producing client-facing or technical output. Encodes the EPLUS rule that routing is by BOTH task difficulty and stakes — and the real cost order, in which Fable is the MOST expensive model, not a cheap one.
---

# Model routing — match the model to the work

On this deployment every message is billed, and most people don't think about
which model is doing the work. This skill routes work to the right-sized model.
Three workers are available as subagents; delegating runs the task on that model
in its own context, keeping this conversation clean.

## The actual cost order (cheapest → most expensive)

Get this right — it is the whole point, and it is easy to guess backwards:

| Worker | Model | ~Cost /1M tokens (in / out) | Capability |
|---|---|---|---|
| `sonnet-standard` | Sonnet 5 | **$2 / $10** — cheapest here | strong, the default |
| `opus-deep` | Opus 5 | $5 / $25 | higher; hard reasoning + review |
| `fable-frontier` | Fable 5 | **$10 / $50 — most expensive (~2x Opus)** | highest; the hardest work only |

**Fable is the most expensive model, not the cheapest.** It is Anthropic's most
capable model, reserved for the hardest problems — routing routine work to it is
the single most expensive mistake you can make here. (Haiku 4.5 is cheaper still
but deliberately not used: 128K context vs. 1M here, and being phased out of
Azure Foundry. Sonnet is the floor.)

## Route on TWO axes, never one

The instinct is to route on difficulty alone. Route on **difficulty AND stakes**:

- **Difficulty** — how much capability the task genuinely needs.
- **Stakes** — what happens if the output is subtly wrong. We are an engineering
  firm: a lot of ordinary-looking text is a professional communication where a
  wrong number, a misstated code section, or an overcommitment is a real
  liability, not a typo.

A task can be *easy* and *high-stakes* at once — those are the dangerous ones.

## How to decide

1. **Default — most work** → `sonnet-standard`. Drafting, analysis, coding,
   synthesis, and simple mechanical tasks too. It's the cheapest worker, so it's
   the floor; there's no point sending routine work anywhere more expensive.
2. **Genuinely hard reasoning** (complex, ambiguous, novel, high-consequence)
   → `opus-deep`.
3. **High stakes, regardless of difficulty** → the output gets an `opus-deep`
   review before it's final, even if Sonnet drafted it. Client-facing messages,
   technical determinations, anything with numbers/claims that must be right,
   anything that commits the firm. Draft on Sonnet — but don't ship without the
   review.
4. **Only the very hardest / longest-horizon problems that Opus genuinely can't
   handle** → `fable-frontier`. This is the costliest option by far; reach for
   it rarely and deliberately, never as a reflex for "important."

The example to internalize (apply the principle, don't hard-match it): a bare
*"rewrite this email"* is a `sonnet-standard` job. But if that email goes to a
client, states a technical position, or commits EPLUS to something, the final
version needs `opus-deep` eyes on it. The word "email" didn't decide that — the
stakes did. And "important" does **not** mean "send it to Fable" — Opus review
is the high-stakes tool; Fable is the extreme-difficulty tool.

## Also worth doing

- **Delegate verbose work** even when the model is the same, to keep this
  conversation's context clean — long generation and big research dumps belong
  in a subagent that returns a summary.
- **Don't over-route.** Delegation has overhead and latency. For a quick,
  low-stakes answer you can just give, give it.
- **Let workers escalate.** Sonnet flags when output needs an Opus review or the
  reasoning needs Opus; Opus flags the rare case that genuinely needs Fable. Act
  on those rather than overriding them — and never escalate past what's needed.

## When the user asks about models directly

Explain in plain language, not jargon: Sonnet is the balanced, low-cost default
for real work; Opus is more capable and more expensive, worth it for hard
problems and for checking anything important before it leaves the firm; Fable is
the most capable and by far the most expensive — for the hardest problems only.
Costs are real per message here, so the goal is the cheapest model that still
meets the task's difficulty and its stakes.
