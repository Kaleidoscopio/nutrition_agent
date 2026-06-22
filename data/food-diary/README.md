# Food diary local canonical store

This directory is reserved for a more reliable local source of truth for Daniel Almeida's food diary.

Proposed structure:
- `entries/YYYY-MM-DD.json` — canonical day record
- `index.json` — maps date to canonical storage metadata
- optional sync state for fact_store mirroring

Status:
- Directory scaffold created.
- Full autonomous integration is not yet active because Hermes does not currently expose a native post-response write hook for agent-authored `fact_store` updates without editing the Hermes codebase or adding approved shell hooks to the runtime config.

If enabled later, the preferred workflow is:
1. Reconstruct day state
2. Write/update local canonical JSON
3. Mirror summary to `fact_store`
4. Verify both
