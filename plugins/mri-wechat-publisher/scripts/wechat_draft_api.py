#!/usr/bin/env python3
"""Draft-only WeChat Official Account API client.

The command is a dry run unless both --execute and the exact approval token are
provided. It intentionally contains no publish, mass-send, update-live, or
delete operations.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from validate_article import load_article, validate_article


API_BASE = "https://api.weixin.qq.com"
APPROVAL_TOKEN = "USER_APPROVED_DRAFT_ONLY"


class WeChatApiError(RuntimeError):
    """A non-secret WeChat API failure."""


def load_env_file(path: Path) -> None:
    """Load missing variables from a local .env file without printing values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


def credential_presence() -> dict[str, bool]:
    return {
        "WECHAT_APP_ID": bool(os.environ.get("WECHAT_APP_ID", "").strip()),
        "WECHAT_APP_SECRET": bool(os.environ.get("WECHAT_APP_SECRET", "").strip()),
    }


def parse_api_json(raw: bytes, status_code: int, operation: str) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WeChatApiError(f"{operation} 返回了非 JSON 响应，HTTP {status_code}。") from exc
    if not isinstance(data, dict):
        raise WeChatApiError(f"{operation} 返回结构异常。")
    errcode = data.get("errcode")
    if errcode not in (None, 0):
        errmsg = str(data.get("errmsg", "unknown error"))
        raise WeChatApiError(f"{operation} 失败：errcode={errcode}, errmsg={errmsg}")
    return data


def post_json(url: str, payload: dict[str, Any], operation: str) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            return parse_api_json(response.read(), response.status, operation)
    except error.HTTPError as exc:
        raw = exc.read()
        if raw:
            return parse_api_json(raw, exc.code, operation)
        raise WeChatApiError(f"{operation} HTTP 失败：{exc.code}。") from exc
    except error.URLError as exc:
        raise WeChatApiError(f"{operation} 网络连接失败。") from exc


def post_media(
    url: str,
    path: Path,
    operation: str,
    field_name: str = "media",
) -> dict[str, Any]:
    boundary = f"----mriwechat{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    body = head + path.read_bytes() + tail
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            return parse_api_json(response.read(), response.status, operation)
    except error.HTTPError as exc:
        raw = exc.read()
        if raw:
            return parse_api_json(raw, exc.code, operation)
        raise WeChatApiError(f"{operation} HTTP 失败：{exc.code}。") from exc
    except error.URLError as exc:
        raise WeChatApiError(f"{operation} 网络连接失败。") from exc


def get_stable_token(app_id: str, app_secret: str) -> str:
    data = post_json(
        f"{API_BASE}/cgi-bin/stable_token",
        {
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
            "force_refresh": False,
        },
        "获取稳定版接口调用凭据",
    )
    token = str(data.get("access_token", "")).strip()
    if not token:
        raise WeChatApiError("获取稳定版接口调用凭据成功响应中缺少 access_token。")
    return token


def upload_content_image(token: str, path: Path) -> str:
    url = f"{API_BASE}/cgi-bin/media/uploadimg?{parse.urlencode({'access_token': token})}"
    data = post_media(url, path, f"上传正文图片 {path.name}")
    url = str(data.get("url", "")).strip()
    if not url:
        raise WeChatApiError(f"上传正文图片 {path.name} 的响应缺少 URL。")
    return url


def upload_cover_material(token: str, path: Path) -> str:
    query = parse.urlencode({"access_token": token, "type": "image"})
    url = f"{API_BASE}/cgi-bin/material/add_material?{query}"
    data = post_media(url, path, f"上传封面素材 {path.name}")
    media_id = str(data.get("media_id", "")).strip()
    if not media_id:
        raise WeChatApiError(f"上传封面素材 {path.name} 的响应缺少 media_id。")
    return media_id


def add_draft(token: str, article: dict[str, Any], content: str, thumb_media_id: str) -> str:
    settings = article.get("settings") or {}
    payload = {
        "articles": [
            {
                "title": article["title"],
                "author": article["author"],
                "digest": article["digest"],
                "content": content,
                "content_source_url": article.get("content_source_url", ""),
                "thumb_media_id": thumb_media_id,
                "need_open_comment": int(settings.get("need_open_comment", 0)),
                "only_fans_can_comment": int(settings.get("only_fans_can_comment", 0)),
            }
        ]
    }
    query = parse.urlencode({"access_token": token})
    data = post_json(f"{API_BASE}/cgi-bin/draft/add?{query}", payload, "新增草稿")
    media_id = str(data.get("media_id", "")).strip()
    if not media_id:
        raise WeChatApiError("新增草稿响应中缺少 media_id。")
    return media_id


def get_draft(token: str, media_id: str) -> dict[str, Any]:
    query = parse.urlencode({"access_token": token})
    data = post_json(
        f"{API_BASE}/cgi-bin/draft/get?{query}",
        {"media_id": media_id},
        "回读草稿",
    )
    news_items = data.get("news_item")
    if not isinstance(news_items, list) or not news_items:
        raise WeChatApiError("回读草稿成功响应中缺少 news_item。")
    titles = [str(item.get("title", "")) for item in news_items if isinstance(item, dict)]
    return {"article_count": len(news_items), "titles": titles}


