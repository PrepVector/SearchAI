---
description: Run the full SEARCH AI research pipeline on a topic — plan, research, outline (with your approval), write, audit, repair, illustrate, publish. Add --newsletter for a curated-links edition instead of a single deep-dive article.
argument-hint: [--newsletter] <research topic or question> [-- any files/paths to include as source material]
---

Topic/request: $ARGUMENTS

Run SEARCH AI's full research and content-generation workflow on this
request. You (the main session) are the orchestrator: you create the run
folder, invoke each specialist subagent via the Task tool in the order
below, run the deterministic scripts yourself where noted, and — critically
— you own the human checkpoint after the outline. Do not skip steps or
merge them "for efficiency"; the guardrails only work because each step's
output is actually checked before the next one starts.

All file paths below are relative to the project root (the folder
containing `knowledge_base/`, `scripts/`, `research_runs/`, and
`.claude/`). If the person invoked this from somewhere else, find the
project root first (look for `scripts/new_run.py`).

## 0. Set up the run

Two content types share this exact same pipeline — the only difference is
`options.json`'s `format` field, read by outline-architect in step 3:
- **Article** (default) — one deep-dive report on the topic/question.
- **Newsletter** — a curated-links edition: a short intro plus one brief
  item per distinct notable piece of evidence found. Triggered by a
  leading `--newsletter` flag in `$ARGUMENTS`, or if the request itself
  is unambiguously asking for a newsletter/digest/roundup (e.g. "this
  week's newsletter on X", "roundup of recent Y developments"). If it's
  genuinely unclear which the person wants, ask — don't guess on this one,
  since it changes the whole shape of the output.

If the request includes files to attach (paths after `--`, or files the
person just mentioned/uploaded), note their paths — you'll pass them to
research-planner in step 1 so it can `Read` them directly (Claude Code
already reads images, PDFs, text, and code natively; for CSV/JSON, Read
the file and summarize it in your own words if research-planner needs a
condensed version).

Run, via Bash:
```
python3 scripts/new_run.py "<the topic text, with --newsletter stripped out>"
```
This prints the new run folder path — call it `<run>` for the rest of this
command. It's already scaffolded with `evidence/`, `outline/`, `draft/`,
`audit/`, `visuals/`, `output/` subfolders and `topic.txt`.

Write `<run>/options.json` with sensible defaults, adjusted for anything
the person specified in their request (depth, format, image count, etc.):
```json
{"depth": "standard", "audience": "professional/technical", "format": "auto",
 "current_findings": true, "web_research": true, "image_count": 4}
```
For a newsletter request, set `"format": "newsletter"` and drop
`image_count` to `1` (a newsletter's items rarely warrant a figure — see
outline-architect's newsletter-mode instructions).

Read `knowledge_base/research_profile.md` first and use its defaults
instead of the hardcoded ones above wherever it has an opinion.

## 1. Plan

Invoke the **research-planner** subagent (Task tool). Tell it the run
folder path, and point it at `knowledge_base/research_profile.md`,
`source_rules.md`, and `content_rules.md` to read for standing guidance,
plus any attached file paths from step 0.

After it finishes, read `<run>/analysis.json`, `<run>/contract.json`, and
`<run>/plan.json` (research-planner writes `analysis.json` as
`{"analysis":..., "plan":...}` — extract `plan` from it if you didn't
already write it separately).

## 2. Research (only if the plan calls for it)

If `plan.use_web_search` is true:
- Invoke **query-builder**, then **evidence-scout**, in that order, each
  told the run folder path.
- Invoke **source-auditor**, then **evidence-mapper**, in that order (both
  are mechanical — they just run their scripts).

If `plan.use_web_search` is false, skip straight to writing an empty
evidence map: write `<run>/evidence/evidence_map.json` as
`{"evidence": [], "single_source_count": 0}` and tell the person briefly
why (per the planner's `reason_search`).

## 3. Outline

Invoke **outline-architect**, told the run folder path and pointed at
`knowledge_base/content_rules.md` and `writing_samples.md`.

## 4. HUMAN CHECKPOINT — outline approval

This is mandatory. Read `<run>/outline/outline.json` and show the person
the outline in your own reply: title, layout, and each section's title +
goal + key questions. Ask plainly: **approve it, edit it yourself, ask you
to regenerate it with specific feedback, or discard it and stop here.**

- If they want edits, apply them directly to `<run>/outline/outline.json`
  yourself (you have Write access) rather than re-invoking the architect
  for small changes.
- If they want a regeneration, write their feedback to
  `<run>/regenerate_feedback.txt` and re-invoke **outline-architect** (it
  reads that file automatically), then show the revised outline and ask
  again.
- If they discard, stop here — leave the run folder as a record but do not
  continue to writing.
- Do not proceed past this point without an explicit approval. Do not
  assume silence or a topic-adjacent follow-up message means approval.

Once approved, if anything was hand-edited, make sure
`<run>/outline/outline.json` reflects the final approved version.

## 5. Write

Invoke **research-writer**, told the run folder path and pointed at
`knowledge_base/writing_samples.md` and `content_rules.md`.

Then run, via Bash, to bring the parsed draft to outline-contract:
```
python3 scripts/outline_contract.py enforce <run>/draft/article_latest.json <run>/outline/outline.json <run>/draft/enforced_v1.json
python3 -c "import json; d=json.load(open('<run>/draft/enforced_v1.json', encoding='utf-8')); json.dump(d['article'], open('<run>/draft/article_latest.json','w', encoding='utf-8'), indent=2, ensure_ascii=False)"
```
Note the `alignment_score` from `enforced_v1.json` — you'll want it for
the final report.

## 6. Audit + repair loop (capped)

Set `MAX_ITERS` = 4 (or a number the person specified). Set `ITERS_DONE` =
0.

Loop:

1. Invoke **quality-auditor**, telling it the run folder path, the current
   `ITERS_DONE`, and `MAX_ITERS`.
2. Read `<run>/audit/gate_latest.json`.
3. If `action` is `"accept"`, stop the loop.
4. Otherwise: increment `ITERS_DONE`. Invoke **repair-editor**, telling it
   the run folder path. Then re-run outline-contract enforcement exactly
   as in step 5 (overwriting `article_latest.json` again). Go back to 1.

Never let this loop run more than `MAX_ITERS` times. If the cap is reached
without `action` becoming `"accept"`, that's fine — stop anyway and report
the true final status honestly (never claim PASS if the gate didn't say
PASS).

## 7. Visuals

Invoke **visual-curator**, told the run folder path and the approved
`image_count` cap from `<run>/options.json`.

## 8. Publish

Invoke **final-publisher**, told the run folder path.

Then render the human-readable deliverable, via Bash:
```
python3 scripts/render_markdown.py <run>/output/article_final.json <run>/output/article.md
```

## 9. Report back

Tell the person: where the report lives (`<run>/output/article.md`), the
final validation status (from the last `gate_latest.json`'s
`display_status`), how many repair passes ran, how many sources were used,
how many visuals were placed, and any warnings worth flagging (unsupported
claims, invented entities, structural gaps, or issues from
`<run>/visuals/visual_audit.json`) — be honest here, don't just say "done!"
if the gate reported warnings or a fail.

## 10. Research memory — periodic feedback

Read `knowledge_base/research_memory.md`'s frontmatter (`search_count`,
`last_feedback_count`, `feedback_every_n`). Increment `search_count` by 1
and write it back. If `search_count - last_feedback_count >=
feedback_every_n`, ask the person a quick, low-friction feedback question
("anything you'd want different about how these come out — style,
sourcing, depth? Or nothing to add — that's fine too"). If they give an
answer, follow the same process as `/review-memory`'s feedback-recording
section to log and (if they want it remembered) distil it. If they have
nothing to add, just update `last_feedback_count` to the current
`search_count` so you don't ask again until the next milestone.

If it's not yet due, skip this step silently — don't mention it.
