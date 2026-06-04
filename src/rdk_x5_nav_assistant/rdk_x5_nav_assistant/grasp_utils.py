"""Lightweight grasp-verification helpers for the navigation board.

This board does NOT process images. It relies on product_pose and tag_event
published by the vision board. Depth and hand landmarks are optional extras
if the vision board forwards them.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def verify_grasp_event(
    *,
    target_product: Optional[Dict[str, Any]],
    product_pose: Optional[Dict[str, Any]],
    tag_event: Optional[Dict[str, Any]] = None,
    target_recently_lost: bool = False,
    wrong_tag_seen: bool = False,
    user_confirmed: bool = False,
) -> Dict[str, Any]:
    """Return a grasp event based on available perception data.

    Navigation board version: no image processing. Relies on:
    - product_pose (from vision board)
    - tag_event (from vision board)
    - user_confirmed (from voice/gesture)
    """
    if wrong_tag_seen:
        name = target_product.get("name") if target_product else "目标商品"
        return {
            "event": "wrong_item_possible",
            "confidence": 0.75,
            "spoken": f"当前识别到的商品不是{name}，请不要拿取，重新对准目标",
        }

    if user_confirmed and target_recently_lost:
        # User says "done" and target just disappeared from view
        return {
            "event": "correct_item_grasped",
            "confidence": 0.55,
            "spoken": "用户已确认，系统判断已拿到正确商品",
        }

    if product_pose is None:
        if target_recently_lost:
            return {
                "event": "grasp_uncertain",
                "confidence": 0.4,
                "spoken": "目标从画面中消失，请确认是否拿到正确商品",
            }
        return {"event": "waiting", "confidence": 0.0, "spoken": ""}

    distance = product_pose.get("distance")
    offset_x = product_pose.get("offset_x", 0.0)

    if distance is not None and distance <= 0.35 and abs(offset_x) <= 0.15:
        return {
            "event": "hand_near_target",
            "confidence": 0.65,
            "distance_m": round(distance, 3),
            "spoken": "已到伸手可拿范围，请轻轻抓取商品",
        }

    if distance is not None:
        hint = ""
        if distance > 0.5:
            hint = "请继续靠近目标商品"
        elif offset_x > 0.1:
            hint = "目标偏右，请向右移动"
        elif offset_x < -0.1:
            hint = "目标偏左，请向左移动"
        else:
            hint = "请继续靠近目标商品"
        return {
            "event": "tracking_target",
            "confidence": 0.4,
            "distance_m": round(distance, 3),
            "spoken": hint,
        }

    return {
        "event": "tracking_target",
        "confidence": 0.35,
        "spoken": "已锁定目标商品，请继续靠近",
    }
