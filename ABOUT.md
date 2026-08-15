# SEARCH AI — Claude Code Edition

## About this project

### What this is

SEARCH AI is a research and professional long-form content-generation
agent that runs entirely inside Claude Code — no server, no API key, no
separate billing. It plans a research question, gathers and audits
evidence, drafts an outline you approve before any prose is written,
writes and quality-gates a full report, and publishes it as a clean,
properly-cited markdown document with figures.

### What this is NOT

SEARCH AI is explicitly **not** a LinkedIn content generator, social-media
manager, posting tool, content-calendar system, or marketing-automation
platform. There is no hook-writing, no scheduling, no publishing to any
platform, no engagement analytics, no content-pillar planning, and no
post-generation workflow of any kind. The output is a markdown file you
review and send/publish yourself, through whatever channel you choose —
SEARCH AI never does that step for you.

### Features

**Two content types, one pipeline.** Article (default) is one deep-dive
report on the topic/question you asked, in whichever analytical layout
fits. Newsletter (`/run-research --newsletter <topic>`) is a
curated-links edition: a short intro plus one 60-150 word "what happened
-> why it matters -> source" item per distinct piece of evidence found —
best for "this week in X" or "roundup of recent Y" requests. Same
evidence-gathering, outline-approval, audit/repair, and publish pipeline
either way — only the outline shape and writing voice change.

**Human-in-the-loop outline checkpoint — a hard stop, not a formality.**
`/run-research` will not invoke the writer from an outline you haven't
explicitly approved, edited, or regenerated with feedback. You can
approve as-is, edit it directly, ask for a feedback-driven regeneration,
or discard the run entirely.

**Real web research, done through Claude Code itself.** evidence-scout
uses Claude Code's own web-search capability — never a paid external
search API — and is explicitly instructed to never invent a source,
product, statistic, or URL. source-auditor and evidence-mapper then
dedupe and number the findings deterministically, with zero model
judgment involved in those structural facts.

**Evidence-grounded writing with real citations.** Every claim traces
back to a numbered evidence item (`[E1]`, `[E2]`, ...). final-publisher
turns these into a deduplicated, numbered References list and strips any
raw marker or stray reference list before you see the report.

**Nine-category structured quality audit + capped automatic repair.**
Every draft is scored across topic alignment, answer-contract coverage,
evidence support, citation integrity, source quality, depth, clarity,
coherence, and redundancy, plus explicit unsupported-claims/invented-
entities/drift lists. `scripts/quality_gate.py` — plain deterministic
code, not a model — decides accept / targeted rewrite / lighter polish /
fail. The repair loop is capped (default 4 passes) and always reports
its true final status; it never silently becomes "PASS."

**Deterministic guardrails ("models propose, code decides").**
`outline_contract.py`'s `structural_audit` (before writing) and
`enforce` (after writing) keep the approved outline a hard contract; the
minimum-depth-indicator check is correctly skipped for newsletter
sections while still fully enforced for every article layout.
`quality_gate.py` runs the same fixed-threshold accept/rewrite/polish/fail
logic as the API Edition. `visual_contract.py` requires every placed
image to have a caption, point at a real outline section, avoid
duplicate archetypes per section, and stay under the image-count cap.

**Real, data-grounded visuals — never invented.** visual-curator decides
per section whether a visual genuinely helps, never forcing a generic
figure and never fetching a stock photo. `scripts/visual_engine.py`
builds deterministic SVG figures only from labels/data that actually
exist in the evidence or a file you attached.

**Native multimodal reading — nothing extra to install.** Claude Code
already reads images, PDFs, text, and code natively, so research-planner
can just Read whatever you attach directly — there's no separate parsing
package to install or maintain for this edition.

**Standing knowledge base, in plain markdown.** `knowledge_base/` holds
your research profile, source rules, content rules, writing samples, and
research memory — all plain `.md` files you can read and hand-edit any
time, populated initially via `/setup` and refined over time via
periodic low-friction feedback prompts and `/add-research-rule` /
`/add-writing-sample` / `/review-memory`.

**Pre-approved permissions for the pipeline's own routine steps.**
`.claude/settings.json` pre-approves exactly the tool calls SEARCH AI's
own pipeline needs (running python3 scripts, editing files in this
project, web search/fetch for evidence) so a run doesn't stop
mid-pipeline asking permission for its own normal steps. Anything
outside that list, and Claude Code's own built-in safety circuit
breakers, still apply as normal. Requires accepting Claude Code's
one-time folder-trust prompt once, interactively, before it takes effect
(see Requirements.md) -- headless runs (including the dashboard below) can't
show that prompt themselves.

**Optional browser dashboard -- a START button instead of slash
commands.** `ui/server.py` is a stdlib-only local web server (launch
with `python3 ui/server.py` or `/start-ui`) providing a topic box, a
START button, a live progress view, and outline approve/edit/regenerate/
discard controls in a browser tab at `http://127.0.0.1:8787`. It drives
the exact same `/run-research` command from outside via Claude Code's
own headless mode (`claude -p`, with `--resume` to continue the same
conversation after you approve or give feedback) -- nothing about the
underlying pipeline changes, and the mandatory outline checkpoint still
applies. This is newer than `/run-research` itself and depends on the
CLI's headless/session-resume behavior; each run's debug panel shows the
exact `claude --resume <session_id>` command to continue by hand in a
terminal if the dashboard ever seems stuck.

