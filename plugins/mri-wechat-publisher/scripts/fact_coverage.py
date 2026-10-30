"""Source-first coverage candidates and bound semantic decisions; no model client."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from article_review import text_blocks, pointer, source_excerpt_errors

ACCEPTED = {"accurate", "reasonable_omission"}
VERDICTS = ACCEPTED | {"important_omission", "misinterpreted", "source_insufficient"}


def matches(text, groups):
    """Candidate retrieval only: each concept group contains alternative expressions."""
    return all(any(str(alias).lower() in text.lower() for alias in group) for group in groups)


def review_coverage(article, article_path, assets):
    formal = article.get("schema_version") == 8 and article.get("source", {}).get("evidence_level") == "FULLTEXT"
    path = article_path.parent / "work/research-facts.json"
    if not path.is_file():
        return {"status": "SOURCE_REVIEW_REQUIRED" if formal else "NOT_REQUIRED", "items": [], "findings": [],
                "reason": "缺少首读来源事实；不能从推文自带verified或零关键词命中认定覆盖完整。"}
    try:
        data = json.loads(assets.read(path))
        manifest = article_path.parent / article["source"]["source_manifest"]
        if data.get("source_manifest_sha256") != assets.digest(manifest):
            raise ValueError("事实摘要的来源清单版本已失效。")
        facts = data["facts"]
        if not isinstance(facts, list) or not facts:
            raise ValueError("首读事实不能为空；只保留影响主结论/定义的高价值事实。")
        ids = [f["id"] for f in facts]
        if len(ids) != len(set(ids)):
            raise ValueError("事实ID重复。")
        for f in facts:
            if not f.get("statement") or f.get("importance") not in {"core", "supporting"} or not f.get("kind"):
                raise ValueError("每项事实须有原始主张、分析类型及重要性。")
            if not f.get("anchors") or any(not isinstance(g, list) or not g for g in f["anchors"] + f.get("requires", [])):
                raise ValueError("事实的定位概念组须为非空别名列表；它们不代表核验通过。")
            if f.get("analysis_n") is not None and (type(f["analysis_n"]) is not int or f["analysis_n"] <= 0):
                raise ValueError("analysis_n须为实际分析的正整数分母。")
            if f.get("matrix") and any(type(f["matrix"].get(k)) is not int or f["matrix"][k] <= 0 for k in ("nodes", "features")):
                raise ValueError("矩阵节点与特征数须为正整数，不能自行补齐。")
        specs = [{"id": f["id"], "source_path": f["source"]["path"], "pages": f["source"].get("pages", []),
                  "source_locator": f["source"]["locator"], "source_excerpt": f["source"]["excerpt"]} for f in facts]
        cache = getattr(assets, "fact_source_cache", None)
        reused_source = bool(cache and cache.get("facts_sha256") == assets.digest(path)
                             and cache.get("source_manifest_sha256") == assets.digest(manifest))
        source_errors = cache["source_errors"] if reused_source else source_excerpt_errors(specs, article, article_path, assets)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "SOURCE_REVIEW_REQUIRED", "items": [], "findings": [], "reason": str(exc)}

    article_sha, facts_sha = assets.digest(article_path), assets.digest(path)
    decision_path = article_path.parent / "work/fact-coverage-review.json"
    decisions = {}
    if decision_path.is_file():
        try:
            decision = json.loads(assets.read(decision_path))
            if decision.get("article_sha256") == article_sha and decision.get("facts_sha256") == facts_sha:
                decisions = {v["fact_id"]: v for v in decision.get("decisions", [])}
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Stale/malformed decisions never supply semantic approval.
    blocks = list(text_blocks(article))
    contexts = {}
    for si, section in enumerate(article.get("sections", [])):
        heading = ""
        for bi, block in enumerate(section.get("blocks", [])):
            if block.get("type") == "subheading":
                heading = block.get("text", "")
            contexts[f"/sections/{si}/blocks/{bi}/"] = heading
    def context(loc, text):
        match = re.match(r"/sections/\d+/blocks/\d+/", loc)
        prefix = match.group(0) if match else loc
        return contexts.get(prefix, "") + " " + text
    visible = " ".join(text for _, _, text in blocks)
    items, findings = [], []
    for fact in facts:
        source = fact["source"]
        active = matches(visible, fact.get("applies_when", fact["anchors"]))
        scope = fact.get("sections", [])
        relevant = [(loc, text) for loc, sid, text in blocks if matches(context(loc, text), fact["anchors"])]
        candidates = [(loc, text) for loc, sid, text in blocks
                      if (not scope or sid in scope) and matches(context(loc, text), fact["anchors"])]
        candidates.sort(key=lambda item: sum(matches(item[1], [g]) for g in fact.get("requires", [])), reverse=True)
        covered = [(loc, text) for loc, text in candidates if matches(text, fact.get("requires", []))]
        # Validation/sensitivity evidence is often distributed between Methods, Results and
        # Interpretation. Analysis denominators and interactions remain paragraph-scoped.
        if fact["kind"] in {"validation", "sensitivity"} and matches(" ".join(t for _, t in candidates), fact.get("requires", [])):
            covered = candidates
        missing = []
        numerical_mismatch = False
        if active and not covered:
            missing.append("未找到在相应分析位置同时覆盖必要计算/结果概念的正文，需核对是否重要遗漏。")
        if active and fact.get("each_location"):
            missing.extend(f"{loc}未说明来源中的测量对象/限定。" for loc, text in candidates
                           if not matches(text, fact.get("requires", [])))
        if active and fact.get("analysis_n") is not None:
            n = fact["analysis_n"]
            if not any(re.search(rf"(?:[nN]\s*[=＝]?\s*{n}\b|{n}\s*(?:人|名|例))", text) for _, text in candidates):
                missing.append(f"该分析来源分母n={n}，候选段未明确对应分母；不能套用总队列人数。")
        if active and fact.get("matrix"):
            matrix = fact["matrix"]
            n, total = matrix["nodes"], matrix["features"]
            between = n * (n - 1) // 2
            if matrix.get("includes_diagonal") and total == n * (n + 1) // 2:
                for loc, text in candidates:
                    for clause in re.split(r"[。；]", text):
                        if (re.search(rf"{total}.{{0,12}}(?:区域间|系统间|节点间)", clause)
                                and not any(term in clause for term in ("系统内", "区域内", "对角线", "含内部"))):
                            missing.append(f"{loc}把{total}项称为纯跨节点连接；{n}节点只有{between}个非重复跨节点项，来源还保留{n}个内部项。")
                            numerical_mismatch = True
        proposed = "misinterpreted" if numerical_mismatch else "important_omission" if missing and active else "reasonable_omission" if not active else "accurate"
        item = {"fact_id": fact["id"], "kind": fact["kind"], "importance": fact["importance"],
                "statement": fact["statement"], "source_path": source["path"], "source_locator": source["locator"],
                "pages": source.get("pages", []), "source_excerpt": source["excerpt"],
                "article_locations": [loc for loc, _ in (candidates or relevant)[:3]],
                "candidate_excerpts": [{"location": loc, "text": text[:500]} for loc, text in (candidates or relevant)[:3]],
                "automatic_suspicions": missing, "proposed_status": proposed, "status": "needs_review",
                "suggestion": "按给出的来源定位核对；只补会改变定义/解释的内容，或记录来源支持的合理省略理由。"}
        if fact["id"] in source_errors:
            item.update(status="source_insufficient", reason=source_errors[fact["id"]])
        else:
            decision = decisions.get(fact["id"], {})
            status = decision.get("status")
            reason = str(decision.get("reason", "")).strip()
            locations = decision.get("article_locations", [])
            excerpt = str(decision.get("article_excerpt", "")).strip()
            quoted = len(excerpt) >= 8 and any(excerpt in pointer(article, loc) for loc in locations)
            # An actual body excerpt plus source-supported explanation is needed; verified is ignored.
            if status in VERDICTS and len(reason) >= 16 and (status == "reasonable_omission" or quoted):
                item.update(status=status, reason=reason, article_locations=locations,
                            semantic_article_excerpt=excerpt, origin="existing_semantic_QA")
        if item["status"] not in ACCEPTED and (missing or item["status"] in VERDICTS):
            ident = hashlib.sha256((fact["id"] + article_sha + facts_sha).encode()).hexdigest()[:20]
            findings.append({"id": ident, "risk": "fact_coverage", "location": ",".join(item["article_locations"]) or "/sections",
                             "text": fact["statement"], "source_locator": source["locator"], "fact_id": fact["id"],
                             "status": "needs_review", "blocking": False,
                             "check": "; ".join(missing) or item.get("reason", item["status"]),
                             "origin": "source_fact_comparison"})
        items.append(item)
    complete = all(item["status"] in ACCEPTED for item in items)
    return {"status": "REVIEWED" if complete else "SOURCE_REVIEW_REQUIRED", "article_sha256": article_sha,
            "facts_sha256": facts_sha, "source_manifest_sha256": assets.digest(manifest),
            "source_errors": source_errors, "source_validation_reused": reused_source,
            "items": items, "findings": findings,
            "limitations": "概念/分母检查仅定位候选；关键词齐全、摘录存在和verified均不证明科学支持。最终结论来自现有语义审校。"}


def coverage_gate(report):
    if report.get("status") in {"REVIEWED", "NOT_REQUIRED"}:
        return []
    pending = [f"{i['fact_id']}:{i['status']}" for i in report.get("items", []) if i["status"] not in ACCEPTED]
    return ["关键来源事实覆盖尚未完成：" + (", ".join(pending) or report.get("reason", "缺少来源核查"))]


def render_facts(report):
    lines = ["# 来源事实与覆盖核查（内部）", "", report.get("limitations", report.get("reason", "")), ""]
    for item in report.get("items", []):
        lines.extend([f"## {item['fact_id']} / {item['kind']}", item["statement"],
                      f"来源：{item['source_locator']}；PDF页{item['pages']}",
                      f"短摘录：{item['source_excerpt']}", f"正文：{', '.join(item['article_locations'])}",
                      f"结论：{item['status']}（自动建议{item['proposed_status']}）", item.get("reason", "待现有语义QA核查。"), ""])
    return "\n".join(lines)
