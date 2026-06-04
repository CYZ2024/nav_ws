#!/usr/bin/env python3
"""Voice navigation guide driven by semantic waypoints and localization."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import String

from .catalog import load_yaml, product_by_id, shelf_for_product
from .navigation_utils import RouteGuide, route_for_product


def _json_msg(payload: Dict[str, Any]) -> String:
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


class NavigationGuideNode(Node):
    def __init__(self) -> None:
        super().__init__("navigation_guide_node")
        self.declare_parameter("product_catalog_path", "")
        self.declare_parameter("store_map_path", "")
        self.declare_parameter("demo_routes_path", "")
        self.declare_parameter("target_product_topic", "/assistant/target_product")
        self.declare_parameter("localization_pose_topic", "/assistant/localization_pose")
        self.declare_parameter("localization_status_topic", "/assistant/localization_status")
        self.declare_parameter("tag_event_topic", "/assistant/tag_event")
        self.declare_parameter("navigation_event_topic", "/assistant/navigation_event")
        self.declare_parameter("tts_topic", "/tts_text")
        self.declare_parameter("default_radius_m", 0.8)
        self.declare_parameter("prepare_radius_m", 1.4)
        self.declare_parameter("off_route_threshold_m", 2.0)
        self.declare_parameter("repeat_s", 3.5)
        self.declare_parameter("publish_rate_hz", 2.0)

        catalog_path = self.get_parameter("product_catalog_path").value
        store_map_path = self.get_parameter("store_map_path").value
        routes_path = self.get_parameter("demo_routes_path").value
        if not catalog_path or not store_map_path or not routes_path:
            raise RuntimeError("product_catalog_path, store_map_path, and demo_routes_path are required")
        self.catalog = load_yaml(catalog_path)
        self.store_map = load_yaml(store_map_path)
        self.routes = load_yaml(routes_path)

        self.current_product: Optional[Dict[str, Any]] = None
        self.current_shelf: Optional[Dict[str, Any]] = None
        self.guide: Optional[RouteGuide] = None
        self.current_xy: Optional[Tuple[float, float]] = None
        self.last_tag_event: Optional[Dict[str, Any]] = None
        self.localization_status: Dict[str, Any] = {}
        self.last_spoken_text = ""
        self.last_spoken_time = 0.0

        self.event_pub = self.create_publisher(String, self.get_parameter("navigation_event_topic").value, 10)
        self.tts_pub = self.create_publisher(String, self.get_parameter("tts_topic").value, 10)

        self.create_subscription(String, self.get_parameter("target_product_topic").value, self._on_target_product, 10)
        self.create_subscription(PoseStamped, self.get_parameter("localization_pose_topic").value, self._on_pose, 10)
        self.create_subscription(String, self.get_parameter("localization_status_topic").value, self._on_localization_status, 10)
        self.create_subscription(String, self.get_parameter("tag_event_topic").value, self._on_tag_event, 10)
        hz = max(0.2, float(self.get_parameter("publish_rate_hz").value))
        self.timer = self.create_timer(1.0 / hz, self._tick)
        self.get_logger().info("Navigation guide node is ready")

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _on_target_product(self, msg: String) -> None:
        payload = self._loads(msg.data)
        product_id = payload.get("product_id") or payload.get("id") or payload.get("name")
        product = product_by_id(str(product_id), self.catalog) if product_id else None
        if product is None:
            self.current_product = None
            self.current_shelf = None
            self.guide = None
            return
        route = route_for_product(product, self.routes)
        shelf = shelf_for_product(product, self.store_map)
        self.current_product = product
        self.current_shelf = shelf
        self.guide = (
            RouteGuide(
                self.store_map,
                route,
                shelf,
                float(self.get_parameter("default_radius_m").value),
                float(self.get_parameter("prepare_radius_m").value),
                float(self.get_parameter("off_route_threshold_m").value),
            )
            if route
            else None
        )
        if self.guide is None:
            self._publish({"action": "route_unavailable", "spoken": "当前商品还没有配置路线，请原地扫描货架"})

    def _on_pose(self, msg: PoseStamped) -> None:
        self.current_xy = (float(msg.pose.position.x), float(msg.pose.position.y))

    def _on_localization_status(self, msg: String) -> None:
        self.localization_status = self._loads(msg.data)

    def _on_tag_event(self, msg: String) -> None:
        self.last_tag_event = self._loads(msg.data)

    def _tick(self) -> None:
        if self.guide is None:
            return
        event = self.guide.update(self.current_xy, self.last_tag_event, self.localization_status)
        event["product_id"] = self.current_product.get("id") if self.current_product else None
        event["product_name"] = self.current_product.get("name") if self.current_product else None
        event["stamp_ns"] = self.get_clock().now().nanoseconds
        self._publish(event)

    def _publish(self, event: Dict[str, Any]) -> None:
        self.event_pub.publish(_json_msg(event))
        spoken = str(event.get("spoken") or "")
        if spoken:
            self._say(spoken)

    def _say(self, text: str) -> None:
        now = self._now()
        repeat_s = float(self.get_parameter("repeat_s").value)
        if text == self.last_spoken_text and now - self.last_spoken_time < repeat_s:
            return
        msg = String()
        msg.data = text
        self.tts_pub.publish(msg)
        self.last_spoken_text = text
        self.last_spoken_time = now

    @staticmethod
    def _loads(data: str) -> Dict[str, Any]:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return {"text": data}
        return payload if isinstance(payload, dict) else {"value": payload}


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = NavigationGuideNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
