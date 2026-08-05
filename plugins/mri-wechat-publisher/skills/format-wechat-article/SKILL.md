---
name: format-wechat-article
description: Convert validated structured Chinese scientific articles into conservative WeChat Official Account HTML with mobile-readable typography, headings, callouts, figures, captions, and references. Use when an article JSON must be rendered, previewed, or prepared for API or browser draft insertion.
---

# Format WeChat Article

## Preconditions

Require article JSON that passes `scripts/validate_article.py`. Do not repair unsupported scientific claims during formatting.

## Rendering

Run:

```powershell
python scripts/render_wechat_html.py <article.json> --output <article.html>
```

Use inline styles only. Remove scripts, forms, iframes, external stylesheets, event handlers, unsupported CSS positioning, and hidden content. Preserve the five heading names and reference order.

For images, preserve `asset_id`, path or uploaded URL, caption, source citation, license note, and alt text. Do not silently remove a missing image; return it as a blocking validation issue.

## Output

Return the HTML path, title length, digest length, section count, figure count, reference count, and sanitizer result. Rendering does not authorize saving to the live draft box.

