# SEARCH AI -- Claude Code Edition

## How to Navigate the Interface (the browser dashboard)

*(Filename note: "?" is left out on purpose -- it isn't allowed in
Windows filenames.)*

This describes the optional browser dashboard (`ui/server.py`). If
you're typing `/run-research` straight into Claude Code instead, you
don't need this file -- see "How to Run the Model.md".

### Opening it

From a terminal in this project folder:
```
python3 ui/server.py
```
or, from inside a Claude Code session in this folder:
```
/start-ui
```

Either one opens your default browser to `http://127.0.0.1:8787`.

That address only works on your own machine, while this command is
still running in that terminal. Closing the terminal (or hitting
Ctrl+C in it) stops the dashboard.

### The screen, top to bottom

**1. "Research topic" box (top card)**

- Type what you want researched, e.g. "North Star Metric frameworks for
  B2B SaaS".
- Tick "Newsletter format" if you want a curated-links digest (short
  intro + one item per source found) instead of a single deep-dive
  report. Leave it unticked for the default article.
- Press START.

**2. Active run card (appears once you press START)**

This card updates itself automatically -- you don't need to refresh the
page. It moves through these states:

- **STARTING / RUNNING** -- a pulsing dot and a stage label
  (researching, writing, auditing/repairing, adding visuals,
  finalizing...). This can take a few minutes, especially while real
  web sources are being gathered. It's safe to leave the tab open and
  check back.
- **AWAITING_DECISION, with an outline shown** -- SEARCH AI has proposed
  a structure and is waiting for you. You'll see each section's title
  and goal, and three buttons:
  - **Approve & Write Full Report** -- locks in the outline exactly as
    shown and writes the complete report.
  - **Regenerate with Feedback** -- asks you what should change, then
    tries again with your notes.
  - **Discard** -- stops the dashboard from tracking this run (it does
    not delete anything already written to disk).
- **AWAITING_DECISION, with no outline shown** -- this means SEARCH AI
  is asking you a question first (most often because your topic was
  ambiguous, like a topic that could mean more than one thing). You'll
  see its actual question and a plain text box -- type your answer and
  press Send Reply. There's deliberately no Approve button in this
  state, since there's nothing to approve yet.
- **DONE** -- the finished report is rendered right there on the page
  (headings, lists, quotes, figures). Press Download PDF above it to
  save a PDF copy. Note: the PDF shows figures as a labeled placeholder
  line rather than the actual image (the on-screen view above it, and
  the `article.md` file on disk, both have the real images).
- **ERROR** -- something went wrong (e.g. Claude Code's CLI wasn't
  found, or a call failed). The message explains what happened.

**3. "Debug info" (small triangle under most runs)**

Click to expand. Shows the run's `session_id`, its folder on disk, and
the exact terminal command (`claude --resume <session_id>`) to continue
that same conversation by hand if the dashboard ever seems stuck. This
is always available as a fallback -- nothing the dashboard does is only
possible through the dashboard.

**4. "Past runs this session" (bottom card)**

Every run you've started since opening the dashboard, most recent
first. Click any of them to bring it back up in the active run card
above -- useful if you started a run, closed the tab, and came back
later (as long as the same `python3 ui/server.py` process is still
running).

### Things that are not in the dashboard (by design)

There is no login, no settings page, and nothing to configure in the
browser itself -- all personalization (your research profile, source
rules, writing samples) lives in `knowledge_base/*.md` and is set up
once via `/setup` in the terminal, not through this interface.
