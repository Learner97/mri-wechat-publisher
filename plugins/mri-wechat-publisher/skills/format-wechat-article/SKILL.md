---
name: format-wechat-article
description: Convert validated structured Chinese scientific articles into conservative WeChat Official Account HTML with mobile-readable system-native typography, headings, core-result figures, concise public captions, and references. Use when a schema-version-8 article with 研究速览、引言、方法、结果、结果解读、结语 and an internal ranked method map, or a compatible legacy article, must be rendered, previewed, or prepared for draft insertion.
---

# Format WeChat Article

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Invoke scripts by absolute path and keep the active working directory as the user's workspace.

## Preconditions

Require article JSON that passes `<plugin-root>/scripts/validate_article.py`. Do not repair unsupported scientific claims during formatting.

## Rendering

Run:

```powershell
python "<plugin-root>/scripts/render_wechat_html.py" <article.json> --output <article.html>
```

Use inline styles only. Remove scripts, forms, iframes, external stylesheets, event handlers, unsupported CSS positioning, and hidden content. Preserve the validated heading names, their order, result-subheading wording, the absence of a separate 方法启示 section in version 8, and reference order. Do not insert a missing section for visual completeness, “证据链”, fixed takeaway boxes, fixed result numbering, or editorial labels during formatting.

Keep `method_map` internal. Never render its field names, research-material locators, critical-missing-detail notes, retrieval process, or material comparison as a public table or checklist. Render only the connected, integrated Methods prose.

Render `digest` once as a visible light-grey introduction card after the author and before the article's 研究速览 section. Keep it concise, factual, mobile-readable, and visually subordinate to the title. Do not render a second digest elsewhere, and do not convert it into a numbered takeaway box.

For images, preserve `asset_id`, path or uploaded URL, caption, source citation, license note, alt text, and `mobile_display` in structured data. Render only the concise `caption` below the image; do not expose a second “来源：” or license paragraph in public HTML. Use the validated cropped, split, or selected-panel asset when a source composite is too dense for mobile display. Do not silently remove a missing image or substitute an unreadable full composite; return it as a blocking validation issue.

Use the original system-native family stack `-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif`. These names request fonts already installed on the reader's device; do not copy, bundle, embed, fetch, or redistribute their font files. Keep plugin-generated cover typography on the bundled OFL-licensed Noto Sans SC.

## Output

Return the HTML path, title length, digest length, section count, figure count, reference count, and sanitizer result. Rendering does not authorize saving to the live draft box.
