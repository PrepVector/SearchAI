# SEARCH AI — Claude Code Edition

A research + professional content-generation agent that runs entirely
inside [Claude Code](https://docs.claude.com/en/docs/claude-code) — no
server, no API key, no separate billing. It is **not** a LinkedIn/social
content generator, scheduler, or marketing automation tool: there is no
posting, no engagement analytics, no content calendar. It plans a research
question, gathers and audits evidence, drafts an outline you approve
before any prose is written, writes and quality-gates a full report, and
publishes it as a clean, properly-cited markdown document with figures.

If you want the same pipeline as a standalone web app that calls the
Anthropic/Gemini APIs directly (with its own token-usage accounting and a
browser UI), see the sibling **SEARCH AI — API Edition** package instead.
This edition is for using SEARCH AI *inside* a Claude Code session, where
the reasoning steps are Claude Code subagents rather than raw API calls.

## What's in here

```
.claude/
  agents/      11 subagent definitions — the specialists that do the
               actual reasoning (research-planner, evidence-scout,
               outline-architect, research-writer, quality-auditor,
               repair-editor, visual-curator, ...) plus three purely
               mechanical ones (source-auditor, evidence-mapper,
               final-publisher) that just run a script and report back.
  commands/    Slash commands you run directly: /setup, /run-research,
               /start-ui, /add-writing-sample, /add-research-rule,
               /review-memory.
  settings.json  Pre-approves the specific tool calls SEARCH AI's own
               pipeline needs (running python3 scripts, editing files
               inside this project, web search/fetch for evidence) so a
               run doesn't stop to ask permission for its own routine
               steps. See "Permissions" below before you rely on this.
scripts/       Dependency-free, stdlib-only Python — the deterministic
               "code decides, models propose" logic (source dedup/
               credibility, evidence numbering, outline-contract
               enforcement, the quality gate, visual-contract structural
               checks, citation/reference assembly, markdown rendering).
               No pip install needed.
knowledge_base/  Your standing research profile, source/content rules,
               writing samples, feedback log, and research memory —
               plain markdown you can read and hand-edit any time.
research_runs/  Where each research run's working files and final output
               land, one timestamped folder per run.
templates/     Reference docs for the article format and a worked example
               outline, mostly useful if you're modifying the agents.
ui/server.py   Optional local browser dashboard — a topic box and a
               START button, as an alternative to typing /run-research.
               See "Browser dashboard" below.
```

## Getting started

1. Drop this folder's contents into (or open Claude Code inside) the
   project root you want SEARCH AI available in — `.claude/` is what
   Claude Code discovers automatically.
2. Make sure `python3` is on your PATH — every deterministic step depends
   on it, and nothing else needs installing (no `pip install`, no `.env`,
   no API key of any kind).
3. Run `/setup` once. It's a short conversational interview that fills in
   your research profile, source preferences, and content rules under
   `knowledge_base/` — skip anything you don't have an opinion on yet, the
   templates already have sensible defaults.
4. Run `/run-research <a topic you actually want researched>`. You'll be
   asked to approve (or edit, or regenerate) the outline before any full
   prose is written — that checkpoint is mandatory by design, not a
   formality. The finished report lands at
   `research_runs/<timestamp>_<slug>/output/article.md`.

   Add `--newsletter` for a curated-links edition instead of a single
   deep-dive report — same pipeline, same approval checkpoint, but the
   outline becomes an intro plus one short item per distinct piece of
   evidence found, e.g. `/run-research --newsletter this week in AI
   research`. See "Content types" below.

Ongoing commands:
- `/review-memory` — see or edit your standing research memory directly.
- `/add-writing-sample` — paste in a piece of writing whose voice future
  reports should match.
- `/add-research-rule` — add a standing source or content rule outside the
  periodic feedback prompt.
- `/start-ui` — launch the optional browser dashboard (see below) instead
  of typing `/run-research` by hand.

## Permissions

This package ships a `.claude/settings.json` that pre-approves exactly
the tool calls SEARCH AI's own pipeline needs — running `python3 <script>`
(both as a Bash command and, on native Windows without Git for Windows,
as a PowerShell command), editing files inside this project folder, and
web search/fetch for evidence-scout. With it in place, a run shouldn't
stop mid-pipeline to ask "can I run this command?" for its own routine
steps — you'll still be asked about anything outside that list, and
Claude Code's own built-in circuit breakers (e.g. deleting your home
directory) are never overridden.

**One-time step this file needs from you:** Claude Code only applies a
project's `permissions.allow` rules once you've accepted its one-time
"trust this folder" prompt, and that prompt only appears in an
*interactive* session — it never appears in headless mode (which is what
the browser dashboard uses under the hood). So: run `claude` normally in
this folder at least once after unzipping this package, accept the trust
prompt if one appears, and every future run — interactive or via the
dashboard — will honor these pre-approvals.

