# FLAGS: things only Morty can do

The agent appends here (never deletes). Morty checks this file and replies by editing the entry.
Format, copy exactly:

```
## FLAG-<n> [BLOCKING|NON-BLOCKING] <short title>
- Phase/step: <e.g. 1.2>
- What I need from Morty: <one concrete ask>
- What I tried: <commands / errors, max 10 lines>
- What I'm doing meanwhile: <next step I moved on to, or "stopped">
- Status: OPEN
```
Morty changes `Status: OPEN` to `Status: DONE <answer>`.

---

## FLAG-0 [BLOCKING] Model endpoint + key  (pre-filled by setup)
- Phase/step: 1.1
- What I need from Morty: put SNITCH_BASE_URL, SNITCH_API_KEY, SNITCH_MODEL in `.env` (see `.env.example`), using the open-source model credits from the Openfire email. Prefer a code model (Qwen2.5/3-Coder, DeepSeek-Coder/V3, Llama, GLM).
- What I tried: n/a
- What I'm doing meanwhile: Phase 0 works offline (classic mutator), so I do Phase 0 first.
- Status: DONE `.env` has SNITCH_BASE_URL=https://openrouter.ai/api/v1 and SNITCH_MODEL=google/gemma-4-31b-it:free. The key is NOT in .env: snitch/llm.py falls back to the OPENROUTER_API_KEY env var exported in Morty's ~/.zshrc. Never print or echo it. If you get 'Missing env vars: SNITCH_API_KEY', your shell didn't load ~/.zshrc: run commands via `zsh -ic '<cmd>'`, or raise a BLOCKING flag. On repeated provider 429s, switch SNITCH_MODEL to poolside/laguna-s-2.1:free and note it in NOTES.md.
