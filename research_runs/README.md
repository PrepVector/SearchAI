# research_runs/

Every `/run-research` call creates one timestamped subfolder here (e.g.
`20260807_152234_why-do-neural-networks-overfit/`) via `scripts/new_run.py`.
Each run folder is self-contained:

```
<run>/
  topic.txt                       the research question
  options.json                    depth/audience/format/image_count/etc.
  analysis.json, contract.json    from research-planner
  queries.json                    from query-builder
  evidence/                       findings, sources, audited findings,
                                   evidence map (from evidence-scout,
                                   source-auditor, evidence-mapper)
  outline/                        outline.json, structural_gaps.json
  regenerate_feedback.txt         present only if you asked to regenerate
                                   the outline with feedback
  draft/                          draft_latest.md, article_latest.json —
                                   overwritten each writer/repair pass
  audit/                          verdict_latest.json, gate_latest.json —
                                   overwritten each audit pass
  visuals/                        figure_*.svg, images.json
  output/                         article_final.json, article.md (the
                                   deliverables)
```

Nothing here is required reading before starting a new run — it's a record
of what happened, useful for resuming a run, debugging why a report came
out a certain way, or just re-reading past reports. Feel free to delete old
run folders you don't need; nothing else in the project depends on them.
