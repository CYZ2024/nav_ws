#!/bin/bash
# Save Cartographer map to .pbstream file
# Usage: ./save_map.sh [output_path]

set -e

OUTPUT="${1:-/home/sunrise/Project/nav_ws/maps/$(date +%Y%m%d_%H%M%S).pbstream}"

echo "=== Saving Cartographer map to: $OUTPUT ==="

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT")"

# Call Cartographer write_state service
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState "filename: '$OUTPUT'"

echo "=== Map saved to: $OUTPUT ==="
echo "To load this map for pure localization:"
echo "  ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py load_state_filename:='$OUTPUT'"
