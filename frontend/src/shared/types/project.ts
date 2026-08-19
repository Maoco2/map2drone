export interface Project {
  id: string;
  name: string;
  description?: string;
  client?: string;
  location?: string;
  user_id?: string;
  date: string;
  created_at: string;
  updated_at: string;
}

export interface Mission {
  id: string;
  project_id: string;
  name: string;
  mission_type: string;
  polygon_geojson: string;
  waypoints_json: string;
  parameters_json: string;
  grid_result_json: string;
  created_at: string;
  updated_at: string;
}

export type MissionType =
  | 'grid'
  | 'double_grid'
  | 'cross_grid'
  | 'corridor'
  | 'oblique'
  | 'facade'
  | 'tower'
  | 'linear'
  | 'orbit'
  | 'poi'
  | 'waypoint';

export interface MissionParameters {
  altitude: number;
  speed: number;
  overlap_frontal: number;
  overlap_lateral: number;
  gsd: number;
  drone_id?: string;
  camera_id?: string;
  home_latitude?: number;
  home_longitude?: number;
}

export interface Waypoint {
  latitude: number;
  longitude: number;
  altitude: number;
  heading: number;
  speed?: number;
  action_type?: number;
  action_param?: number;
  elevation_msnm?: number;
  agl?: number;
}

export interface PhotoPoint {
  index: number;
  latitude: number;
  longitude: number;
  altitude_m: number;
  distance_along_line_m: number;
  speed_ms: number;
  heading_deg: number;
  capture: boolean;
}

export interface Drone {
  id: string;
  name: string;
  manufacturer: string;
  weight_kg: number;
  max_speed_ms: number;
  flight_time_min: number;
  max_altitude_m: number;
  camera_id?: string;
}

export interface Camera {
  id: string;
  name: string;
  sensor_width_mm: number;
  sensor_height_mm: number;
  image_width_px: number;
  image_height_px: number;
  focal_length_mm: number;
  pixel_size_um: number;
  shutter_speed_s?: number;
  shutter_type?: string;
}

export type CaptureIntervalStatus = 'VALID' | 'WARNING' | 'INCOMPATIBLE' | 'ERROR';

export interface CaptureIntervalResult {
  status: CaptureIntervalStatus;
  required_photo_spacing_m?: number;
  ideal_interval_s?: number;
  recommended_interval_s?: number;
  actual_photo_spacing_m?: number;
  effective_front_overlap?: number;
  required_front_overlap?: number;
  speed_mps?: number;
  maximum_speed_for_1s?: number;
  planned_agl_m?: number;
  terrain_follow?: boolean;
  assumed_agl_m?: number;
  assumed_footprint_length_m?: number;
}

export type TurnRadiusMode = 'AUTO' | 'MANUAL' | 'NONE';
export type TurnStatus = 'VALID' | 'CONSTRAINED' | 'INVALID' | 'NONE';

export interface TurnRadiusConfig {
  mode: TurnRadiusMode;
  mission_type?: 'AREA_GRID' | 'LINEAR_CORRIDOR';
  speed_ms?: number;
  line_spacing_m?: number;
  safety_factor?: number;
  max_lateral_acceleration_ms2?: number;
  min_turn_radius_m?: number;
  max_turn_radius_m?: number;
  turn_clearance_m?: number;
  turn_extension_m?: number;
  manual_radius_m?: number;
  flight_lines_geojson?: GeoJSON.FeatureCollection;
}

export interface TurnGeometryResult {
  mode: string;
  status: TurnStatus;
  radius_m: number;
  dynamic_radius_m: number;
  safe_radius_m: number;
  available_radius_m: number;
  turn_angle_deg: number;
  turn_speed_ms: number;
  survey_speed_ms: number;
  extension_before_m: number;
  extension_after_m: number;
  clearance_m: number;
  turn_distance_m: number;
  turn_duration_s: number;
  photo_capture_recommended_during_turn: boolean;
  turn_direction: string;
  warnings: string[];
  explanation: string;
  geometry: GeoJSON.FeatureCollection;
  metadata: Record<string, number | string | boolean | null>;
}

export interface TurnRadiusPlanResult {
  mission_type: string;
  mode: string;
  status: TurnStatus;
  radius_m: number;
  turn_count: number;
  turns: TurnGeometryResult[];
  per_waypoint_curve_size: Record<string, number>;
  warnings: string[];
  explanation: string;
  geometry: GeoJSON.FeatureCollection;
  epsg: number;
  crs_name: string;
}

