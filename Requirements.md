# SEARCH AI — Claude Code Edition

## Required setup — what a new user MUST do before this will run

This edition needs far less setup than the API Edition — no API key, no
server, no pip install. Here is the complete list of what you must do.

### 1. Have python3 on your PATH (required)

Every deterministic step (source dedup, evidence numbering, the outline
contract, the quality gate, visual-contract checks, publishing,
rendering) is a plain Python 3 script under `scripts/` — nothing else in
this edition needs installing, but python3 itself is not optional.

Check with:

```
python3 --version
```

Python 3.9+ is required. If it's missing, install Python 3 for your OS
before your first `/run-research` call — the scripts use only the
standard library, so no pip install is needed once python3 is present.

### 2. Place this folder where Claude Code will find it (required)

Drop this package's contents into (or open Claude Code inside) the
project root you want SEARCH AI available in. Claude Code auto-discovers
everything under `.claude/` (the agents and slash commands) — there is
no separate registration step.

### 3. Run /setup once (required — takes a couple of minutes)

Inside a Claude Code session in that project, run:

```
/setup
```

This is a short conversational interview that personalizes
`knowledge_base/research_profile.md`, `source_rules.md`, and
`content_rules.md` (and `writing_samples.md` if you give it a voice
sample). You can skip any question you don't have an opinion on yet —
the templates already ship with sensible defaults, so `/setup` is about
personalizing, not unlocking, functionality.

### 4. Run your first research request

```
/run-research <a topic you actually want researched>
```

or, for the newsletter content type:

```
/run-research --newsletter <this week's topic/theme>
```

You will be asked to approve, edit, or regenerate the outline before any
full prose is written — that checkpoint is mandatory, not a formality.
The finished report lands at
`research_runs/<timestamp>_<slug>/output/article.md`.

### 5. (Recommended) accept the folder-trust prompt once

This package ships a `.claude/settings.json` that pre-approves the tool
calls `/run-research` routinely needs (running python3 scripts, editing
files in this folder, web search/fetch for evidence) so a run doesn't
stop to ask permission for its own normal steps. Claude Code only
applies those pre-approvals after you accept its one-time "trust this
folder" prompt in an **interactive** session — that prompt cannot appear
in headless mode, which is what the optional browser dashboard (below)
uses. If you plan to use the dashboard, make sure you've run `claude`
normally in this folder at least once first and accepted the trust
prompt if one appeared. If you skip this, you'll just see more
individual permission prompts than necessary — nothing breaks.

### Optional — a browser dashboard instead of typing slash commands

```
python3 ui/server.py
```

or run `/start-ui` from inside a Claude Code session in this folder.
Opens a local page at `http://127.0.0.1:8787` with a topic box, a START
button, live progress, and outline approve/edit/regenerate/discard
controls (including removing individual sections before you approve) —
the same mandatory outline checkpoint, just in a browser tab instead of
the terminal. If a run's turn ever ends before the report finishes
(most commonly because a step needed a permission headless mode can't
grant — see item 5 above), the dashboard shows a **Continue** button
instead of silently re-showing the same outline. This is optional and
newer/less road-tested than typing `/run-research` directly; the
terminal remains the fallback if anything about it seems stuck (each
run's debug panel shows the exact `claude --resume <session_id>`
command to pick the conversation back up by hand).

### Things that are NOT required (unlike the API Edition)

- No API key of any kind — reasoning steps run as subagents inside your
  existing Claude Code session, using whatever model that session is on.
- No `.env` file, no `config.py` to edit, no server to start.
- No pip install / `requirements.txt` — `scripts/` is 100% Python
  standard library.
- No separate multimodal-parsing setup — Claude Code already reads
  images, PDFs, text, and code natively.

### Optional — only relevant if you want to tune specifics

- `knowledge_base/*.md` — you can hand-edit any of these directly at any
  time instead of going through `/setup` or `/add-research-rule`; they
  are plain markdown, not a database.
- `/run-research`'s default repair-loop cap (4 passes) — mention a
  different number in your request if you want it changed for that run;
  there's no global setting file for this since each run is independent.
- `templates/article_format_spec.md` and `templates/outline_example.json`
  — only worth reading if you're modifying the agents/scripts yourself;
  not needed for normal use.

### Verify your setup (recommended, not required)

From the project root:

```
python3 scripts/new_run.py "setup verification test"
```

If that prints a new folder path under `research_runs/`, your Python
environment is correctly set up and `/run-research`'s deterministic
steps will work. You can delete the test run folder afterward.
