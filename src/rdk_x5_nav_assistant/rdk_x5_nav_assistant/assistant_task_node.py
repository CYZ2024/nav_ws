#!/usr/bin/env python3
"""Shopping task state machine and voice-guidance policy."""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import String

from .catalog import (
    detect_command,
    find_product,
    load_yaml,
    parse_intent_payload,
    shelf_for_product,
    tag_by_id,
    waypoint_by_id,
)


def _json_msg(payload: Dict[str, Any]) -> String:
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


class AssistantTaskNode(Node):
    def __init__(self) -> None:
        super().__init__("assistant_task_node")

        self.declare_parameter("product_catalog_path", "")
        self.declare_parameter("store_map_path", "")
        self.declare_parameter("demo_routes_path", "")
        self.declare_parameter("user_intent_topic", "/assistant/user_intent")
        self.declare_parameter("obstacle_topic", "/perception/obstacle")
        self.declare_parameter("product_pose_topic", "/perception/product_pose")
        self.declare_parameter("tag_event_topic", "/assistant/tag_event")
        self.declare_parameter("gesture_event_topic", "/assistant/gesture_event")
        self.declare_parameter("navigation_event_topic", "/assistant/navigation_event")
        self.declare_parameter("grasp_event_topic", "/assistant/grasp_event")
        self.declare_parameter("localization_status_topic", "/assistant/localization_status")
        self.declare_parameter("assistant_pose_topic", "/assistant/localization_pose")
        self.declare_parameter("target_product_topic", "/assistant/target_product")
        self.declare_parameter("task_state_topic", "/assistant/task_state")
        self.declare_parameter("tts_topic", "/tts_text")
        self.declare_parameter("arrival_radius_m", 0.8)
        self.declare_parameter("guidance_repeat_s", 1.6)
        self.declare_parameter("navigation_repeat_s", 4.0)

        catalog_path = self.get_parameter("product_catalog_path").value
        store_map_path = self.get_parameter("store_map_path").value
        routes_path = self.get_parameter("demo_routes_path").value
        if not catalog_path or not store_map_path or not routes_path:
            raise RuntimeError("product_catalog_path, store_map_path, and demo_routes_path are required")

        self.catalog = load_yaml(catalog_path)
        self.store_map = load_yaml(store_map_path)
        self.routes = load_yaml(routes_path)

        self.state = "Idle"
        self.current_product: Optional[Dict[str, Any]] = None
        self.current_shelf: Optional[Dict[str, Any]] = None
        self.current_route: Optional[Dict[str, Any]] = None
        self.last_obstacle: Dict[str, Any] = {}
        self.last_product_pose: Optional[Dict[str, Any]] = None
        self.last_tag_event: Optional[Dict[str, Any]] = None
        self.last_gesture_event: Optional[Dict[str, Any]] = None
        self.last_navigation_event: Optional[Dict[str, Any]] = None
        self.last_grasp_event: Optional[Dict[str, Any]] = None
        self.last_localization_status: Optional[Dict[str, Any]] = None
        self.assistant_xy: Optional[Tuple[float, float]] = None
        self.last_spoken_text = ""
        self.last_spoken_time = 0.0
        self.state_entered_time = self._now()

        self.target_product_pub = self.create_publisher(
            String,
            self.get_parameter("target_product_topic").value,
            10,
        )
        self.task_state_pub = self.create_publisher(
            String,
            self.get_parameter("task_state_topic").value,
            10,
        )
        self.tts_pub = self.create_publisher(String, self.get_parameter("tts_topic").value, 10)

        self.create_subscription(String, self.get_parameter("user_intent_topic").value, self._on_user_intent, 10)
        self.create_subscription(String, self.get_parameter("obstacle_topic").value, self._on_obstacle, 10)
        self.create_subscription(String, self.get_parameter("product_pose_topic").value, self._on_product_pose, 10)
        self.create_subscription(String, self.get_parameter("tag_event_topic").value, self._on_tag_event, 10)
        self.create_subscription(String, self.get_parameter("gesture_event_topic").value, self._on_gesture_event, 10)
        self.create_subscription(String, self.get_parameter("navigation_event_topic").value, self._on_navigation_event, 10)
        self.create_subscription(String, self.get_parameter("grasp_event_topic").value, self._on_grasp_event, 10)
        self.create_subscription(String, self.get_parameter("localization_status_topic").value, self._on_localization_status, 10)
        self.create_subscription(PoseStamped, self.get_parameter("assistant_pose_topic").value, self._on_pose, 10)
        self.timer = self.create_timer(0.5, self._tick)

        self._publish_state("startup")
        self._say("购物辅助系统已启动，请说出想购买的商品", force=True)
        self.get_logger().info("Assistant task node is ready")

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _say(self, text: str, min_interval: float = 1.0, force: bool = False) -> None:
        now = self._now()
        if not force and text == self.last_spoken_text and now - self.last_spoken_time < min_interval:
            return
        msg = String()
        msg.data = text
        self.tts_pub.publish(msg)
        self.last_spoken_text = text
        self.last_spoken_time = now

    def _set_state(self, state: str, reason: str) -> None:
        if self.state == state:
            return
        self.state = state
        self.state_entered_time = self._now()
        self._publish_state(reason)

    def _publish_state(self, reason: str = "") -> None:
        payload = {
            "state": self.state,
            "reason": reason,
            "product_id": self.current_product.get("id") if self.current_product else None,
            "product_name": self.current_product.get("name") if self.current_product else None,
            "shelf_id": self.current_shelf.get("id") if self.current_shelf else None,
            "route_id": self.current_route.get("id") if self.current_route else None,
            "obstacle": self.last_obstacle,
            "product_pose": self.last_product_pose,
            "tag_event": self.last_tag_event,
            "gesture_event": self.last_gesture_event,
            "navigation_event": self.last_navigation_event,
            "grasp_event": self.last_grasp_event,
            "localization_status": self.last_localization_status,
            "assistant_xy": self.assistant_xy,
            "stamp_ns": self.get_clock().now().nanoseconds,
        }
        self.task_state_pub.publish(_json_msg(payload))

    def _on_user_intent(self, msg: String) -> None:
        intent = parse_intent_payload(msg.data)
        text = str(intent.get("text") or intent.get("utterance") or msg.data)
        command = intent.get("command") or detect_command(text)
        if command:
            self._handle_command(str(command))
            return

        product = find_product(intent, self.catalog)
        if product is None:
            self._say("暂时没有在演示商品库中找到这个商品，请换一个商品名称", force=True)
            self._publish_state("unknown_product")
            return

        shelf = shelf_for_product(product, self.store_map)
        route = self._route_for_product(product)
        self.current_product = product
        self.current_shelf = shelf
        self.current_route = route
        self.last_product_pose = None
        self.last_tag_event = None
        self.last_gesture_event = None

        self.target_product_pub.publish(
            _json_msg(
                {
                    "product_id": product.get("id"),
                    "name": product.get("name"),
                    "shelf_id": product.get("shelf_id"),
                    "detection_classes": product.get("detection_classes", []),
                }
            )
        )
        shelf_name = shelf.get("name") if shelf else product.get("shelf_id", "目标货架")
        self._set_state("NavigateRoute", "new_product_intent")
        self._say(f"已识别商品{product.get('name')}，正在前往{shelf_name}", force=True)

    def _handle_command(self, command: str) -> None:
        if command == "stop":
            self._set_state("Paused", "user_stop")
            self._say("已暂停，请确认周围安全", force=True)
        elif command == "repeat":
            if self.last_spoken_text:
                self._say(self.last_spoken_text, force=True)
            else:
                self._say("当前没有可重复的提示", force=True)
        elif command == "confirm":
            if self.state in ("ReachGuide", "VerifyGrasp", "SearchSku", "SearchProduct", "Done"):
                self._set_state("VerifyGrasp", "user_confirm_request")
                self._say("收到确认手势，系统继续通过商品标识判断是否拿对", force=True)
            else:
                self._say("当前还没有进入抓取确认阶段", force=True)
        elif command == "return":
            self.current_product = None
            self.current_shelf = {"id": "entrance", "name": "入口", "waypoint_id": "entrance"}
            self.current_route = None
            self._set_state("NavigateRoute", "return_entrance")
            self._say("开始返回入口", force=True)
        elif command == "rescan":
            if self.current_product:
                self.last_product_pose = None
                self._set_state("SearchSku", "gesture_rescan")
                self._say("好的，请重新对准货架扫描商品标签", force=True)
            else:
                self._say("当前还没有目标商品，请先说出想购买的商品", force=True)

    def _on_obstacle(self, msg: String) -> None:
        self.last_obstacle = self._loads(msg.data)

    def _on_product_pose(self, msg: String) -> None:
        payload = self._loads(msg.data)
        if self.current_product and payload.get("target_product_id") != self.current_product.get("id"):
            return
        self.last_product_pose = payload
        if self.current_product and self.state in ("ApproachShelf", "SearchSku", "SearchProduct", "Recover"):
            self._set_state("ReachGuide", "product_found")
            name = self.current_product.get("name") if self.current_product else "目标商品"
            self._say(f"已找到{name}，开始持续抓取引导", force=True)

    def _on_tag_event(self, msg: String) -> None:
        payload = self._loads(msg.data)
        self.last_tag_event = payload
        if self.state == "ApproachShelf" and self._tag_matches_current_shelf(payload):
            self._set_state("SearchSku", "shelf_tag_verified")
            shelf_name = self.current_shelf.get("name") if self.current_shelf else "目标货架"
            self._say(f"已确认到达{shelf_name}，开始寻找目标商品", force=True)

    def _on_gesture_event(self, msg: String) -> None:
        self.last_gesture_event = self._loads(msg.data)
        self._publish_state("gesture_event")

    def _on_navigation_event(self, msg: String) -> None:
        payload = self._loads(msg.data)
        self.last_navigation_event = payload
        action = payload.get("action")
        if action == "arrived_shelf" and self.state in ("NavigateRoute", "NavigateShelf"):
            self._set_state("ApproachShelf", "navigation_arrived_shelf")
        elif action in ("off_route", "localization_low", "localization_unavailable"):
            self._publish_state(str(action))

    def _on_grasp_event(self, msg: String) -> None:
        payload = self._loads(msg.data)
        self.last_grasp_event = payload
        event = payload.get("event")
        spoken = payload.get("spoken")
        if event == "correct_item_grasped":
            self._set_state("Done", "grasp_verified")
            if spoken:
                self._say(str(spoken), force=True)
        elif event == "wrong_item_possible":
            self._set_state("Recover", "wrong_item_possible")
            if spoken:
                self._say(str(spoken), force=True)
        elif event in ("hand_near_target", "grasp_uncertain"):
            if self.state == "ReachGuide":
                self._set_state("VerifyGrasp", str(event))
            if spoken:
                self._say(str(spoken), min_interval=2.0)
        else:
            self._publish_state("grasp_event")

    def _on_localization_status(self, msg: String) -> None:
        self.last_localization_status = self._loads(msg.data)
        self._publish_state("localization_status")

    def _on_pose(self, msg: PoseStamped) -> None:
        self.assistant_xy = (float(msg.pose.position.x), float(msg.pose.position.y))

    def _tick(self) -> None:
        if self.state == "Paused":
            return

        if self.state in ("NavigateRoute", "NavigateShelf"):
            self._tick_navigate()
        elif self.state in ("ApproachShelf", "TagAlign"):
            self._tick_approach_shelf()
        elif self.state in ("SearchSku", "SearchProduct"):
            self._tick_search_product()
        elif self.state in ("ReachGuide", "VerifyGrasp"):
            self._tick_reach_guide()
        elif self.state == "Recover":
            self._tick_recover()

    def _tick_navigate(self) -> None:
        if self.last_obstacle.get("severity") == "stop":
            self._say(self.last_obstacle.get("spoken", "前方障碍物过近，请停止"), min_interval=3.0)
            self._publish_state("obstacle_stop")
            return

        if self.current_shelf and self.assistant_xy is not None:
            target_xy = self._target_xy_for_shelf(self.current_shelf)
            if target_xy is not None:
                distance = math.dist(self.assistant_xy, target_xy)
                if distance <= float(self.get_parameter("arrival_radius_m").value):
                    self._set_state("ApproachShelf", "arrived_by_pose")
                    self._say("已到达目标货架附近，开始扫描定位标识", force=True)
                    return
                self._say(f"继续前进，距离目标货架约{distance:.1f}米", min_interval=float(self.get_parameter("navigation_repeat_s").value))
                return

        route_hint = self._route_hint()
        self._say(route_hint, min_interval=float(self.get_parameter("navigation_repeat_s").value))

    def _tick_approach_shelf(self) -> None:
        if self.last_tag_event and self._tag_matches_current_shelf(self.last_tag_event):
            self._set_state("SearchSku", "shelf_tag_verified")
            self._say("货架标识确认完成，请面向货架寻找目标商品", force=True)
            return
        if self._now() - self.state_entered_time < 1.0:
            return
        self._set_state("SearchSku", "shelf_area_ready")
        self._say("已到达货架区域，请面向货架，开始搜索目标商品", force=True)

    def _tick_search_product(self) -> None:
        if self._product_pose_is_fresh():
            self._set_state("ReachGuide", "product_found")
            name = self.current_product.get("name") if self.current_product else "目标商品"
            self._say(f"已找到{name}，开始持续抓取引导", force=True)
            return
        self._say("请缓慢左右转动设备，扫描货架上的商品", min_interval=4.0)

    def _tick_reach_guide(self) -> None:
        if self.last_obstacle.get("severity") == "stop":
            self._say(self.last_obstacle.get("spoken", "前方障碍物过近，请停止"), min_interval=2.0)
            return
        if not self._product_pose_is_fresh(max_age_s=2.5):
            self._say("目标暂时丢失，请稍微后退并重新对准货架", min_interval=3.0)
            self._set_state("SearchSku", "product_lost")
            return
        spoken = self.last_product_pose.get("spoken", "请继续靠近目标商品")
        self._say(spoken, min_interval=float(self.get_parameter("guidance_repeat_s").value))
        self._publish_state("reach_guidance")

    def _tick_recover(self) -> None:
        self._say("请把商品放回原处，重新扫描目标商品标签", min_interval=3.0)
        if self._product_pose_is_fresh():
            self._set_state("ReachGuide", "recovered_target")

    def _route_for_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        route_id = product.get("route_id")
        for route in self.routes.get("routes", []) or []:
            if route.get("id") == route_id or route.get("product_id") == product.get("id"):
                return route
        return None

    def _route_hint(self) -> str:
        if self.current_route:
            hint = self.current_route.get("voice_hint")
            if hint:
                return str(hint)
        if self.current_shelf:
            return f"请沿通道前进，寻找{self.current_shelf.get('name', '目标货架')}"
        return "请沿通道缓慢前进"

    def _target_xy_for_shelf(self, shelf: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        waypoint_id = shelf.get("waypoint_id")
        waypoint = waypoint_by_id(waypoint_id, self.store_map) if waypoint_id else None
        pose = (waypoint or shelf).get("pose")
        if isinstance(pose, list) and len(pose) >= 2:
            return float(pose[0]), float(pose[1])
        return None

    def _tag_matches_current_shelf(self, tag_event: Dict[str, Any]) -> bool:
        if not self.current_shelf:
            return False
        tag_id = tag_event.get("id")
        tag = tag_by_id(tag_id, self.store_map) if tag_id is not None else None
        return bool(tag and tag.get("shelf_id") == self.current_shelf.get("id"))

    def _product_pose_is_fresh(self, max_age_s: float = 3.0) -> bool:
        if not self.last_product_pose:
            return False
        stamp_ns = self.last_product_pose.get("stamp_ns")
        if stamp_ns is None:
            return True
        return self._now() - float(stamp_ns) / 1e9 <= max_age_s

    @staticmethod
    def _loads(data: str) -> Dict[str, Any]:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return {"text": data}
        return payload if isinstance(payload, dict) else {"value": payload}


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = AssistantTaskNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