def resolve_article_asset(article_path: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = article_path.parent / candidate
    return candidate.resolve()


def rewrite_inline_images(
    token: str,
    article: dict[str, Any],
    article_path: Path,
    content: str,
) -> tuple[str, list[dict[str, str]]]:
    uploaded: list[dict[str, str]] = []
    for figure in article.get("figures", []):
        asset_id = figure["asset_id"]
        marker = f"wechat-asset://{asset_id}"
        if marker not in content:
            continue
        figure_path = resolve_article_asset(article_path, figure["path"])
        if not figure_path.is_file():
            raise WeChatApiError(f"正文图片不存在：{figure_path}")
        url = upload_content_image(token, figure_path)
        content = content.replace(marker, url)
        uploaded.append({"asset_id": asset_id, "url": url})
    if "wechat-asset://" in content:
        raise WeChatApiError("正文仍包含未解析的本地图片占位符。")
    return content, uploaded


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a WeChat draft; publishing is unsupported.")
    parser.add_argument("article", type=Path)
    parser.add_argument("html", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--cover", type=Path, help="Override article.cover.path.")
    parser.add_argument("--receipt", type=Path, default=Path("output/draft-receipt.json"))
    parser.add_argument(
        "--check-token-only",
        action="store_true",
        help="Validate credentials by requesting a stable token without printing it or writing a draft.",
    )
    parser.add_argument(
        "--verify-media-id",
        default="",
        help="Read back an existing draft by media ID without creating or modifying anything.",
    )
    parser.add_argument("--execute", action="store_true", help="Perform the live draft write.")
    parser.add_argument("--approval-token", default="")
    args = parser.parse_args()

    article_path = args.article.resolve()
    html_path = args.html.resolve()
    plugin_root = Path(__file__).resolve().parents[1]
    workspace_env = plugin_root.parents[1] / ".env"
    env_path = (args.env_file or workspace_env).resolve()
    load_env_file(env_path)

    try:
        article = load_article(article_path)
        qa = validate_article(article, article_path)
        if qa["status"] != "QA_PASSED":
            raise WeChatApiError("文章未通过 QA，禁止进入草稿箱。")
        if article.get("publication_mode") != "draft_only":
            raise WeChatApiError("publication_mode 不是 draft_only。")
        if not html_path.is_file():
            raise WeChatApiError(f"HTML 文件不存在：{html_path}")
        content = html_path.read_text(encoding="utf-8")

        if args.check_token_only:
            presence = credential_presence()
            if not all(presence.values()):
                raise WeChatApiError(
                    f"本地凭据未配置完整：{presence}。请勿在聊天中粘贴 AppSecret。"
                )
            app_id = os.environ["WECHAT_APP_ID"].strip()
            app_secret = os.environ["WECHAT_APP_SECRET"].strip()
            get_stable_token(app_id, app_secret)
            print(
                json.dumps(
                    {
                        "status": "TOKEN_CHECK_PASSED",
                        "credential_presence": presence,
                        "access_token_received": True,
                        "draft_written": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        if args.verify_media_id:
            presence = credential_presence()
            if not all(presence.values()):
                raise WeChatApiError(
                    f"本地凭据未配置完整：{presence}。请勿在聊天中粘贴 AppSecret。"
                )
            app_id = os.environ["WECHAT_APP_ID"].strip()
            app_secret = os.environ["WECHAT_APP_SECRET"].strip()
            token = get_stable_token(app_id, app_secret)
            verification = get_draft(token, args.verify_media_id.strip())
            print(
                json.dumps(
                    {
                        "status": "DRAFT_GET_PASSED",
                        "draft_written": False,
                        **verification,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        cover_value = args.cover
        if cover_value is None and isinstance(article.get("cover"), dict):
            cover_value = Path(article["cover"]["path"])

        plan = {
            "status": "DRY_RUN_READY" if not args.execute else "EXECUTION_REQUESTED",
            "transport": "wechat_draft_api",
            "publication_mode": "draft_only",
            "article_id": article["article_id"],
            "title": article["title"],
            "credential_presence": credential_presence(),
            "inline_image_count": len(article.get("figures", [])),
            "cover_configured": cover_value is not None,
            "operations": ["stable_token", "upload_content_images", "upload_cover_material", "add_draft"],
        }
        if not args.execute:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return 0

        if args.approval_token != APPROVAL_TOKEN:
            raise WeChatApiError(
                f"实时写入需要 --approval-token {APPROVAL_TOKEN}；该标记只能在用户明确同意保存草稿后使用。"
            )
        presence = credential_presence()
        if not all(presence.values()):
            raise WeChatApiError(f"本地凭据未配置完整：{presence}。不要在聊天中粘贴 AppSecret。")
        if cover_value is None:
            raise WeChatApiError("API 新增草稿需要封面图片。")

        cover_path = resolve_article_asset(article_path, str(cover_value))
        if not cover_path.is_file():
            raise WeChatApiError(f"封面文件不存在：{cover_path}")

        app_id = os.environ["WECHAT_APP_ID"].strip()
        app_secret = os.environ["WECHAT_APP_SECRET"].strip()
        token = get_stable_token(app_id, app_secret)
        rewritten_content, uploaded_images = rewrite_inline_images(token, article, article_path, content)
        thumb_media_id = upload_cover_material(token, cover_path)
        draft_media_id = add_draft(token, article, rewritten_content, thumb_media_id)

        receipt = {
            "status": "DRAFT_SAVED",
            "transport": "wechat_draft_api",
            "publication_mode": "draft_only",
            "article_id": article["article_id"],
            "title": article["title"],
            "draft_media_id": draft_media_id,
            "uploaded_inline_images": uploaded_images,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        write_receipt(args.receipt.resolve(), receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, WeChatApiError, RuntimeError) as exc:
        print(json.dumps({"status": "DRAFT_SAVE_BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
