# Feedback log

Append-only history of feedback given after research runs. `/run-research`
appends here when you answer its periodic feedback prompt (every N runs,
default 30 — see `research_memory.md`); `research_memory.md`'s standing
directives are periodically distilled from these entries. This file is a
raw log, not itself read by the writing/research agents — only
`research_memory.md`'s distilled directives are.

Format per entry:
```
## <ISO date> — run #<search_count> — category: style|preference|note
Rating: <1-5 or none>
<feedback text>
```

---

(No feedback yet.)
