-- Cartographer 2D PURE LOCALIZATION configuration
-- Load a pre-built .pbstream map and localize against it using scan matching.
-- Use with: cartographer_localization.launch.py load_state_filename:='/path/to/map.pbstream'

include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,

  -- Frame configuration: pure LiDAR, no external odometry
  map_frame = "map",
  tracking_frame = "base_footprint",
  published_frame = "base_footprint",
  odom_frame = "odom",
  provide_odom_frame = false,
  publish_frame_projected_to_2d = true,

  -- Sensor configuration
  use_odometry = false,
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,

  -- Timing
  lookup_transform_timeout_sec = 0.2,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
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

-- Pure localization: keep only recent submaps, don't grow the map
TRAJECTORY_BUILDER.pure_localization_trimmer = {
  max_submaps_to_keep = 3,
}

-- 2D trajectory builder tuning (same as mapping mode)
TRAJECTORY_BUILDER_2D.min_range = 0.12
TRAJECTORY_BUILDER_2D.max_range = 8.0
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 2.0
TRAJECTORY_BUILDER_2D.use_imu_data = false
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true

-- More aggressive scan matching for localization (less drift tolerance)
TRAJECTORY_BUILDER_2D.motion_filter.max_time_seconds = 0.2
TRAJECTORY_BUILDER_2D.motion_filter.max_distance_meters = 0.05
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = math.rad(0.5)

-- Submap configuration (smaller for localization)
TRAJECTORY_BUILDER_2D.submaps.num_range_data = 35
TRAJECTORY_BUILDER_2D.submaps.grid_options_2d.resolution = 0.05

-- Ceres scan matcher tuning
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.occupied_space_weight = 10.0
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.translation_weight = 10.0
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.rotation_weight = 40.0

-- Fast correlative scan matcher (for relocalization)
TRAJECTORY_BUILDER_2D.adaptive_voxel_filter.max_length = 0.5
TRAJECTORY_BUILDER_2D.adaptive_voxel_filter.min_num_points = 200

-- Global SLAM: optimize less frequently in localization mode
POSE_GRAPH.optimize_every_n_nodes = 20
POSE_GRAPH.constraint_builder.min_score = 0.55
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.60
POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.linear_search_window = 3.0
POSE_GRAPH.constraint_builder.fast_correlative_scan_matcher.angular_search_window = math.rad(30.0)
POSE_GRAPH.constraint_builder.max_constraint_distance = 10.0
POSE_GRAPH.constraint_builder.sampling_ratio = 0.3

-- Optimization problem weights
POSE_GRAPH.optimization_problem.huber_scale = 1e1
POSE_GRAPH.optimization_problem.acceleration_weight = 1e3
POSE_GRAPH.optimization_problem.rotation_weight = 3e5

return options
