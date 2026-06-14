#!/usr/bin/env python3
"""Publish map->base_footprint from an initial pose for visualization tests."""

from __future__ import annotations

import math
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, TransformStamped
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


def _yaw_to_quaternion(yaw: float):
    z = math.sin(yaw / 2.0)
    w = math.cos(yaw / 2.0)
    return z, w


def _quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


class InitialPoseTf(Node):
    """Small helper for obstacle tests without a real localization source."""

    def __init__(self) -> None:
        super().__init__("initial_pose_tf")

        self.declare_parameter("map_frame", "map")
        self.declare_parameter("robot_frame", "base_footprint")
        self.declare_parameter("initial_pose_topic", "/initialpose")
        self.declare_parameter("x", 0.0)
        self.declare_parameter("y", 0.0)
        self.declare_parameter("yaw", 0.0)
        self.declare_parameter("publish_rate_hz", 20.0)

        self.map_frame = str(self.get_parameter("map_frame").value)
        self.robot_frame = str(self.get_parameter("robot_frame").value)
        self.x = float(self.get_parameter("x").value)
        self.y = float(self.get_parameter("y").value)
        self.yaw = float(self.get_parameter("yaw").value)

        self.broadcaster = TransformBroadcaster(self)
        self.create_subscription(
            PoseWithCovarianceStamped,
            str(self.get_parameter("initial_pose_topic").value),
            self._on_initial_pose,
            10,
        )

        rate = max(1.0, float(self.get_parameter("publish_rate_hz").value))
        self.create_timer(1.0 / rate, self._publish_tf)
        self.get_logger().info(
            "Initial pose TF ready: %s -> %s at x=%.2f y=%.2f yaw=%.2f"
            % (self.map_frame, self.robot_frame, self.x, self.y, self.yaw)
        )

    def _on_initial_pose(self, msg: PoseWithCovarianceStamped) -> None:
        pose = msg.pose.pose
        self.x = pose.position.x
        self.y = pose.position.y
        q = pose.orientation
        self.yaw = _quaternion_to_yaw(q.x, q.y, q.z, q.w)
        self.get_logger().info(
            "Updated initial pose: x=%.2f y=%.2f yaw=%.2f" % (self.x, self.y, self.yaw)
        )

    def _publish_tf(self) -> None:
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = self.map_frame
        transform.child_frame_id = self.robot_frame
        transform.transform.translation.x = self.x
        transform.transform.translation.y = self.y
        transform.transform.translation.z = 0.0
        z, w = _yaw_to_quaternion(self.yaw)
        transform.transform.rotation.z = z
        transform.transform.rotation.w = w
        self.broadcaster.sendTransform(transform)


def main() -> None:
    rclpy.init()
    node = InitialPoseTf()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
