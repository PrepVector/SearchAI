# Delimited-markdown article format

This is the exact format research-writer and repair-editor write
(`<run>/draft/draft_latest.md`), parsed by `scripts/article_format.py`.
Never JSON for prose — this is plain text on purpose, and it's what makes
a human editing a draft by hand (or a repair pass touching just one
section) straightforward.

```
=== TITLE ===
Why Neural Networks Overfit: Causes, Detection, and Mitigation

=== ABSTRACT ===
(leave this block's body empty if the layout doesn't warrant an abstract —
never write filler just to fill the slot)

=== ANSWER ===
Overfitting occurs when a model learns patterns specific to its training
data rather than the underlying signal, and it is detected by a growing
gap between training and validation loss rather than by inspection alone...
(80-160 words, answers the main question in its first sentence)

=== TAKEAWAYS ===
- Overfitting is fundamentally a capacity/data mismatch, not randomness [E1]
- Validation-loss divergence is the reliable detection signal, not training accuracy alone
- Regularization and early stopping address the same problem from different angles

=== SECTION: s1-what-is-overfitting | What Overfitting Actually Is ===
PULL QUOTE: A model that overfits has memorized, not learned.
Overfitting occurs when [...] as shown by the divergence between training
and validation loss [E1]. **Formally**, ...

=== SECTION: s2-root-causes | Root Causes ===
Building on the definition above, three mechanisms dominate: excess model
capacity [E2], insufficient training data, and prolonged training past the
point of diminishing returns...

=== SECTION: s3-mitigations | Mitigation Techniques ===
Each cause above maps to a specific class of fix. Regularization techniques
such as dropout [E3] constrain effective capacity; early stopping halts
training at the validation-loss minimum...
```

## Rules the format enforces by construction

- **Section ids must match the outline exactly** (same `id` values, same
  order) — `scripts/outline_contract.py enforce` fixes drift automatically,
  but a close match up front means less gets silently rewritten.
- **`PULL QUOTE:`** is optional, one line, only on 2-4 sections total
  across the whole report, and never on the first section.
- **`[E1]`, `[E2]`, …** are the numbered evidence claims from
  `<run>/evidence/evidence_map.json` — cite the ones that actually support
  a sentence; final-publisher maps these into a deduplicated References
  list and strips the raw markers from the final text.
- **No self-written References section** — writing one yourself creates a
  second, conflicting list; final-publisher builds the real one
  deterministically from what you cited.
