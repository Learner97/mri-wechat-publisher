---
name: format-wechat-article
description: Convert validated structured Chinese scientific articles into conservative WeChat Official Account HTML with mobile-readable system-native typography, headings, core-result figures, concise public captions, and references. Use when a schema-version-8 article with 研究速览、引言、方法、结果、结果解读、结语 and an internal ranked method map, or a compatible legacy article, must be rendered, previewed, or prepared for draft insertion.
---

# Format WeChat Article

Resolve the plugin root above `skills/`. Reuse the already-loaded, unchanged [editorial profile](../../docs/editorial-profile.md) as the single authority for typography, digest placement, original figures and visible/internal content; load it only when missing or changed.

## Build

Require validated article JSON and already selected, reviewed source images. Run:

```powershell
python "<plugin-root>/scripts/prepare_article.py" <article.json>
```

Reuse the established renderer. Do not rewrite prose, select or alter images, renumber figures, or introduce a per-article CSS theme while formatting.

- `preview.html`: the single self-contained article preview with actual embedded images.
- `article.html`: a small redirect/link to that preview, preserving the established entry path.
- `wechat-upload.html`: upload-only fragment with image placeholders.
- `figure-review.html`: 430px inspection page referencing the same local original assets.
- Internal evidence/method/figure maps and `bundle-manifest.json`: traceable inputs, rendering code and output hashes.

The asset store reuses reads, image decoding, hashes and encodings within one build. Identical sources, JSON, assets, code and intact outputs reuse the previous deterministic build without rewriting it; changed inputs invalidate it. A cache hit never supplies scientific QA or user approval.

Deliver the preview to the user. Pass only `wechat-upload.html` to an authorized draft-save flow. Standalone `render_wechat_html.py` defaults to a self-contained preview; placeholders require `--for-upload`.

Generation alone does not authorize saving or establish scientific, license or visual QA. After actual review, `qa-wechat-article` records the bundle-bound QA; the state tool records a separate user-approved snapshot.
