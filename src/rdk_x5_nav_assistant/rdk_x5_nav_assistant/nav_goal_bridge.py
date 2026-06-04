#!/usr/bin/env python3
"""Bridge between robot-ai and Nav2.

Receives /shopping/nav_goal from robot-ai, sends Nav2 NavigateToPose action,
publishes /shopping/nav_status and /shopping/robot_pose back to robot-ai.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener
import tf2_geometry_msgs


def _json_msg(payload: Dict[str, Any]) -> String:
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    return msg


class NavGoalBridge(Node):
    """Bridge navigation goals from AI board to Nav2 and report status back."""

    def __init__(self) -> None:
        super().__init__("nav_goal_bridge")

        # Parameters
        self.declare_parameter("nav_goal_topic", "/shopping/nav_goal")
        self.declare_parameter("nav_cancel_topic", "/shopping/nav_cancel")
        self.declare_parameter("nav_status_topic", "/shopping/nav_status")
        self.declare_parameter("robot_pose_topic", "/shopping/robot_pose")
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("robot_frame", "base_footprint")
        self.declare_parameter("publish_rate_hz", 5.0)
        self.declare_parameter("goal_timeout_s", 120.0)

        self.map_frame = str(self.get_parameter("map_frame").value)
        self.robot_frame = str(self.get_parameter("robot_frame").value)

        # TF
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Publishers
        self.status_pub = self.create_publisher(
            String,
            self.get_parameter("nav_status_topic").value,
            10,
        )
        self.pose_pub = self.create_publisher(
            String,
            self.get_parameter("robot_pose_topic").value,
            10,
        )

        # Subscribers
        self.create_subscription(
            String,
            self.get_parameter("nav_goal_topic").value,
            self._on_nav_goal,
            10,
        )
        self.create_subscription(
            String,
            self.get_parameter("nav_cancel_topic").value,
            self._on_nav_cancel,
            10,
        )

        # Nav2 action client
        self._nav_client = ActionClient(
            self,
            NavigateToPose,
            "navigate_to_pose",
            callback_group=ReentrantCallbackGroup(),
        )

        # State
        self._current_goal_handle: Optional[Any] = None
        self._current_request_id: Optional[str] = None
        self._current_product_id: Optional[str] = None
        self._current_shelf_id: Optional[str] = None
        self._goal_start_time: Optional[float] = None

        # Timer for periodic status/pose publishing
        rate = max(0.5, float(self.get_parameter("publish_rate_hz").value))
        self._timer = self.create_timer(1.0 / rate, self._tick)

        self.get_logger().info("Nav goal bridge is ready")

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _on_nav_goal(self, msg: String) -> None:
        payload = self._loads(msg.data)
        request_id = payload.get("request_id", "")
        product_id = payload.get("product_id", "")
        shelf_id = payload.get("shelf_id", "")
        target_pose = payload.get("target_pose", {})
        mode = payload.get("mode", "navigate_to_shelf")

        self.get_logger().info(
            f"Received nav_goal: req={request_id}, product={product_id}, "
            f"shelf={shelf_id}, mode={mode}"
        )

        # Cancel any existing goal
        if self._current_goal_handle is not None:
            self._cancel_current_goal()

        self._current_request_id = request_id
        self._current_product_id = product_id
        self._current_shelf_id = shelf_id
        self._goal_start_time = self._now()

        # Build PoseStamped from target_pose
        pose = self._build_pose(target_pose)
        if pose is None:
            self._publish_status("FAILED", "invalid_target_pose", 0.0)
            return

        # Send Nav2 goal
        self._send_nav2_goal(pose)

    def _on_nav_cancel(self, msg: String) -> None:
        payload = self._loads(msg.data)
        request_id = payload.get("request_id", "")
        reason = payload.get("reason", "user_cancelled")

        if self._current_request_id == request_id or request_id == "":
            self.get_logger().info(f"Cancelling goal: {reason}")
            self._cancel_current_goal()
            self._publish_status("CANCELED", reason, 0.0)
            self._reset_goal()

    def _send_nav2_goal(self, pose: PoseStamped) -> None:
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available")
            self._publish_status("FAILED", "nav2_server_unavailable", 0.0)
            self._reset_goal()
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = pose

        self.get_logger().info(
            f"Sending Nav2 goal: x={pose.pose.position.x:.2f}, "
            f"y={pose.pose.position.y:.2f}, frame={pose.header.frame_id}"
        )

        send_goal_future = self._nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self._feedback_callback,
        )
        send_goal_future.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("Nav2 goal rejected")
            self._publish_status("FAILED", "goal_rejected", 0.0)
            self._reset_goal()
            return

        self._current_goal_handle = goal_handle
        self.get_logger().info("Nav2 goal accepted")
        self._publish_status("ACCEPTED", "goal_accepted", 0.0)

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_callback)

    def _feedback_callback(self, feedback_msg) -> None:
        fb = feedback_msg.feedback
        remaining = fb.distance_remaining
        # Estimate navigation time based on remaining distance (0.3 m/s walking speed)
        eta_s = remaining / 0.3 if remaining > 0 else 0
        self._publish_status("MOVING", "navigating", remaining, eta_s)

    def _result_callback(self, future) -> None:
        result = future.result()
        status = result.status if result else GoalStatus.STATUS_UNKNOWN

        if status == GoalStatus.STATUS_SUCCEEDED:
            self._publish_status("ARRIVED", "goal_reached", 0.0)
            self.get_logger().info("Nav2 goal succeeded")
        elif status == GoalStatus.STATUS_CANCELED:
            self._publish_status("CANCELED", "goal_canceled", 0.0)
            self.get_logger().info("Nav2 goal canceled")
        elif status == GoalStatus.STATUS_ABORTED:
            self._publish_status("FAILED", "goal_aborted", 0.0)
            self.get_logger().warn("Nav2 goal aborted")
        else:
            self._publish_status("FAILED", f"status_{status}", 0.0)
            self.get_logger().warn(f"Nav2 goal ended with status {status}")

        self._reset_goal()

    def _cancel_current_goal(self) -> None:
        if self._current_goal_handle is not None:
            cancel_future = self._current_goal_handle.cancel_goal_async()
            # Don't wait for result; fire and forget
            self._current_goal_handle = None

    def _reset_goal(self) -> None:
        self._current_goal_handle = None
        self._goal_start_time = None
        # Keep request_id/product_id/shelf_id until next goal arrives

    def _tick(self) -> None:
        # Publish current robot pose
        self._publish_robot_pose()

        # Check for goal timeout
        if self._goal_start_time is not None:
            timeout = float(self.get_parameter("goal_timeout_s").value)
            elapsed = self._now() - self._goal_start_time
            if elapsed > timeout:
                self.get_logger().warn(f"Goal timeout after {elapsed:.1f}s")
                self._cancel_current_goal()
                self._publish_status("FAILED", "timeout", 0.0)
                self._reset_goal()

    def _publish_status(
        self,
        state: str,
        message: str,
        distance_remaining: float,
        eta_s: float = 0.0,
    ) -> None:
        payload = {
            "request_id": self._current_request_id,
            "state": state,
            "message": message,
            "distance_remaining": round(distance_remaining, 2),
            "eta_s": round(eta_s, 1),
            "product_id": self._current_product_id,
            "shelf_id": self._current_shelf_id,
            "stamp_ns": self.get_clock().now().nanoseconds,
        }
        self.status_pub.publish(_json_msg(payload))

    def _publish_robot_pose(self) -> None:
        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame,
                self.robot_frame,
                rclpy.time.Time(),
            )
            tx = transform.transform.translation.x
            ty = transform.transform.translation.y
            tz = transform.transform.translation.z
            q = transform.transform.rotation
            # Convert quaternion to yaw
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                           1.0 - 2.0 * (q.y * q.y + q.z * q.z))

            payload = {
                "frame_id": self.map_frame,
                "x": round(tx, 4),
                "y": round(ty, 4),
                "z": round(tz, 4),
                "yaw": round(yaw, 4),
                "stamp_ns": self.get_clock().now().nanoseconds,
            }
            self.pose_pub.publish(_json_msg(payload))
        except Exception as e:
            # TF not available yet; don't spam errors
            pass

    def _build_pose(self, target_pose: Dict[str, Any]) -> Optional[PoseStamped]:
        frame_id = target_pose.get("frame_id", "map")
        x = float(target_pose.get("x", 0.0))
        y = float(target_pose.get("y", 0.0))
        yaw = float(target_pose.get("yaw", 0.0))

        pose = PoseStamped()
        pose.header.frame_id = frame_id
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        # Convert yaw to quaternion
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    @staticmethod
    def _loads(data: str) -> Dict[str, Any]:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return {"text": data}
        return payload if isinstance(payload, dict) else {"value": payload}


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = NavGoalBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
