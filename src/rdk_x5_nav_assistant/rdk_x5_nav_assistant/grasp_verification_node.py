#!/usr/bin/env python3
"""Lightweight grasp verification on the navigation board.

Does NOT process images directly. Subscribes to perception topics
published by the vision board:
  - /perception/product_pose  (vision board)
  - /assistant/tag_event      (vision board)
  - optional: /assistant/gesture_event for user confirmation

Emits /assistant/grasp_event for the task state machine.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .catalog import load_yaml, product_by_id, product_by_tag_id
from .grasp_utils import verify_grasp_event


def _json_msg(payload: Dict[str, Any]) -> String:
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


class GraspVerificationNode(Node):
    def __init__(self) -> None:
        super().__init__("grasp_verification_node")
        self.declare_parameter("product_catalog_path", "")
        self.declare_parameter("target_product_topic", "/assistant/target_product")
        self.declare_parameter("product_pose_topic", "/perception/product_pose")
        self.declare_parameter("tag_event_topic", "/assistant/tag_event")
        self.declare_parameter("gesture_event_topic", "/assistant/gesture_event")
        self.declare_parameter("grasp_event_topic", "/assistant/grasp_event")
        self.declare_parameter("product_stale_s", 1.5)
        self.declare_parameter("publish_rate_hz", 2.0)

        catalog_path = self.get_parameter("product_catalog_path").value
        if not catalog_path:
            raise RuntimeError("product_catalog_path is required")
        self.catalog = load_yaml(catalog_path)

        self.current_product: Optional[Dict[str, Any]] = None
        self.last_product_pose: Optional[Dict[str, Any]] = None
        self.last_product_pose_time = 0.0
        self.wrong_tag_seen = False
        self.last_event = ""
        self.user_confirmed = False

        self.event_pub = self.create_publisher(String, self.get_parameter("grasp_event_topic").value, 10)
        self.create_subscription(String, self.get_parameter("target_product_topic").value, self._on_target_product, 10)
        self.create_subscription(String, self.get_parameter("product_pose_topic").value, self._on_product_pose, 10)
        self.create_subscription(String, self.get_parameter("tag_event_topic").value, self._on_tag_event, 10)
        self.create_subscription(String, self.get_parameter("gesture_event_topic").value, self._on_gesture_event, 10)

        hz = max(0.2, float(self.get_parameter("publish_rate_hz").value))
        self.timer = self.create_timer(1.0 / hz, self._tick)
        self.get_logger().info("Grasp verification node is ready (navigation board, no vision)")

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _on_target_product(self, msg: String) -> None:
        payload = self._loads(msg.data)
        product_id = payload.get("product_id") or payload.get("id") or payload.get("name")
        product = product_by_id(str(product_id), self.catalog) if product_id else None
        self.current_product = product
        self.last_product_pose = None
        self.last_product_pose_time = 0.0
        self.wrong_tag_seen = False
        self.last_event = ""
        self.user_confirmed = False

    def _on_product_pose(self, msg: String) -> None:
        payload = self._loads(msg.data)
        if self.current_product and payload.get("target_product_id") != self.current_product.get("id"):
            return
        self.last_product_pose = payload
        self.last_product_pose_time = self._now()

    def _on_tag_event(self, msg: String) -> None:
        payload = self._loads(msg.data)
        try:
            tag_id = int(payload.get("id"))
        except (TypeError, ValueError):
            return
        product = product_by_tag_id(tag_id, self.catalog)
        if product is None or self.current_product is None:
            return
        self.wrong_tag_seen = product.get("id") != self.current_product.get("id")

    def _on_gesture_event(self, msg: String) -> None:
        payload = self._loads(msg.data)
        gesture = payload.get("gesture") or payload.get("action", "")
        if gesture in ("confirm", "ok", "done"):
            self.user_confirmed = True

    def _tick(self) -> None:
        if self.current_product is None:
            return
        now = self._now()
        stale_s = float(self.get_parameter("product_stale_s").value)
        target_lost = bool(self.last_product_pose and now - self.last_product_pose_time > stale_s)
        pose = None if target_lost else self.last_product_pose

        event = verify_grasp_event(
            target_product=self.current_product,
            product_pose=pose,
            tag_event=None,
            target_recently_lost=target_lost,
            wrong_tag_seen=self.wrong_tag_seen,
            user_confirmed=self.user_confirmed,
        )
        if event["event"] == "wrong_item_possible":
            self.wrong_tag_seen = False

        event.update(
            {
                "product_id": self.current_product.get("id"),
                "product_name": self.current_product.get("name"),
                "target_recently_lost": target_lost,
                "stamp_ns": self.get_clock().now().nanoseconds,
            }
        )
        if event["event"] != "waiting" or self.last_event != "waiting":
            self.event_pub.publish(_json_msg(event))
        self.last_event = event["event"]

    @staticmethod
    def _loads(data: str) -> Dict[str, Any]:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return {"text": data}
        return payload if isinstance(payload, dict) else {"value": payload}


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = GraspVerificationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
