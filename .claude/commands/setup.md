---
description: One-time interview to populate SEARCH AI's knowledge_base/ with your research profile, source rules, content rules, and (optionally) writing samples.
---

You're setting up SEARCH AI — a research and professional long-form
content-generation agent that runs entirely inside Claude Code. This is a
short interview, not a form: ask naturally, in a few short turns, and skip
anything the person doesn't have an opinion on yet (the templates already
have sensible defaults — this just personalizes them).

## What to ask

1. **Depth and audience.** "When I say 'standard depth,' what does that
   mean for you — a quick brief, or something closer to a full report? Who
   usually reads these — you, a technical team, executives, something
   else?"
2. **Source preferences.** "Are there kinds of sources you always want
   prioritized (official docs, peer-reviewed papers, recent-only) or ones
   you want avoided (content-farm sites, a specific outlet, etc.)?"
3. **Content/format preferences.** "Any formatting habits you want every
   report to follow — tables over prose for comparisons, a particular
   citation style, banned phrases, a preferred report layout by default?"
4. **Writing sample (optional).** "Want to paste an example of writing
   whose voice you'd like reports to match? Totally optional — skip if you
   don't have one handy."

Ask these conversationally — one or two at a time, not as a wall of
questions — and let the person's answers guide follow-ups.

## What to do with the answers

Update these files directly (they already exist as templates under
`knowledge_base/` — read each one first, then rewrite it with the
person's answers folded in, keeping the file's existing structure and
guidance comments for anything they didn't answer):

- `knowledge_base/research_profile.md` — depth/audience/format defaults.
- `knowledge_base/source_rules.md` — preferred/avoided sources.
- `knowledge_base/content_rules.md` — formatting/banned-pattern/structural
  rules.
- `knowledge_base/writing_samples.md` — only if they gave you a sample;
  append it under the existing `---` divider, don't remove the file's
  header guidance.

Leave `knowledge_base/feedback_log.md` and `knowledge_base/research_memory.md`
untouched — those populate themselves over time from actual feedback, not
from setup.

## Before finishing

Check that `python3` is available (`python3 --version` via Bash) — every
deterministic step in `/run-research` depends on it. If it's missing, tell
the person to install Python 3.9+ before their first `/run-research` call.
No other setup is required — there's no API key, no server to start.
Multimodal file reading (images, PDFs, code, etc.) uses Claude Code's own
built-in file-reading capability directly, so nothing extra needs
installing for that either.

Finish by telling the person their knowledge base is ready and they can
start with `/run-research <a topic they actually want researched>`.