export interface TurnRadiusResponse {
  turn_radius_result?: TurnRadiusPlanResult | null;
  turn_radius_warnings?: string[];
}

export interface TurnRadiusRecomputeRequest {
  mission_type: 'AREA_GRID' | 'LINEAR_CORRIDOR';
  waypoints: Waypoint[];
  line_spacing: number;
  recommended_speed_ms: number;
  turn_radius: TurnRadiusConfig;
  flight_lines_geojson?: GeoJSON.FeatureCollection;
}

export interface GridResult {
  waypoints: Waypoint[];
  total_distance: number;
  estimated_time_sec: number;
  photo_count: number;
  battery_count: number;
  gsd: number;
  footprint_width: number;
  footprint_height: number;
  line_spacing: number;
  photo_spacing: number;
  recommended_speed_ms: number;
  mission_id?: string;
  sweep_deg?: number;
  num_lines?: number;
  waypoint_mode?: 'photo' | 'vertex' | 'terrain';
  corridor_length_m?: number;
  corridor_area_m2?: number;
  geometry?: CorridorGeometry;
  warnings?: string[];
  capture_interval?: CaptureIntervalResult;
  turn_radius_result?: TurnRadiusPlanResult | null;
  turn_radius_warnings?: string[];
  flight_lines_geojson?: GeoJSON.FeatureCollection;
  photo_points?: PhotoPoint[];
}

export interface CorridorGeometry {
  polygon_geojson: GeoJSON.Polygon;
  flight_lines_geojson: GeoJSON.FeatureCollection;
  centerline_geojson?: GeoJSON.LineString;
  epsg_out: number;
  crs_name: string;
  transformation: string;
}

export interface CorridorImportResponse extends GridResult {
  import_format: string;
  import_source: string;
  features_found: number;
}

export interface CorridorParseResponse {
  centerline: { type: 'LineString'; coordinates: [number, number][] };
  import_format: string;
  import_source: string;
  features_found: number;
  warnings: string[];
}

export interface ExportCompatibility {
  category: string;
  label: string;
  description: string;
}

export interface ExportWarning {
  code: string;
  message: string;
  fields: string[];
}

export interface ExportFormat {
  id: string;
  name: string;
  extension: string;
  version: string;
  description: string;
  compatibility?: ExportCompatibility;
}

export interface ExportFormatCheckItem {
  id: string;
  name: string;
  extension: string;
  compatibility?: ExportCompatibility;
  warnings: ExportWarning[];
}

