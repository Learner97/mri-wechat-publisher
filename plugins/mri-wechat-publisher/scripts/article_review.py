"""Offline review leads, not a scientific truth classifier or an extra model call."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

RISK_CHECKS = {
    "subtype_stage": "核对分型是否具有纵向转变证据，不能把聚类顺序当必经阶段。",
    "crosssection_change": "核对设计与分析单位：组间差异是否被写成个体变化或变化速度。",
    "association_causality": "核对因果方向及干预证据，区分观察、作者解释与编辑推断。",
    "mr_assumptions": "核对MR工具变量假设、方向性、多效性及敏感性结果。",
    "interaction_inference": "核对直接组间比较或交互；一组显著、另一组不显著不证明组差。",
    "validation_scope": "核对训练/内部测试/外部样本、事后亚组与独立临床验证。",
    "metric_interpretation": "核对AUC/准确率/R²/相关系数/效应量的定义及尺度。",
    "spatial_to_individual": "核对空间脑区对应是否被写成个体层面的预测或关联。",
    "metric_definition": "核对计算对象、单位、维度、对角线、归一化、独立计算或投影及生理解释。",
    "sample_denominator": "核对本项分析的样本分母、子样本、配对及统计单位。",
    "key_result_omission": "补回影响主要结论的必要结果/阴性或敏感性分析及其正文定位。",
    "null_independence": "未检出显著相关不证明完全独立或不存在共享；核对原估计、区间及解释强度。",
}


def qualified(clause):
    """Local claim polarity: a caution cannot mask a later affirmative contrast."""
    assertion = re.search(r"导致|引起|造成|驱动|证明|确定.*机制|完全独立|遗传独立|必经|必然演变|独立临床验证", clause)
    prefix = clause[max(0, assertion.start() - 28):assertion.start()] if assertion else clause
    negative = re.search(r"不能|无法|不等同|不等于|不构成|不是|并非|不代表|尚未证实|没有证据|不足以|尚不足|尚难|未能|不意味着", prefix)
    conditional = re.search(r"如果|若|只有", clause) and re.search(r"干预|随机|操纵|实验|工具变量", clause) and re.search(r"才(?:能|可)|尚需|有待", clause)
    return bool(negative or conditional)


def pointer(article, path):
    """Resolve the optional evidence-map JSON pointer; only visible text is accepted."""
    try:
        value = article
        for part in path.lstrip("/").split("/"):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value if isinstance(value, str) else ""
    except (KeyError, IndexError, ValueError, TypeError):
        return ""


def text_blocks(article):
    yield "/title", "title", article.get("title", "")
    yield "/digest", "digest", article.get("digest", "")
    for si, section in enumerate(article.get("sections", [])):
        for bi, block in enumerate(section.get("blocks", [])):
            if block.get("type") in {"paragraph", "subheading", "callout"}:
                yield f"/sections/{si}/blocks/{bi}/text", section["id"], block.get("text", "")
            elif block.get("type") == "list":
                for i, text in enumerate(block.get("items", [])):
                    yield f"/sections/{si}/blocks/{bi}/items/{i}", section["id"], text


def review_article(article):
    blocks = list(text_blocks(article))
    method_context = " ".join(str(m.get(k, "")) for m in article.get("method_map", [])
                              for k in ("name", "purpose", "data", "statistics"))
    design = method_context + " " + " ".join(t for _, sid, t in blocks if sid == "methods")
    null_context = " ".join(t for _, _, t in blocks)
    findings = []

    def add(code, location, text, *, blocking=False):
        ident = hashlib.sha256(f"{code}\n{location}\n{text}".encode()).hexdigest()[:20]
        if any(f["risk"] == code and f["location"] == location for f in findings):
            return
        findings.append({"id": ident, "risk": code, "location": location, "text": text,
                         "status": "needs_review", "blocking": blocking, "check": RISK_CHECKS[code]})

    for location, _, text in blocks:
        # Each rule needs a design/claim combination. Negated cautions are not assertions.
        for sentence in re.split(r"[。！？；\n]|(?:但是|然而|不过|但|却)", text):
            if not sentence.strip():
                continue
            caution = qualified(sentence)
            if (not caution and re.search(r"未检出|未发现|未达到显著|不显著", null_context)
                    and re.search(r"完全独立|遗传独立|没有任何.*(?:遗传|关联)|毫无.*(?:相关|关联)|并不共享.{0,14}遗传|不存在.*(?:共享|相关)", sentence)
                    and not re.search(r"独立计算|独立样本", sentence)
                    and not ("不存在显著" in sentence and not re.search(r"完全独立|遗传独立", sentence))):
                add("null_independence", location, sentence)
            if not caution:
                if re.search(r"聚类|分型|亚型", sentence + design) and re.search(r"必经|依次经历|必然演变|必然发展|疾病发展阶段", sentence):
                    add("subtype_stage", location, sentence)
                if "横断面" in sentence + design and re.search(r"个体.*(?:逐渐|变化速度)|患者.*(?:依次|逐年)|萎缩更快|个体纵向变化", sentence):
                    add("crosssection_change", location, sentence)
                if re.search(r"相关|空间对应|空间关联|空间关系|富集|统计中介|PLS", sentence) and re.search(r"导致|引起|造成|驱动|决定了|证明.*因果|确定.*机制|直接机制|机制证据", sentence):
                    add("association_causality", location, sentence)
                if re.search(r"孟德尔随机化|\bMR\b", sentence + design) and re.search(r"证明.*因果|无条件.*因果|排除所有混杂|不受.*假设", sentence):
                    add("mr_assumptions", location, sentence)
                if re.search(r"交叉验证|内部测试|事后(?:分层|亚组)", sentence + design) and re.search(r"独立临床验证|成熟临床|可直接.*临床|证实.*治疗决策|完成.*外部验证", sentence):
                    add("validation_scope", location, sentence)
                if (re.search(r"AUC[^。；]{0,25}(?:即|意味着|相当于|表示|代表|等于)[^。；]{0,12}(?:准确率|正确诊断)|AUC准确率|R[²2][^。；]{0,25}(?:准确率|患者比例)", sentence, re.I)
                        or re.search(r"相关系数[^。；]{0,25}解释了?\s*\d+\s*%", sentence)):
                    add("metric_interpretation", location, sentence)
                if re.search(r"空间相关|空间对应|脑区间相关", sentence) and re.search(r"个体.*(?:预测|诊断|风险)", sentence):
                    add("spatial_to_individual", location, sentence)
                if re.search(r"(?:网络|连接)权重.*(?:实际|生理)能耗|静态指标.*变化速度|独立计算.*等同.*投影", sentence):
                    add("metric_definition", location, sentence)
                if re.search(r"总样本量.*(?:每项|所有子|每个子)分析|所有子分析.*总样本", sentence):
                    add("sample_denominator", location, sentence)
        # The invalid inference can span several sentences within one paragraph.
        if (re.search(r"(?:组.*显著.*组.*不显著|组.*[pP]\s*[<＜].*组.*[pP]\s*[>＞])", text)
                and re.search(r"(?:因此|所以|说明|表明).*(?:显著差异|显著不同|显著强于)", text)
                and not re.search(r"(?:不能|不代表|不足以|不意味着).{0,18}(?:组间|显著差异)|尚需.*交互|交互.*[pP]\s*[<＜]", text)):
            add("interaction_inference", location, text)

    for i, claim in enumerate(article.get("evidence_map", [])):
        locations = claim.get("article_locations", [])
        for code in claim.get("risk_tags", []):
            if code in RISK_CHECKS:
                targets = [(loc, pointer(article, loc)) for loc in locations]
                for loc, value in targets or [(f"/evidence_map/{i}/claim", claim["claim"])]:
                    add(code, loc, value or claim["claim"])
        if claim.get("essential_result"):
            result_locations = {loc for loc, sid, _ in blocks if sid in {"results", "result_interpretation"}}
            linked = [pointer(article, loc) for loc in locations
                      if loc in result_locations]
            if not any(linked) or (re.search(r"不显著|未发现|无显著|阴性", claim["claim"])
                                   and not any(re.search(r"不显著|未发现|无显著|阴性|未检出", s) for s in linked)):
                add("key_result_omission", f"/evidence_map/{i}/claim", claim["claim"], blocking=True)

    # Cheap candidate retrieval only. Paraphrase/claim-level judgement stays in manual QA.
    repetitions = []
    groups = {sid: [(loc, text) for loc, name, text in blocks if name == sid and len(text) >= 18]
              for sid in {"digest", "overview", "introduction", "results", "result_interpretation", "closing"}}
    for left, right in [("digest", "overview"), ("overview", "introduction"),
                        ("results", "result_interpretation"), ("result_interpretation", "closing")]:
        candidates = []
        for lp, lt in groups[left]:
            clean = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", lt).lower()
            a = {clean[i:i + 3] for i in range(len(clean) - 2)}
            for rp, rt in groups[right]:
                clean = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", rt).lower()
                b = {clean[i:i + 3] for i in range(len(clean) - 2)}
                shared = [c["claim_id"] for c in article.get("evidence_map", [])
                          if lp in c.get("article_locations", []) and rp in c.get("article_locations", [])]
                score = 2 * len(a & b) / max(1, len(a) + len(b))
                if shared or (min(len(a), len(b)) >= 6 and score >= .65):
                    candidates.append({"locations": [lp, rp], "shared_claims": shared,
                                       "similarity": round(score, 3), "action": "人工检查科学信息是否重复；不自动删除阴性结果或改写正文。"})
        repetitions.extend(sorted(candidates, key=lambda v: v["similarity"], reverse=True)[:3])
    return {"status": "REVIEW_REQUIRED" if findings else "NO_AUTOMATIC_FLAGS",
            "limitations": "规则只定位风险，零命中不代表科学核验通过。", "risks": findings, "repetition_candidates": repetitions}


def source_excerpt_errors(specs, article, article_path, assets):
    """Check registered bytes/locators, not whether an excerpt proves an interpretation."""
    import json
    manifest = article.get("source", {}).get("source_manifest", "")
    records = {}
    if manifest and not manifest.startswith("internal:"):
        data = json.loads(assets.read(article_path.parent / manifest))
        for item in [data.get("main_file", {})] + data.get("supplements", []):
            if item.get("path"):
                records[(article_path.parent / item["path"]).resolve()] = item
    # Batch the union of requested PDF pages; repeated facts do not reopen/re-extract them.
    requests = {}
    for r in specs:
        path = (article_path.parent / str(r.get("source_path", ""))).resolve()
        pages = r.get("pages", [])
        if path in records and path.suffix.lower() == ".pdf" and isinstance(pages, list):
            requests.setdefault(path, set()).update(n for n in pages if type(n) is int and n > 0)
    for path, pages in requests.items():
        try:
            assets.source_text(path, sorted(pages))
        except (OSError, ValueError, IndexError, TypeError):
            pass  # Identify each invalid locator below rather than discard the entire batch.
    errors = {}
    for r in specs:
        ident = r.get("id", "?")
        path = (article_path.parent / str(r.get("source_path", ""))).resolve()
        excerpt = re.sub(r"\s+", "", str(r.get("source_excerpt", "")))
        if path not in records or len(excerpt) < 12 or not r.get("source_locator"):
            errors[ident] = "摘录须来自已登记的主文/补充材料并有精确定位。"
            continue
        try:
            if records[path].get("sha256") and records[path]["sha256"] != assets.digest(path):
                raise ValueError("来源文件与登记SHA-256不一致。")
            text = assets.source_text(path, r.get("pages", []))
            if excerpt not in re.sub(r"\s+", "", text):
                raise ValueError("摘录未在指定来源位置找到；核对提取/OCR，不得编造。")
        except (OSError, ValueError, IndexError, TypeError, ET.ParseError) as exc:
            errors[ident] = str(exc)
    return errors


def check_resolutions(report, resolutions, article, article_path, assets):
    """Require source-bound excerpts, never a self-assigned verified flag alone."""
    by_id = {r.get("id"): r for r in resolutions if isinstance(r, dict)}
    errors, valid = [], []
    for finding in report["risks"]:
        if finding.get("risk") == "fact_coverage":
            continue  # Source coverage has its own bound semantic decisions; do not duplicate them.
        r = by_id.get(finding["id"], {})
        if finding.get("blocking"):
            errors.append(f"{finding['id']}: 必要结果必须先补入正文映射。")
        elif (r.get("decision") != "supported" or len(str(r.get("reason", "")).strip()) < 12):
            errors.append(f"{finding['id']}: 待来源复核，需具体定位、解释及来源摘录。")
        else:
            valid.append(r)
    errors.extend(f"{ident}: {reason}" for ident, reason in source_excerpt_errors(valid, article, article_path, assets).items())
    return errors
