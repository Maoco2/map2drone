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
