#!/bin/bash
# Save Cartographer map to .pbstream file
# Usage: ./save_map.sh [output_filename]

set -e

DEFAULT_OUTPUT="/home/sunrise/Project/nav_ws/maps/supermarket_$(date +%Y%m%d_%H%M%S).pbstream"
OUTPUT="${1:-$DEFAULT_OUTPUT}"

echo "Saving Cartographer map to: $OUTPUT"

# Ensure directory exists
mkdir -p "$(dirname "$OUTPUT")"

# Call Cartographer write_state service
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState "filename: '$OUTPUT'"

echo "Map saved to: $OUTPUT"
echo ""
echo "To use this map for localization:"
echo "  ros2 launch rdk_x5_nav_assistant cartographer_localization.launch.py load_state_filename:='$OUTPUT'"
