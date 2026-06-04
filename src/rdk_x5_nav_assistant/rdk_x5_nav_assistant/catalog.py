"""Catalog and route helpers shared by the navigation assistant nodes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml


COMMAND_KEYWORDS = {
    "stop": ("停止", "暂停", "别动", "stop", "pause"),
    "repeat": ("重复", "再说一遍", "repeat"),
    "confirm": ("确认", "拿到", "已经拿到", "完成", "done", "ok"),
    "return": ("返回", "回入口", "回到入口", "return"),
    "rescan": ("重新扫描", "重扫", "再扫描", "rescan", "scan again"),
}


def load_yaml(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    text = str(text).strip().lower()
    return re.sub(r"[\s,，。.!！?？:：;；\"'""''、]+", "", text)


def parse_intent_payload(payload: str) -> Dict[str, Any]:
    """Accept raw Chinese text or JSON payloads from ASR/LLM nodes."""
    payload = payload.strip()
    if not payload:
        return {"text": ""}
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {"text": payload}
    if isinstance(parsed, dict):
        parsed.setdefault("text", payload)
        return parsed
    return {"text": str(parsed)}


def detect_command(text: str) -> Optional[str]:
    normalized = normalize_text(text)
    for command, keywords in COMMAND_KEYWORDS.items():
        if any(normalize_text(keyword) in normalized for keyword in keywords):
            return command
    return None


def product_terms(product: Dict[str, Any]) -> Iterable[str]:
    yield product.get("id", "")
    yield product.get("name", "")
    for alias in product.get("aliases", []) or []:
        yield alias


def find_product(intent: Dict[str, Any], catalog: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the best product by id, Chinese name, alias, or text containment."""
    candidates = []
    for key in ("product_id", "product", "name", "target", "text"):
        value = intent.get(key)
        if value:
            candidates.append(normalize_text(value))

    products = catalog.get("products", []) or []
    for candidate in candidates:
        if not candidate:
            continue
        for product in products:
            terms = [normalize_text(term) for term in product_terms(product)]
            if candidate in terms:
                return product
        for product in products:
            terms = [normalize_text(term) for term in product_terms(product)]
            if any(term and term in candidate for term in terms):
                return product
    return None


def product_by_id(product_id: str, catalog: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    wanted = normalize_text(product_id)
    for product in catalog.get("products", []) or []:
        if normalize_text(product.get("id")) == wanted:
            return product
    return None


def product_by_tag_id(tag_id: int, catalog: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find product by its AprilTag ID."""
    for product in catalog.get("products", []) or []:
        if product.get("apriltag_id") == tag_id:
            return product
    return None


def shelf_for_product(product: Dict[str, Any], store_map: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    shelf_id = product.get("shelf_id")
    for shelf in store_map.get("shelves", []) or []:
        if shelf.get("id") == shelf_id:
            return shelf
    return None


def waypoint_by_id(waypoint_id: str, store_map: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for waypoint in store_map.get("waypoints", []) or []:
        if waypoint.get("id") == waypoint_id:
            return waypoint
    return None


def tag_by_id(tag_id: int | str, store_map: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tag_id_text = str(tag_id)
    for tag in store_map.get("apriltags", []) or []:
        if str(tag.get("id")) == tag_id_text:
            return tag
    return None
