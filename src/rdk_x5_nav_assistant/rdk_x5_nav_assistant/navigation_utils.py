"""Semantic-route helpers for hand-pushed navigation guidance."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


Pose2D = Tuple[float, float, float]


def pose_xy(pose: Any) -> Optional[Tuple[float, float]]:
    if isinstance(pose, (list, tuple)) and len(pose) >= 2:
        try:
            return float(pose[0]), float(pose[1])
        except (TypeError, ValueError):
            return None
    if isinstance(pose, dict):
        try:
            return float(pose["x"]), float(pose["y"])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def waypoint_by_id(store_map: Dict[str, Any], waypoint_id: str) -> Optional[Dict[str, Any]]:
    for waypoint in store_map.get("waypoints", []) or []:
        if waypoint.get("id") == waypoint_id:
            return waypoint
    return None


def shelf_tag_matches(store_map: Dict[str, Any], shelf_id: Optional[str], tag_event: Optional[Dict[str, Any]]) -> bool:
    if not shelf_id or not tag_event:
        return False
    tag_id = tag_event.get("id")
    if tag_id is None:
        return False
    for tag in store_map.get("apriltags", []) or []:
        if str(tag.get("id")) == str(tag_id):
            return tag.get("shelf_id") == shelf_id
    return False


def route_for_product(product: Dict[str, Any], routes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    route_id = product.get("route_id")
    for route in routes.get("routes", []) or []:
        if route.get("id") == route_id or route.get("product_id") == product.get("id"):
            return route
    return None


def route_waypoints(route: Optional[Dict[str, Any]], store_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not route:
        return []
    waypoints = []
    for waypoint_id in route.get("waypoints", []) or []:
        waypoint = waypoint_by_id(store_map, waypoint_id)
        if waypoint:
            waypoints.append(waypoint)
    return waypoints


def waypoint_distance(current_xy: Tuple[float, float], waypoint: Dict[str, Any]) -> Optional[float]:
    target_xy = pose_xy(waypoint.get("pose"))
    if target_xy is None:
        return None
    return math.dist(current_xy, target_xy)


def nearest_route_distance(current_xy: Tuple[float, float], waypoints: List[Dict[str, Any]]) -> Optional[float]:
    distances = [waypoint_distance(current_xy, waypoint) for waypoint in waypoints]
    distances = [distance for distance in distances if distance is not None]
    return min(distances) if distances else None


class RouteGuide:
    """Track waypoint progress without ever commanding robot motion."""

    def __init__(
        self,
        store_map: Dict[str, Any],
        route: Dict[str, Any],
        shelf: Optional[Dict[str, Any]] = None,
        default_radius_m: float = 0.8,
        prepare_radius_m: float = 1.4,
        off_route_threshold_m: float = 2.0,
    ) -> None:
        self.store_map = store_map
        self.route = route
        self.shelf = shelf or {}
        self.waypoints = route_waypoints(route, store_map)
        self.default_radius_m = float(default_radius_m)
        self.prepare_radius_m = float(prepare_radius_m)
        self.off_route_threshold_m = float(off_route_threshold_m)
        self.index = 0 if len(self.waypoints) <= 1 else 1

    def update(
        self,
        current_xy: Optional[Tuple[float, float]],
        tag_event: Optional[Dict[str, Any]] = None,
        localization_status: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if localization_status and localization_status.get("status") in ("low", "stale", "unavailable"):
            return self._event(
                "localization_low",
                "定位置信度较低，请缓慢移动并面向通道，重新定位",
                localization_status=localization_status,
            )
        if current_xy is None:
            return self._event("localization_unavailable", "暂时没有定位，请缓慢移动并面向通道")
        if not self.waypoints:
            return self._event("route_unavailable", "当前商品还没有配置路线，请原地扫描货架")

        nearest = nearest_route_distance(current_xy, self.waypoints)
        if nearest is not None and nearest > self.off_route_threshold_m:
            return self._event(
                "off_route",
                "当前位置偏离路线，请回到主通道后继续",
                distance_m=round(nearest, 3),
            )

        self.index = min(self.index, len(self.waypoints) - 1)
        target = self.waypoints[self.index]
        distance = waypoint_distance(current_xy, target)
        if distance is None:
            return self._event("route_unavailable", "路线点坐标缺失，请检查语义地图")

        radius = float(target.get("trigger_radius_m") or target.get("arrival_radius_m") or self.default_radius_m)
        tag_verified = shelf_tag_matches(self.store_map, self.shelf.get("id"), tag_event)
        is_final = self.index >= len(self.waypoints) - 1

        if distance <= radius:
            if is_final:
                text = str(target.get("arrival_text") or f"已到达{self.shelf.get('name', '目标货架')}附近，请面向货架")
                return self._event(
                    "arrived_shelf",
                    text,
                    waypoint=target,
                    distance_m=round(distance, 3),
                    tag_verified=tag_verified,
                )
            self.index += 1
            next_waypoint = self.waypoints[self.index]
            turn_hint = target.get("turn_hint") or next_waypoint.get("approach_hint")
            text = str(turn_hint or next_waypoint.get("voice_hint") or f"已到达{target.get('name')}，请继续前进")
            return self._event(
                "waypoint_reached",
                text,
                waypoint=target,
                next_waypoint=next_waypoint,
                distance_m=round(distance, 3),
                tag_verified=tag_verified,
            )

        if distance <= float(target.get("prepare_radius_m") or self.prepare_radius_m):
            text = str(target.get("prepare_text") or target.get("voice_hint") or f"准备靠近{target.get('name')}")
            action = "prepare_turn" if target.get("turn_hint") else "approach_waypoint"
            return self._event(
                action,
                text,
                waypoint=target,
                distance_m=round(distance, 3),
                tag_verified=tag_verified,
            )

        text = str(target.get("voice_hint") or self.route.get("voice_hint") or "请沿路线继续前进")
        return self._event(
            "continue_forward",
            text,
            waypoint=target,
            distance_m=round(distance, 3),
            tag_verified=tag_verified,
        )

    def _event(self, action: str, spoken: str, **extra: Any) -> Dict[str, Any]:
        waypoint = extra.pop("waypoint", None)
        next_waypoint = extra.pop("next_waypoint", None)
        payload = {
            "action": action,
            "spoken": spoken,
            "route_id": self.route.get("id"),
            "route_index": self.index,
            "shelf_id": self.shelf.get("id"),
            "shelf_name": self.shelf.get("name"),
            **extra,
        }
        if waypoint:
            payload["waypoint_id"] = waypoint.get("id")
            payload["waypoint_name"] = waypoint.get("name")
        if next_waypoint:
            payload["next_waypoint_id"] = next_waypoint.get("id")
            payload["next_waypoint_name"] = next_waypoint.get("name")
        return payload