export interface ExportWaypoint {
  latitude: number;
  longitude: number;
  altitude: number;
  heading: number;
  speed?: number;
  curve_size?: number;
  gimbal_pitch?: number;
  action_type?: number;
  action_param?: number;
  elevation_msnm?: number;
  agl?: number;
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  country: string;
  city: string;
  phone: string;
  gender: string;
  profession: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ── Universal Mission Model (Fase 10B) — types only ─────────────────────────

export type CaptureMode = 'NONE' | 'TIME' | 'DISTANCE';
export type DroneDynamicsProvenance = 'DEFAULT' | 'USER' | 'DRONE_PROFILE';

export interface UniversalWaypoint {
  index: number;
  latitude?: number;
  longitude?: number;
  altitude_m?: number;
  heading_deg?: number;
  speed_mps?: number;
  action_type?: number;
  action?: number;
  gimbal_mode?: number;
  gimbal_pitch_deg?: number;
  curve_size_m?: number;
  capture_enabled?: boolean;
  capture_time_interval_s?: number;
  capture_distance_interval_m?: number;
  photo_index?: number;
  line_index?: number;
  segment_index?: number;
  terrain_elevation_m?: number;
  agl_m?: number;
}

export interface FlightSegment {
  segment_index: number;
  start_waypoint: number;
  end_waypoint: number;
  distance_m: number;
  heading_deg?: number;
  speed_mps?: number;
  duration_s: number;
  line_index?: number;
  is_photo_segment: boolean;
  is_turn_segment: boolean;
  turn_angle_deg?: number;
}

export interface CapturePlan {
  mode: CaptureMode;
  scientific_interval_s?: number;
  commercial_interval_s?: number;
  photo_spacing_m?: number;
  status: string;
}

export interface TurnPlan {
  mode: string;
  status: TurnStatus;
  radius_m?: number;
  safe_radius_m?: number;
  available_radius_m?: number;
  extension_m?: number;
  a_lat_ms2?: number;
  safety_factor?: number;
  turn_duration_s?: number;
  turn_distance_m?: number;
  turn_count: number;
  turns: Record<string, unknown>[];
  warnings: string[];
  geometry?: GeoJSON.FeatureCollection;
}

export interface DroneFlightDynamicsProfile {
  max_lateral_acceleration_ms2?: number;
  preferred_turn_speed_mps?: number;
  min_turn_radius_m?: number;
  max_turn_radius_m?: number;
  provenance: DroneDynamicsProvenance;
}

export interface DroneProfile {
  id?: string;
  name?: string;
  manufacturer?: string;
  weight_kg?: number;
  max_speed_ms?: number;
  flight_time_min?: number;
  max_altitude_m?: number;
  dynamics: DroneFlightDynamicsProfile;
}

export interface CameraProfile {
  id?: string;
  name?: string;
  sensor_width_mm?: number;
  sensor_height_mm?: number;
  resolution_width_px?: number;
  resolution_height_px?: number;
  focal_length_mm?: number;
  pixel_size_um?: number;
  shutter_type?: string;
  shutter_speed_s?: number;
  shutter_latency_ms?: number;
  gimbal_max_rotation_rate_deg_s?: number;
  burst_rate_fps?: number;
}

export interface UniversalMissionMetrics {
  total_distance_m: number;
  estimated_time_sec: number;
  straight_distance_m: number;
  transition_distance_m: number;
  turn_distance_m: number;
  straight_time_s: number;
  transition_time_s: number;
  turn_time_s: number;
  turn_source: string;
  battery_count: number;
  gsd_cm: number;
  footprint_width_m: number;
  footprint_height_m: number;
  line_spacing_m: number;
  photo_spacing_m: number;
  num_lines: number;
  photo_count: number;
  flight_distance_m: number;
  flight_time_s: number;
  straight_flight_time_s: number;
  line_count: number;
  waypoint_count: number;
  estimated_energy?: number;
}

export interface UniversalMission {
  schema_version: string;
  mission_type: 'grid' | 'linear_corridor';
  created_at: string;
  mission_id?: string;
  name?: string;
  coordinate_reference: string;
  parameters: Record<string, unknown>;
  waypoints: UniversalWaypoint[];
  segments: FlightSegment[];
  flight_lines_geojson?: GeoJSON.FeatureCollection;
  geometry?: CorridorGeometry;
  photo_points?: PhotoPoint[];
  metrics: UniversalMissionMetrics;
  capture_interval?: CaptureIntervalResult;
  capture_plan?: CapturePlan;
  turn_radius_result?: TurnRadiusPlanResult | null;
  turn_plan?: TurnPlan;
  turn_radius_warnings?: string[];
  drone_profile?: DroneProfile;
  camera_profile?: CameraProfile;
  warnings?: string[];
}

// ── Optimizer types (Fase 10B) — types only ─────────────────────────────────

export interface OptimizationConstraints {
  min_gsd?: number;
  max_gsd?: number;
  preferred_gsd?: number;
  min_overlap_front?: number;
  max_overlap_front?: number;
  preferred_overlap_front?: number;
  min_overlap_side?: number;
  max_overlap_side?: number;
  preferred_overlap_side?: number;
  min_altitude?: number;
  max_altitude?: number;
  min_speed?: number;
  max_speed?: number;
  max_battery_count?: number;
  max_flight_time?: number;
  preferred_turn_radius?: number;
  max_photo_count?: number;
  allowed_capture_intervals?: number[];
}

export interface OptimizationWeights {
  coverage: number;
  gsd: number;
  overlap: number;
  time: number;
  battery: number;
  photo_count: number;
  turn: number;
  safety: number;
}

export type ScoreComponentStatus = 'SCORED' | 'UNKNOWN' | 'DATA_REQUIRED';

export interface ScoreComponentDetail {
  component: string;
  label: string;
  raw_value?: number | null;
  target?: number | null;
  normalized_value?: number | null;
  weight: number;
  contribution?: number | null;
  status: ScoreComponentStatus;
  message?: string | null;
}

export interface MissionScore {
  coverage_score?: number;
  gsd_score?: number;
  overlap_score?: number;
  time_score?: number;
  battery_score?: number;
  photo_count_score?: number;
  turn_score?: number;
  safety_score?: number;
  total_score?: number;
  details?: ScoreComponentDetail[];
}

export interface OptimizerInput {
  mission: UniversalMission;
  drone_profile?: DroneProfile;
  camera_profile?: CameraProfile;
  constraints?: OptimizationConstraints;
  weights?: OptimizationWeights;
}

export interface OptimizerEvaluateResponse {
  valid: boolean;
  status: string;
  metrics: UniversalMissionMetrics;
  score?: MissionScore;
  warnings: string[];
  validation?: {
    status: string;
    errors: { severity: string; code: string; field: string; message: string }[];
    warnings: { severity: string; code: string; field: string; message: string }[];
  };
}

export interface MissionValidateResponse {
  valid: boolean;
  status: string;
  errors: { severity: string; code: string; field: string; message: string }[];
  warnings: { severity: string; code: string; field: string; message: string }[];
}

// ── Optimizer solve types (Fase 10C) ────────────────────────────────────────

export type OptimizerVariableMode = 'fixed' | 'range' | 'candidate_values';

export interface OptimizerVariableDeclaration {
  name: string;
  mode: OptimizerVariableMode;
  value?: number | string | null;
  min_value?: number;
  max_value?: number;
  step?: number;
  values?: (number | string)[];
}

export interface OptimizerSolveRequest {
  grid?: {
    polygon: GeoJSON.Polygon;
    altitude: number;
    overlap_frontal: number;
    overlap_lateral: number;
    camera_id?: string;
    drone_id: string;
    project_id?: string;
    home_latitude?: number;
    home_longitude?: number;
    rotation_deg?: number;
    grid_type?: string;
    altitude_mode?: string;
    turn_radius?: any;
  };
  corridor?: {
    centerline: GeoJSON.LineString;
    width_left: number;
    width_right: number;
    altitude: number;
    overlap_frontal: number;
    overlap_lateral: number;
    camera_id?: string;
    drone_id: string;
    project_id?: string;
    home_latitude?: number;
    home_longitude?: number;
    altitude_mode?: string;
    turn_radius?: any;
  };
  variables?: { variables: OptimizerVariableDeclaration[] };
  constraints?: OptimizationConstraints;
  weights?: OptimizationWeights;
  max_candidates?: number;
}

export interface OptimizerCandidate {
  label: string;
  variable_values: Record<string, number>;
  mission: UniversalMission;
  score?: MissionScore;
}

export type OptimizerSolveStatus = 'OPTIMAL' | 'FEASIBLE' | 'CONSTRAINED' | 'NO_SOLUTION';

export interface OptimizerSolveResponse {
  status: OptimizerSolveStatus;
  message: string;
  best_candidate?: OptimizerCandidate | null;
  best_score?: MissionScore | null;
  alternatives: OptimizerCandidate[];
  stats: {
    total: number;
    evaluated: number;
    valid: number;
    invalid: number;
    rejected: number;
  };
  warnings: string[];
  explanation?: {
    summary: string;
    reasons: string[];
    warnings: string[];
    stats: Record<string, number>;
  } | null;
}

// ── Optimizer apply / export readiness (Fase 10F) ───────────────────────────

export interface OptimizerApplyRequest {
  solve_request: OptimizerSolveRequest;
  winner: UniversalMission;
  winner_variable_values?: Record<string, number>;
  project_id?: string | null;
  original_mission_id?: string | null;
  name?: string | null;
}

export interface MissionComparisonItem {
  metric: string;
  label: string;
  baseline?: number | null;
  winner?: number | null;
  delta?: number | null;
  unit: string;
}

export interface OptimizerApplyResponse {
  applied?: boolean;
  mission_id?: string | null;
  baseline_mission: UniversalMission;
  baseline_score?: MissionScore | null;
  winner_mission: UniversalMission;
  winner_score?: MissionScore | null;
  comparison: MissionComparisonItem[];
  modified_variables: string[];
  verification: Record<string, unknown>;
  warnings: string[];
}

export type ExportReadinessStatus = 'READY' | 'WARNING' | 'BLOCKED';

export interface ExportReadinessItem {
  id: string;
  name: string;
  extension: string;
  status: ExportReadinessStatus;
  reasons: string[];
  codes: string[];
  compatibility?: {
    category: string;
    label: string;
    description: string;
  } | null;
  warnings: Array<Record<string, unknown>>;
}

export interface ExportCheckUmmResponse {
  items: ExportReadinessItem[];
}
