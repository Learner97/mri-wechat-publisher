---
name: save-wechat-draft
description: Save a user-approved WeChat article to an Official Account draft box through the draft API or an already logged-in browser, with strict draft-only controls and safe credential handling. Use when QA has passed and the user explicitly asks to create or update a draft; never use for publishing or mass-send.
---

# Save WeChat Draft

## Hard gates

Require all of the following:

- `QA_PASSED` result;
- explicit user approval for live draft creation;
- `publication_mode=draft_only`;
- unique draft title or idempotency key;
- a local audit-log destination that excludes secrets.

## Select transport

1. Prefer the API only when `WECHAT_APP_ID` and `WECHAT_APP_SECRET` are present locally, the outbound IP is allowlisted, and the draft capability test passes.
2. Otherwise use an already logged-in browser. Do not ask for account passwords, QR codes, cookies, or AppSecret in chat.
3. If browser reauthentication appears, pause for the user to complete it.

## API path

Use `scripts/wechat_draft_api.py`. Upload inline images, upload a cover image, rewrite image URLs, and add the draft. Report API error codes without tokens. Do not call free-publish, publish, mass-send, delete, or replace-live-content endpoints.

## Browser path

Open the Official Account article editor, fill title, author, digest, body, and available images, then click only “保存为草稿”. Return to the draft list and verify the exact test title exists. Never click “发表”.

## Receipt

Record transport, non-secret account label, article idempotency key, draft media id when available, visible title, timestamp, and verification result.

For a database-managed cycle, call `scripts/workflow_state_db.py approve-draft` only after the user's explicit approval. After the draft API or browser verification succeeds, call `scripts/workflow_state_db.py record-draft --receipt <receipt.json>`. Never mark `DRAFT_SAVED` before both gates succeed. Ad-hoc test drafts without a workflow cycle may keep a standalone receipt.
