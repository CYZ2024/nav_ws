#!/usr/bin/env python3
"""Normalize localization sources: Cartographer, RTAB-Map, or odometry.

Supports multiple pose sources for flexible SLAM backend switching.
Primary: Cartographer /tracked_pose → /assistant/localization_pose
Fallback: RTAB-Map /rtabmap/localization_pose
Fallback: /odom
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String


def _json_msg(payload: Dict[str, Any]) -> String:
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


class LocalizationBridge(Node):
    def __init__(self) -> None:
        super().__init__("localization_bridge")
        self.declare_parameter("cartographer_pose_topic", "/tracked_pose")
        self.declare_parameter("rtabmap_pose_topic", "/rtabmap/localization_pose")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("localization_pose_topic", "/assistant/localization_pose")
        self.declare_parameter("localization_status_topic", "/assistant/localization_status")
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("stale_after_s", 2.0)
        self.declare_parameter("publish_rate_hz", 5.0)

        self.pose_pub = self.create_publisher(
            PoseStamped,
            self.get_parameter("localization_pose_topic").value,
            10,
        )
        self.status_pub = self.create_publisher(
            String,
            self.get_parameter("localization_status_topic").value,
            10,
        )

        self.last_pose: Optional[PoseStamped] = None
        self.last_source = "none"
        self.last_stamp_ns = 0

        # Subscribe to all possible pose sources
        carto_topic = str(self.get_parameter("cartographer_pose_topic").value or "")
        rtabmap_topic = str(self.get_parameter("rtabmap_pose_topic").value or "")
        odom_topic = str(self.get_parameter("odom_topic").value or "")

        if carto_topic:
            self.create_subscription(PoseStamped, carto_topic, self._on_carto_pose, 10)
            self.get_logger().info(f"Subscribing to Cartographer pose: {carto_topic}")
        if rtabmap_topic:
            self.create_subscription(PoseStamped, rtabmap_topic, self._on_pose, 10)
            self.get_logger().info(f"Subscribing to RTAB-Map pose: {rtabmap_topic}")
        if odom_topic:
            self.create_subscription(Odometry, odom_topic, self._on_odom, 10)
            self.get_logger().info(f"Subscribing to odometry: {odom_topic}")

        hz = max(0.2, float(self.get_parameter("publish_rate_hz").value))
        self.timer = self.create_timer(1.0 / hz, self._tick)
        self.get_logger().info("Localization bridge is ready (supports Cartographer/RTAB-Map/odom)")

    def _now_ns(self) -> int:
        return self.get_clock().now().nanoseconds

    def _on_carto_pose(self, msg: PoseStamped) -> None:
        """Handle Cartographer /tracked_pose."""
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose
        if not pose.header.frame_id:
            pose.header.frame_id = str(self.get_parameter("frame_id").value)
        self.last_pose = pose
        self.last_source = "cartographer"
        self.last_stamp_ns = self._stamp_or_now_ns(pose)
        self.pose_pub.publish(pose)
        self._publish_status("ok")

    def _on_pose(self, msg: PoseStamped) -> None:
        """Handle RTAB-Map pose."""
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose
        if not pose.header.frame_id:
            pose.header.frame_id = str(self.get_parameter("frame_id").value)
        self.last_pose = pose
        self.last_source = "rtabmap"
        self.last_stamp_ns = self._stamp_or_now_ns(pose)
        self.pose_pub.publish(pose)
        self._publish_status("ok")

    def _on_odom(self, msg: Odometry) -> None:
        """Handle odometry fallback."""
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose.pose
        if not pose.header.frame_id:
            pose.header.frame_id = msg.header.frame_id or str(self.get_parameter("frame_id").value)
        self.last_pose = pose
        self.last_source = "odom"
        self.last_stamp_ns = self._stamp_or_now_ns(pose)
        self.pose_pub.publish(pose)
        self._publish_status("ok")

    def _tick(self) -> None:
        if self.last_pose is None:
            self._publish_status("unavailable")
            return
        age_s = (self._now_ns() - self.last_stamp_ns) / 1e9
        stale_after = float(self.get_parameter("stale_after_s").value)
        self._publish_status("stale" if age_s > stale_after else "ok")

    def _publish_status(self, status: str) -> None:
        age_s = None
        if self.last_stamp_ns:
            age_s = max(0.0, (self._now_ns() - self.last_stamp_ns) / 1e9)
        pose_payload = None
        if self.last_pose is not None:
            pose_payload = {
                "x": round(float(self.last_pose.pose.position.x), 3),
                "y": round(float(self.last_pose.pose.position.y), 3),
                "z": round(float(self.last_pose.pose.position.z), 3),
                "frame_id": self.last_pose.header.frame_id,
            }
        self.status_pub.publish(
            _json_msg(
                {
                    "status": status,
                    "source": self.last_source,
                    "age_s": None if age_s is None else round(age_s, 3),
                    "pose": pose_payload,
                    "stamp_ns": self._now_ns(),
                }
            )
        )

    def _stamp_or_now_ns(self, msg: PoseStamped) -> int:
        stamp = msg.header.stamp
        stamp_ns = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
        return stamp_ns if stamp_ns > 0 else self._now_ns()


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = LocalizationBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
