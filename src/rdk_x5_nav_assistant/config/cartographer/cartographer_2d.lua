-- Cartographer 2D SLAM configuration for shopping cart (no odometry, pure LiDAR)
-- Optimized for indoor supermarket environment with YDLIDAR X3 (via vp100_ros2)

include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,

  -- Frame configuration: pure LiDAR, no external odometry
  map_frame = "map",
  tracking_frame = "base_footprint",     -- The frame Cartographer tracks
  published_frame = "base_footprint",    -- Publish map -> base_footprint directly
  odom_frame = "odom",
  provide_odom_frame = false,            -- No odom frame needed without wheel odometry
  publish_frame_projected_to_2d = true,  -- Publish 2D pose for Nav2 compatibility

  -- Sensor configuration
  use_odometry = false,                  -- No wheel odometry on shopping cart
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,

  -- Timing
  lookup_transform_timeout_sec = 0.2,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,        -- 200 Hz pose output
  trajectory_publish_period_sec = 30e-3,

  -- Sampling ratios
  rangefinder_sampling_ratio = 1.0,
  odometry_sampling_ratio = 1.0,
  fixed_frame_pose_sampling_ratio = 1.0,
  imu_sampling_ratio = 1.0,
  landmarks_sampling_ratio = 1.0,
}

-- Use 2D trajectory builder
MAP_BUILDER.use_trajectory_builder_2d = true

-- 2D trajectory builder tuning for indoor supermarket
TRAJECTORY_BUILDER_2D.min_range = 0.12               -- YDLIDAR X3 minimum reliable range
TRAJECTORY_BUILDER_2D.max_range = 8.0                -- Indoor supermarket range
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 2.0  -- Treat missing as 2m
TRAJECTORY_BUILDER_2D.use_imu_data = false           -- No IMU on this setup
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true

-- Motion filter: don't process scans if robot hasn't moved enough
-- For a shopping cart pushed by human, be more sensitive
TRAJECTORY_BUILDER_2D.motion_filter.max_time_seconds = 0.2
TRAJECTORY_BUILDER_2D.motion_filter.max_distance_meters = 0.05
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = math.rad(0.5)

-- Submap configuration
TRAJECTORY_BUILDER_2D.submaps.num_range_data = 60    -- Smaller submaps for tighter loop closure
TRAJECTORY_BUILDER_2D.submaps.grid_options_2d.resolution = 0.05

-- Ceres scan matcher tuning
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.occupied_space_weight = 10.0
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.translation_weight = 10.0
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.rotation_weight = 40.0

-- Fast correlative scan matcher (for loop closure detection)
TRAJECTORY_BUILDER_2D.adaptive_voxel_filter.max_length = 0.5
TRAJECTORY_BUILDER_2D.adaptive_voxel_filter.min_num_points = 200
TRAJECTORY_BUILDER_2D.loop_closure_adaptive_voxel_filter.max_length = 0.5

-- Global SLAM / Pose graph optimization
-- Tuned for stable loop closure in supermarket aisles
POSE_GRAPH.optimize_every_n_nodes = 45
POSE_GRAPH.constraint_builder.min_score = 0.55
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.60
POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.linear_search_window = 3.0
POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.angular_search_window = math.rad(30.0)

-- Loop closure search constraints
POSE_GRAPH.constraint_builder.max_constraint_distance = 10.0
POSE_GRAPH.constraint_builder.sampling_ratio = 0.3

-- Optimization problem weights
POSE_GRAPH.optimization_problem.huber_scale = 1e1
POSE_GRAPH.optimization_problem.acceleration_weight = 1e3
POSE_GRAPH.optimization_problem.rotation_weight = 3e5

-- Global localization (relocalization) settings
-- NOTE: global_sampling_ratio and local_sampling_ratio are already defined
-- in pose_graph.lua. Do not redefine them here to avoid "used wrong number
-- of times" fatal error from lua_parameter_dictionary.

return options
