#!/usr/bin/env python3
"""Filter a configurable angular sector out of a LaserScan."""

from __future__ import annotations

import math
from typing import List, Optional

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


def _wrap_degrees(angle: float) -> float:
    wrapped = (angle + 180.0) % 360.0 - 180.0
    return 180.0 if wrapped == -180.0 and angle > 0.0 else wrapped


def _angular_distance_degrees(angle: float, center: float) -> float:
    return abs(_wrap_degrees(angle - center))


def _nan_ranges(length: int) -> List[float]:
    return [math.nan] * length


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_float(value: object) -> float:
    return float(value)


class ScanSectorFilter(Node):
    """Remove ranges inside an angular sector, measured in laser frame degrees."""

    def __init__(self) -> None:
        super().__init__("scan_sector_filter")

        self.declare_parameter("input_scan_topic", "/scan")
        self.declare_parameter("filtered_scan_topic", "/scan_filtered")
        self.declare_parameter("blocked_scan_topic", "/scan_blocked")
        self.declare_parameter("filter_enabled", True)
        self.declare_parameter("filter_center_deg", 180.0)
        self.declare_parameter("filter_width_deg", 90.0)
        self.declare_parameter("invert_filter", False)
        self.declare_parameter("replacement", "nan")

        self._filtered_pub = self.create_publisher(
            LaserScan,
            str(self.get_parameter("filtered_scan_topic").value),
            10,
        )
        self._blocked_pub = self.create_publisher(
            LaserScan,
            str(self.get_parameter("blocked_scan_topic").value),
            10,
        )
        self.create_subscription(
            LaserScan,
            str(self.get_parameter("input_scan_topic").value),
            self._on_scan,
            10,
        )

        self._last_log_time = 0.0
        self.get_logger().info(
            "Scan sector filter ready: filtering center=%.1f deg width=%.1f deg"
            % (
                _as_float(self.get_parameter("filter_center_deg").value),
                _as_float(self.get_parameter("filter_width_deg").value),
            )
        )

    def _on_scan(self, scan: LaserScan) -> None:
        ranges = list(scan.ranges)
        intensities: Optional[List[float]] = list(scan.intensities) if scan.intensities else None

        filtered = LaserScan()
        filtered.header = scan.header
        filtered.angle_min = scan.angle_min
        filtered.angle_max = scan.angle_max
        filtered.angle_increment = scan.angle_increment
        filtered.time_increment = scan.time_increment
        filtered.scan_time = scan.scan_time
        filtered.range_min = scan.range_min
        filtered.range_max = scan.range_max
        filtered.ranges = ranges[:]
        filtered.intensities = intensities[:] if intensities is not None else []

        blocked = LaserScan()
        blocked.header = scan.header
        blocked.angle_min = scan.angle_min
        blocked.angle_max = scan.angle_max
        blocked.angle_increment = scan.angle_increment
        blocked.time_increment = scan.time_increment
        blocked.scan_time = scan.scan_time
        blocked.range_min = scan.range_min
        blocked.range_max = scan.range_max
        blocked.ranges = _nan_ranges(len(ranges))
        blocked.intensities = _nan_ranges(len(intensities)) if intensities is not None else []

        if not _as_bool(self.get_parameter("filter_enabled").value):
            self._filtered_pub.publish(filtered)
            self._blocked_pub.publish(blocked)
            return

        center = _wrap_degrees(_as_float(self.get_parameter("filter_center_deg").value))
        half_width = max(0.0, min(360.0, _as_float(self.get_parameter("filter_width_deg").value))) / 2.0
        invert = _as_bool(self.get_parameter("invert_filter").value)
        replacement = str(self.get_parameter("replacement").value).lower()

        replacement_value = 0.0 if replacement == "zero" else math.nan
        blocked_count = 0

        for index, value in enumerate(ranges):
            angle_rad = scan.angle_min + index * scan.angle_increment
            angle_deg = math.degrees(angle_rad)
            inside_sector = _angular_distance_degrees(angle_deg, center) <= half_width
            should_filter = not inside_sector if invert else inside_sector
            if not should_filter:
                continue

            blocked.ranges[index] = value
            filtered.ranges[index] = replacement_value
            blocked_count += 1

            if intensities is not None:
                blocked.intensities[index] = intensities[index]
                filtered.intensities[index] = 0.0

        self._filtered_pub.publish(filtered)
        self._blocked_pub.publish(blocked)

        now = self.get_clock().now().nanoseconds / 1e9
        if now - self._last_log_time > 5.0:
            self._last_log_time = now
            self.get_logger().info(
                "Filtered %d/%d beams: center=%.1f deg width=%.1f deg invert=%s"
                % (blocked_count, len(ranges), center, half_width * 2.0, invert)
            )


def main() -> None:
    rclpy.init()
    node = ScanSectorFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
