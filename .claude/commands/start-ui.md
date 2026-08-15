---
description: Launch the local browser dashboard (topic box, a START button, and outline approve/regenerate buttons) as an alternative to typing /run-research by hand.
argument-hint: (no arguments)
---

Run this in the background so it doesn't block the conversation:

    python3 ui/server.py

Then tell the person, in your own words, something close to this:

"Dashboard running — it should have opened in your browser automatically;
if not, go to http://127.0.0.1:8787. Type a topic, hit START, and you'll
see live progress and the outline to approve/regenerate right there in
the browser, same checkpoint as usual. This is a convenience layer around
/run-research, not a replacement — if the browser ever seems stuck, this
terminal (or `claude --resume <session_id>`, shown in the dashboard's
debug panel) is always the fallback. Leave this terminal window open
while you use the dashboard; press Ctrl+C here when you're done."

Do not read or summarize ui/server.py's contents unless the person asks
you to — just run it and hand off to the browser.
