-- Map2Drone Seed Data
-- Populates drones and cameras tables with real manufacturer specs

INSERT INTO public.cameras (id, name, sensor_width_mm, sensor_height_mm, image_width_px, image_height_px, focal_length_mm, pixel_size_um) VALUES
  ('a1b2c3d4-0001-4000-8000-000000000001', 'DJI Mini 3 / Mini 4 Pro Camera', 6.4, 4.8, 4032, 3024, 24, 1.59),
  ('a1b2c3d4-0001-4000-8000-000000000002', 'DJI Air 3 Wide Camera', 8.8, 6.6, 5280, 3956, 24, 1.67),
  ('a1b2c3d4-0001-4000-8000-000000000003', 'DJI Air 3S Camera', 10.0, 7.5, 5472, 3648, 24, 1.83),
  ('a1b2c3d4-0001-4000-8000-000000000004', 'DJI Mavic 3 / 3 Classic Camera', 17.3, 13.0, 5280, 3956, 24, 3.27),
  ('a1b2c3d4-0001-4000-8000-000000000005', 'DJI Mavic 3E Wide Camera', 17.3, 13.0, 5280, 3956, 24, 3.27),
  ('a1b2c3d4-0001-4000-8000-000000000006', 'DJI Matrice 4E Camera', 13.2, 8.8, 5472, 3648, 24, 2.41),
  ('a1b2c3d4-0001-4000-8000-000000000007', 'DJI Matrice 350 RTK Zenmuse H20', 7.68, 5.76, 4056, 3040, 24, 1.89),
  ('a1b2c3d4-0001-4000-8000-000000000008', 'DJI Phantom 4 RTK Camera', 13.2, 8.8, 5472, 3648, 24, 2.41),
  ('a1b2c3d4-0001-4000-8000-000000000009', 'Autel EVO II Pro Camera', 13.2, 8.8, 5472, 3648, 28, 2.41),
  ('a1b2c3d4-0001-4000-8000-000000000010', 'Parrot Anafi Camera', 6.4, 4.8, 4608, 3456, 23, 1.39);

INSERT INTO public.drones (id, name, manufacturer, weight_kg, max_speed_ms, flight_time_min, max_altitude_m, camera_id) VALUES
  ('b2c3d4e5-0001-4000-8000-000000000001', 'DJI Mini 3', 'DJI', 0.249, 16, 38, 4000, 'a1b2c3d4-0001-4000-8000-000000000001'),
  ('b2c3d4e5-0001-4000-8000-000000000002', 'DJI Mini 4 Pro', 'DJI', 0.249, 16, 34, 4000, 'a1b2c3d4-0001-4000-8000-000000000001'),
  ('b2c3d4e5-0001-4000-8000-000000000003', 'DJI Air 3', 'DJI', 0.720, 19, 46, 5000, 'a1b2c3d4-0001-4000-8000-000000000002'),
  ('b2c3d4e5-0001-4000-8000-000000000004', 'DJI Air 3S', 'DJI', 0.724, 19, 45, 5000, 'a1b2c3d4-0001-4000-8000-000000000003'),
  ('b2c3d4e5-0001-4000-8000-000000000005', 'DJI Mavic 3', 'DJI', 0.895, 21, 46, 5000, 'a1b2c3d4-0001-4000-8000-000000000004'),
  ('b2c3d4e5-0001-4000-8000-000000000006', 'DJI Mavic 3 Classic', 'DJI', 0.895, 21, 46, 5000, 'a1b2c3d4-0001-4000-8000-000000000004'),
  ('b2c3d4e5-0001-4000-8000-000000000007', 'DJI Mavic 3 Enterprise', 'DJI', 0.915, 21, 45, 5000, 'a1b2c3d4-0001-4000-8000-000000000005'),
  ('b2c3d4e5-0001-4000-8000-000000000008', 'DJI Matrice 4E', 'DJI', 1.050, 21, 42, 5000, 'a1b2c3d4-0001-4000-8000-000000000006'),
  ('b2c3d4e5-0001-4000-8000-000000000009', 'DJI Matrice 350 RTK', 'DJI', 6.470, 23, 55, 5000, 'a1b2c3d4-0001-4000-8000-000000000007'),
  ('b2c3d4e5-0001-4000-8000-000000000010', 'DJI Phantom 4 RTK', 'DJI', 1.391, 20, 30, 5000, 'a1b2c3d4-0001-4000-8000-000000000008'),
  ('b2c3d4e5-0001-4000-8000-000000000011', 'Autel EVO II Pro', 'Autel', 1.130, 20, 40, 4000, 'a1b2c3d4-0001-4000-8000-000000000009'),
  ('b2c3d4e5-0001-4000-8000-000000000012', 'Parrot Anafi USA', 'Parrot', 0.495, 15, 32, 4000, 'a1b2c3d4-0001-4000-8000-000000000010');

-- Insert a default demo project
INSERT INTO public.projects (id, name, description, client, location, date)
VALUES (
  'c3d4e5f6-0001-4000-8000-000000000001',
  'Demo Project',
  'Proyecto de demostración Map2Drone',
  'Demo Client',
  'Ciudad de México',
  NOW()
);