**Edit the outline, or cut sections, before approving.** The outline
review screen has an "Edit Outline" mode (reword any section's title or
goal, add a section, or remove one) plus a one-click "&times;" on each
section for the common case of just cutting it. Saving writes straight
to the run's `outline.json` -- no regeneration turn spent, and no
re-invoking outline-architect for a change you can make yourself.

**Recovers from a stalled turn instead of looping.** If a resumed
session's turn ever ends before the report actually finishes (most
commonly because a step needed a permission headless mode can't grant
on its own), the dashboard used to silently re-show the same,
already-approved outline as if it were a new decision -- indistinguishable
from being stuck approving the same thing forever. It now detects this
(the outline on disk is unchanged from what was approved, but there's
still no finished report) and shows a **Continue** button with Claude's
own last message, instead.

**Finished report shown on-screen, with a one-click PDF download.**
When a run reaches "done," the dashboard renders the actual report in
the browser (headings, lists, blockquotes, figures) instead of raw
markdown text, and offers a "Download PDF" button. The PDF is produced
by a small hand-written, dependency-free PDF writer bundled in
`ui/server.py` -- consistent with this edition's no-pip-install rule.
Known limitation: figures are embedded in the PDF as bracketed text
placeholders, not actual images (rendering arbitrary SVG into a
hand-written PDF would require a real vector-graphics translator). The
on-screen dashboard view and `research_runs/<run>/output/article.md`
both keep the real figures -- the PDF is a text-complete,
share/print-ready copy, not a strict superset of those two.

### How to run it

See Requirements.md for the full setup checklist. Short version:

1. Make sure python3 is on your PATH (no other install needed — every
   script is dependency-free stdlib Python).
2. Drop this folder's contents into (or open Claude Code inside) the
   project root you want SEARCH AI available in.
3. Run `/setup` once (a short conversational interview).
4. Run `/run-research <a topic you want researched>` — or
   `/run-research --newsletter <this week's theme>` for the newsletter
   content type.

The finished report lands at
`research_runs/<timestamp>_<slug>/output/article.md`.

No API key, no `.env` file, no server, no pip install.

### How it works (high level — see ARCHITECTURE.md for the full detail)

`/run-research` is the orchestrator. It creates a run folder, then
invokes each specialist subagent (via the Task tool) in order, running a
handful of deterministic scripts itself in between:

`new_run.py` (scaffold) -> research-planner subagent (analysis + answer
contract + plan) -> [if web search warranted: query-builder +
evidence-scout subagents] -> source-auditor + evidence-mapper subagents
(each just runs its matching deterministic script) -> outline-architect
subagent (proposes structure) -> `outline_contract.py` `structural_audit`
(deterministic pre-write check) -> shown to you for the human checkpoint
-> research-writer subagent (writes the full report) ->
`outline_contract.py` `enforce` (deterministic structure repair) ->
quality-auditor subagent (nine-category audit) -> `quality_gate.py`
(deterministic accept/rewrite/polish/fail) -> repair-editor subagent
loop (capped) -> visual-curator subagent (real figures) ->
`visual_contract.py` audit (deterministic placement check) ->
final-publisher subagent (assembles references, runs
`final_publisher.py`) -> `render_markdown.py` -> `output/article.md`.

Every "does this structurally hold together" question is answered by
plain Python in `scripts/`, not by asking a subagent to grade its own
homework a second time. Subagents are only ever trusted to propose
content — never to be the final word on whether it's structurally valid.

The key architectural difference from the sibling API Edition: reasoning
steps here are Claude Code subagents instead of direct Anthropic/Gemini
API calls, and the deterministic steps are CLI scripts the orchestrating
command runs itself instead of in-process Python functions behind a
FastAPI route. There is no token-usage ledger here, since Claude Code
sessions don't expose per-call token accounting the way a direct API
integration does.

### Project layout

```
.claude/
  agents/       11 subagent definitions -- 8 reasoning specialists
                (research-planner, query-builder, evidence-scout,
                outline-architect, research-writer, quality-auditor,
                repair-editor, visual-curator) + 3 mechanical wrappers
                (source-auditor, evidence-mapper, final-publisher) that
                just run a script and report back.
  commands/     /setup, /run-research, /start-ui, /add-writing-sample,
                /add-research-rule, /review-memory
  settings.json pre-approved tool-call permissions for the pipeline's
                own routine steps (see Features above)
scripts/        dependency-free, stdlib-only Python -- the deterministic
                "code decides, models propose" logic (source dedup/
                credibility, evidence numbering, outline-contract
                enforcement, the quality gate, visual-contract structural
                checks, citation/reference assembly, markdown rendering)
knowledge_base/ your standing research profile, source/content rules,
                writing samples, feedback log, and research memory --
                plain markdown, hand-editable any time
research_runs/  each run's working files and final output, one
                timestamped folder per run
templates/      reference docs for the article format and a worked
                example outline -- mostly useful if modifying the agents
ui/server.py    optional local browser dashboard (topic box + START
                button) driving /run-research via Claude Code's headless
                mode -- see Features above
```

See README.md for the user-facing quick start and ARCHITECTURE.md for
the full pipeline diagram, subagent/script responsibilities, and what's
intentionally different from the API Edition.

### Build

Architectural port of SEARCH AI API Edition build 2026.08.07-1-api — two
content types (Article, Newsletter), no API key required.