## Browser dashboard (optional)

If you'd rather click a button than type slash commands, run:

    python3 ui/server.py

or, from inside a Claude Code session in this folder, just run
`/start-ui`. Either way it opens `http://127.0.0.1:8787` in your browser:
type a topic, hit **START**, and watch live progress; when the outline is
ready you'll see it right there with **Approve & Write Full Report**,
**Regenerate with Feedback**, and **Discard** buttons — the same mandatory
checkpoint as the terminal flow, just in a browser tab. It's a thin
wrapper around `claude -p` (Claude Code's own headless/scriptable mode)
running the identical `/run-research` command from outside instead of
inside an interactive session — nothing about the underlying pipeline
changes.

When a run finishes, the dashboard renders the finished report right there
on the page (headings, lists, blockquotes, and figures — not raw
markdown text), with a **Download PDF** button above it. The PDF is built
by a small dependency-free PDF writer bundled in `ui/server.py` — no pip
install, no external converter, no browser print dialog. One deliberate
trade-off: the PDF embeds each figure as a bracketed text placeholder
("[Figure: ... -- see the dashboard or article.md for the image]")
rather than the actual image, since drawing arbitrary SVG figures inside
a hand-written PDF would need a real vector-graphics translator. The
on-screen dashboard view and `research_runs/<run>/output/article.md`
both remain the full-fidelity versions with the actual figures — the PDF
is for sharing/printing the text, not a replacement for either.

This is newer and less road-tested than `/run-research` typed directly
into Claude Code, since it depends on the CLI's headless output format
and session-resume behavior rather than an interactive conversation. Each
run's status panel includes a **Debug** section with the exact
`claude --resume <session_id>` command to pick that same conversation up
by hand in a terminal if the dashboard ever seems stuck — the terminal is
always the fallback, never required to be replaced.

## How a run works

`/run-research` is the orchestrator: it creates a run folder, invokes each
specialist subagent in order, and runs the deterministic scripts itself in
between. Two design choices matter if you're reading the agents/scripts
directly:

- **The outline checkpoint is a hard stop.** The pipeline will not write a
  full draft from an outline you haven't explicitly approved, edited, or
  regenerated with feedback.
- **Deterministic steps never ask a model to re-judge structural facts.**
  Source deduplication/credibility, evidence numbering, outline-contract
  alignment, the accept/rewrite/polish quality gate, and citation/
  reference-list assembly are all plain Python in `scripts/`, not LLM
  calls — a model proposes content, code decides whether it's structurally
  sound. This also means those steps are fast, free, and reproducible.
- **The repair loop is capped** (default 4 passes) and always reports its
  true final status — a run that hits the cap without passing is reported
  as such, never silently upgraded to "PASS."

## Content types — Article vs Newsletter

`--newsletter` on `/run-research` picks which shape SEARCH AI produces —
everything else (evidence gathering, outline approval, the quality
audit/repair loop, citation resolution, publishing) is the identical
pipeline either way:

- **Article** (default) — one deep-dive report on the topic/question you
  asked, in whichever analytical layout fits.
- **Newsletter** — a curated-links edition: a short intro previewing the
  theme, then one brief item (60-150 words, "what happened → why it
  matters → source") per distinct piece of evidence the research turned
  up. Best for a request like "this week in X" rather than a single
  narrow question. Visuals are rarely placed — a newsletter is skimmed,
  not illustrated — unless a section's evidence genuinely contains
  comparable numbers worth one simple chart.

Still explicitly not a social-media tool either way — no hooks,
scheduling, publishing, or engagement analytics; a generated newsletter is
a first draft you review and send yourself, same as an article.

## Citations

research-writer and repair-editor cite evidence inline as `[E1]`, `[E2]`,
... — the numbered claims from `evidence_map.json`. `final-publisher` is
what turns those into a deduplicated, numbered References list and strips
the raw markers from the published text; a report should never show a
literal `[E1]` to the reader. If you ever see one, it means
`final-publisher` was run without its `evidence_map.json` argument — check
the exact command in `.claude/agents/final-publisher.md`.

## Notes on scope

This is a faithful architectural port of SEARCH AI's API Edition pipeline,
not a reduced version of it: the same research → outline → write → audit →
repair → visualize → publish flow, the same deterministic guardrails, the
same delimited-markdown article format. What's genuinely different is the
execution model — LLM reasoning steps are Claude Code subagents instead of
direct API calls, and the deterministic steps are CLI scripts run by the
orchestrating command instead of in-process Python functions — and there
is no token-usage ledger, since Claude Code sessions don't expose
per-call token accounting the way a direct API integration does.
