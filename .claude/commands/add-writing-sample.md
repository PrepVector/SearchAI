---
description: Add a writing sample to the knowledge base so future reports match its voice.
argument-hint: [pasted text, or a file path to read the sample from]
---

Input: $ARGUMENTS

Add a writing sample to `knowledge_base/writing_samples.md` so
research-writer and repair-editor can match its voice on future runs.

If `$ARGUMENTS` looks like a file path, read that file and use its
contents as the sample. If it's pasted text, use it directly. If neither
was given, ask the person to paste a sample or point you at a file.

Read the current `knowledge_base/writing_samples.md` first. Append the new
sample below the existing `---` divider (don't touch the file's header
guidance), with a short heading noting where it came from and the date,
e.g.:

```
## Sample added <date> — <short description, e.g. "Q3 market report excerpt">

<the sample text>
```

Keep the sample verbatim — don't summarize or edit it; the whole point is
for research-writer to see the real voice, not your paraphrase of it.

Confirm to the person that the sample was added and will inform future
reports' voice.
