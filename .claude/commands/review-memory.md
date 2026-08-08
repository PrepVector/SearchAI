---
description: Review, prune, or add to SEARCH AI's research memory (standing style/preference directives distilled from past feedback), and record new feedback.
argument-hint: [optional feedback text to record right now]
---

Input: $ARGUMENTS

## If no input was given — just review

Read `knowledge_base/research_memory.md` and show the person its current
state plainly: search count, how many runs until the next automatic
feedback prompt, and the current style/preference directives. Ask if they
want to remove or edit any directive, or add a new one directly (skip
distillation for a direct add — just append it to the right list in their
own words). Apply whatever they ask for by editing the file directly.

## If input was given — record feedback now

Treat `$ARGUMENTS` as feedback about how SEARCH AI's reports have been
turning out. This is the same routine `/run-research`'s periodic prompt
uses, so it's consistent whether feedback comes from there or from running
this command directly.

1. Ask (if not already obvious from their wording) whether this is a
   **style** note (writing/formatting habits), a **preference** note
   (depth, sourcing, audience, visual habits, banned patterns), or just a
   **note** not really worth turning into a standing rule. Also ask,
   unless they've made it obvious: do they want this **remembered** as a
   standing directive, or is this just feedback on one specific run that
   shouldn't change future behavior ("don't remember this run")?

2. Append the raw feedback to `knowledge_base/feedback_log.md` regardless
   of whether it'll be remembered — read the file first, then append an
   entry in its documented format (date, run number from
   `research_memory.md`'s `search_count`, category, rating if given, the
   text).

3. If they want it remembered: read `knowledge_base/research_memory.md`
   and its recent entries in `feedback_log.md` for the same category.
   Distill an updated, concise set of directives for that category —
   concrete, actionable, imperative statements a future report generator
   should follow. Merge with what's already there; when old and new
   conflict, the newest wins; drop anything vague ("be better") or clearly
   a one-off complaint about a single run. Keep each category to a
   reasonable, readable length (roughly 8 directives or fewer — merge
   related ones rather than letting the list grow forever). Write the
   updated `## Style directives` or `## Preference directives` section
   back to `knowledge_base/research_memory.md`.

4. Update `last_feedback_count` in `research_memory.md`'s frontmatter to
   the current `search_count` either way (remembered or not) — the point
   of that counter is just "don't ask again immediately," not a record of
   what was kept.

5. Confirm to the person what changed: new/updated directive(s), or "noted
   but not saved as a standing rule" if they chose not to remember it.

Never write anything to `research_memory.md` that looks like it could be
sensitive personal information or the contents of a researched document —
only the person's own short feedback text about how SEARCH AI should
behave.
