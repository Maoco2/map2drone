"""Comprehensive drone and camera seed database."""

from app.models.schemas import Camera, Drone, Project

# ---------------------------------------------------------------------------
# Camera sensors – each unique sensor gets an id and full specs
# ---------------------------------------------------------------------------

CAMERAS: list[Camera] = [
    # --- 4/3" CMOS 20 MP (Hasselblad / Mecanico) – Mavic 3 / M3E ---
    Camera(id="cam-43-20mp", name='4/3" CMOS 20 MP', sensor_width_mm=17.3, sensor_height_mm=13.0, image_width_px=5280, image_height_px=3956, focal_length_mm=12, pixel_size_um=3.27, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1" CMOS 20 MP – P4RTK / P4P / Air 2S ---
    Camera(id="cam-1-20mp", name='1" CMOS 20 MP', sensor_width_mm=13.2, sensor_height_mm=8.8, image_width_px=5472, image_height_px=3648, focal_length_mm=8.8, pixel_size_um=2.41, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1/1.3" CMOS 48 MP – Mini 4 Pro / Air 3 ---
    Camera(id="cam-1-1.3-48mp", name='1/1.3" CMOS 48 MP', sensor_width_mm=8.8, sensor_height_mm=6.6, image_width_px=8000, image_height_px=6000, focal_length_mm=6.1, pixel_size_um=1.10, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1/1.3" CMOS 12 MP (binned) – Mini 3 / Mini 4 Pro 12MP mode ---
    Camera(id="cam-1-1.3-12mp", name='1/1.3" CMOS 12 MP', sensor_width_mm=8.8, sensor_height_mm=6.6, image_width_px=4000, image_height_px=3000, focal_length_mm=6.1, pixel_size_um=2.20, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1/2" CMOS 48 MP – Matrice 30T / 30, Air 2 ---
    Camera(id="cam-1-2-48mp", name='1/2" CMOS 48 MP', sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=8000, image_height_px=6000, focal_length_mm=4.4, pixel_size_um=0.80, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1/2.3" CMOS 12 MP – Mini 2 / Spark / Phantom 3 ---
    Camera(id="cam-1-2.3-12mp", name='1/2.3" CMOS 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1/1.28" CMOS 50 MP – EVO Nano+ / EVO Max ---
    Camera(id="cam-1-1.28-50mp", name='1/1.28" CMOS 50 MP', sensor_width_mm=9.8, sensor_height_mm=7.4, image_width_px=8160, image_height_px=6144, focal_length_mm=6.8, pixel_size_um=1.20, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1/2.4" CMOS 21 MP – ANAFI USA ---
    Camera(id="cam-1-2.4-21mp", name='1/2.4" CMOS 21 MP', sensor_width_mm=6.3, sensor_height_mm=4.7, image_width_px=5120, image_height_px=3840, focal_length_mm=4.4, pixel_size_um=1.23, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Zenmuse P1 24 mm (full frame 45 MP) ---
    Camera(id="cam-p1-24mm", name="Zenmuse P1 24mm 45 MP", sensor_width_mm=36.0, sensor_height_mm=24.0, image_width_px=8192, image_height_px=5460, focal_length_mm=24, pixel_size_um=4.40, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- Zenmuse P1 35 mm (full frame 45 MP) ---
    Camera(id="cam-p1-35mm", name="Zenmuse P1 35mm 45 MP", sensor_width_mm=36.0, sensor_height_mm=24.0, image_width_px=8192, image_height_px=5460, focal_length_mm=35, pixel_size_um=4.40, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- Zenmuse P1 50 mm (full frame 45 MP) ---
    Camera(id="cam-p1-50mm", name="Zenmuse P1 50mm 45 MP", sensor_width_mm=36.0, sensor_height_mm=24.0, image_width_px=8192, image_height_px=5460, focal_length_mm=50, pixel_size_um=4.40, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- Sony RX1R II Full Frame 42 MP ---
    Camera(id="cam-rx1r2", name="Sony RX1R II 42 MP", sensor_width_mm=35.9, sensor_height_mm=24.0, image_width_px=7952, image_height_px=5304, focal_length_mm=35, pixel_size_um=4.51, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Sony a7R IV / ILX-LR1 Full Frame 61 MP ---
    Camera(id="cam-a7r4", name="Sony Alpha 7R IV 61 MP", sensor_width_mm=35.9, sensor_height_mm=24.0, image_width_px=9504, image_height_px=6336, focal_length_mm=35, pixel_size_um=3.76, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Sony a7R V Full Frame 61 MP ---
    Camera(id="cam-a7r5", name="Sony Alpha 7R V 61 MP", sensor_width_mm=35.9, sensor_height_mm=24.0, image_width_px=9504, image_height_px=6336, focal_length_mm=35, pixel_size_um=3.76, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Sony Alpha 1 Full Frame 50 MP ---
    Camera(id="cam-a1", name="Sony Alpha 1 50 MP", sensor_width_mm=35.9, sensor_height_mm=24.0, image_width_px=8640, image_height_px=5760, focal_length_mm=35, pixel_size_um=4.16, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Sony a6100 APS-C 24 MP ---
    Camera(id="cam-a6100", name="Sony a6100 APS-C 24 MP", sensor_width_mm=23.5, sensor_height_mm=15.6, image_width_px=6000, image_height_px=4000, focal_length_mm=13, pixel_size_um=3.92, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Sony FX3 Full Frame 12 MP ---
    Camera(id="cam-fx3", name="Sony FX3 Full Frame 12 MP", sensor_width_mm=35.6, sensor_height_mm=20.0, image_width_px=4240, image_height_px=2384, focal_length_mm=35, pixel_size_um=8.40, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- CA103 Full Frame 61 MP ---
    Camera(id="cam-ca103", name="CA103 Full Frame 61 MP", sensor_width_mm=35.9, sensor_height_mm=24.0, image_width_px=9504, image_height_px=6336, focal_length_mm=35, pixel_size_um=3.76, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Sony UMC-R10C 20 MP ---
    Camera(id="cam-umc-r10c", name="Sony UMC-R10C 20 MP", sensor_width_mm=13.2, sensor_height_mm=8.8, image_width_px=5472, image_height_px=3648, focal_length_mm=8.8, pixel_size_um=2.41, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- senseFly S.O.D.A. 3D 20 MP ---
    Camera(id="cam-soda3d", name="senseFly S.O.D.A. 3D 20 MP", sensor_width_mm=13.2, sensor_height_mm=8.8, image_width_px=5472, image_height_px=3648, focal_length_mm=8.8, pixel_size_um=2.41, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- senseFly S.O.D.A. 20 MP ---
    Camera(id="cam-soda", name="senseFly S.O.D.A. 20 MP", sensor_width_mm=13.2, sensor_height_mm=8.8, image_width_px=5472, image_height_px=3648, focal_length_mm=8.8, pixel_size_um=2.41, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- senseFly Aivia 24 MP (APS-C) ---
    Camera(id="cam-aivia", name="senseFly Aivia 24 MP", sensor_width_mm=23.5, sensor_height_mm=15.6, image_width_px=6000, image_height_px=4000, focal_length_mm=13, pixel_size_um=3.92, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Duet M (Multispectral + RGB) ---
    Camera(id="cam-duet-m", name="Duet M Multispectral + RGB", sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=4000, image_height_px=3000, focal_length_mm=4.4, pixel_size_um=1.60, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Skydio X10 1/1.3" 48 MP ---
    Camera(id="cam-skydio-x10", name='Skydio X10 1/1.3" 48 MP', sensor_width_mm=8.8, sensor_height_mm=6.6, image_width_px=8000, image_height_px=6000, focal_length_mm=6.1, pixel_size_um=1.10, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Skydio X2E 1/2.3" 12 MP ---
    Camera(id="cam-skydio-x2e", name='Skydio X2E 1/2.3" 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Sony ILC-7RM4 61 MP ---
    Camera(id="cam-ilc7rm4", name="Sony ILC-7RM4 61 MP", sensor_width_mm=35.9, sensor_height_mm=24.0, image_width_px=9504, image_height_px=6336, focal_length_mm=35, pixel_size_um=3.76, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- APS-C 24 MP generic ---
    Camera(id="cam-apsc-24mp", name="Sensor APS-C 24 MP", sensor_width_mm=23.5, sensor_height_mm=15.6, image_width_px=6000, image_height_px=4000, focal_length_mm=13, pixel_size_um=3.92, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Oblique D2m 26 MP x 3 ---
    Camera(id="cam-d2m", name="Oblique D2m 26 MP", sensor_width_mm=23.5, sensor_height_mm=15.6, image_width_px=6240, image_height_px=4160, focal_length_mm=13, pixel_size_um=3.76, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Parrot ANAFI Ai 1/2" 48 MP ---
    Camera(id="cam-parrot-ai", name='Parrot ANAFI Ai 1/2" 48 MP', sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=8000, image_height_px=6000, focal_length_mm=4.4, pixel_size_um=0.80, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Phase One iXM-100 100 MP ---
    Camera(id="cam-ixm100", name="Phase One iXM-100 100 MP", sensor_width_mm=53.7, sensor_height_mm=40.3, image_width_px=11664, image_height_px=8750, focal_length_mm=50, pixel_size_um=4.60, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- Phase One iXM-50 50 MP ---
    Camera(id="cam-ixm50", name="Phase One iXM-50 50 MP", sensor_width_mm=43.9, sensor_height_mm=32.9, image_width_px=8280, image_height_px=6208, focal_length_mm=50, pixel_size_um=5.30, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- Zenmuse X9-8K Air 45 MP ---
    Camera(id="cam-x9-8k", name="Zenmuse X9-8K Air 45 MP", sensor_width_mm=23.1, sensor_height_mm=12.9, image_width_px=8192, image_height_px=4320, focal_length_mm=14.7, pixel_size_um=2.82, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Zenmuse X7 Super 35 24 MP ---
    Camera(id="cam-x7", name="Zenmuse X7 24 MP", sensor_width_mm=23.5, sensor_height_mm=15.7, image_width_px=6016, image_height_px=4008, focal_length_mm=15.7, pixel_size_um=3.91, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- Zenmuse X5S Micro 4/3 20.8 MP ---
    Camera(id="cam-x5s", name="Zenmuse X5S M4/3 20.8 MP", sensor_width_mm=17.3, sensor_height_mm=13.0, image_width_px=5280, image_height_px=3956, focal_length_mm=12, pixel_size_um=3.27, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Zenmuse X5 Micro 4/3 16 MP ---
    Camera(id="cam-x5", name="Zenmuse X5 M4/3 16 MP", sensor_width_mm=17.3, sensor_height_mm=13.0, image_width_px=4608, image_height_px=3456, focal_length_mm=12, pixel_size_um=3.75, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Zenmuse X3 1/2.3" 12 MP ---
    Camera(id="cam-x3", name='Zenmuse X3 1/2.3" 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Air 3S / Air 3 Wide 1/1.3" 48 MP ---
    Camera(id="cam-air3-wide", name='DJI Air 3 1/1.3" 48 MP', sensor_width_mm=8.8, sensor_height_mm=6.6, image_width_px=8000, image_height_px=6000, focal_length_mm=6.1, pixel_size_um=1.10, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mini 3 / Mini 4 Pro 1/1.3" 48 MP ---
    Camera(id="cam-mini4-48mp", name='DJI Mini 4 Pro 1/1.3" 48 MP', sensor_width_mm=8.8, sensor_height_mm=6.6, image_width_px=8000, image_height_px=6000, focal_length_mm=6.1, pixel_size_um=1.10, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mini 3 1/1.3" 12 MP ---
    Camera(id="cam-mini3-12mp", name='DJI Mini 3 1/1.3" 12 MP', sensor_width_mm=8.8, sensor_height_mm=6.6, image_width_px=4000, image_height_px=3000, focal_length_mm=6.1, pixel_size_um=2.20, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mini 2 SE / Mini SE 1/2.3" 12 MP ---
    Camera(id="cam-mini2", name='DJI Mini 2 1/2.3" 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- 1/2.6" CMOS 12 MP ---
    Camera(id="cam-1-2.6-12mp", name='1/2.6" CMOS 12 MP', sensor_width_mm=5.8, sensor_height_mm=4.3, image_width_px=4000, image_height_px=3000, focal_length_mm=4, pixel_size_um=1.45, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- MicaSense Altum-PT (Multispectral) ---
    Camera(id="cam-altum-pt", name="MicaSense Altum-PT", sensor_width_mm=7.1, sensor_height_mm=5.3, image_width_px=2064, image_height_px=1544, focal_length_mm=5.1, pixel_size_um=3.45, shutter_speed_s=0.001, shutter_type="mechanical"),
    # --- Zenmuse H20T / H30T Visual Wide ---
    Camera(id="cam-h20t", name="Zenmuse H20T 48 MP Wide", sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=8000, image_height_px=6000, focal_length_mm=4.4, pixel_size_um=0.80, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Zenmuse L2 Mapping RGB ---
    Camera(id="cam-l2", name="Zenmuse L2 Mapping RGB", sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=5280, image_height_px=3956, focal_length_mm=4.4, pixel_size_um=1.20, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Agras mapping cameras ---
    Camera(id="cam-agras-fpv", name="DJI Agras FPV HD", sensor_width_mm=4.8, sensor_height_mm=3.6, image_width_px=1920, image_height_px=1440, focal_length_mm=3.3, pixel_size_um=2.50, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Custom EO/IR 12 MP ---
    Camera(id="cam-eo-ir-12mp", name="Custom EO/IR 12 MP", sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Delair integrated 21 MP ---
    Camera(id="cam-delair-21mp", name="Delair Industrial 21 MP", sensor_width_mm=13.2, sensor_height_mm=8.8, image_width_px=5280, image_height_px=3956, focal_length_mm=8.8, pixel_size_um=2.50, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Fimi 1/2" 48 MP ---
    Camera(id="cam-fimi-48mp", name='Fimi 1/2" 48 MP', sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=8000, image_height_px=6000, focal_length_mm=4.4, pixel_size_um=0.80, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Workswell 16 MP ---
    Camera(id="cam-workswell-16mp", name="Workswell Visual 16 MP", sensor_width_mm=7.4, sensor_height_mm=5.0, image_width_px=4608, image_height_px=3456, focal_length_mm=5, pixel_size_um=1.60, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- md先進 RGB 24 MP ---
    Camera(id="cam-md-24mp", name="md先進 RGB 24 MP", sensor_width_mm=23.5, sensor_height_mm=15.6, image_width_px=6000, image_height_px=4000, focal_length_mm=13, pixel_size_um=3.92, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Custom EO Gimbal 24 MP ---
    Camera(id="cam-custom-eo-24mp", name="Custom EO Gimbal 24 MP", sensor_width_mm=23.5, sensor_height_mm=15.6, image_width_px=6000, image_height_px=4000, focal_length_mm=13, pixel_size_um=3.92, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Custom Sensor 12 MP (Manta / logistics) ---
    Camera(id="cam-custom-12mp", name="Custom Sensor 12 MP", sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic 2 Zoom 1/2.3" 12 MP ---
    Camera(id="cam-m2z", name='Mavic 2 Zoom 1/2.3" 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic 2 Pro 1" 20 MP ---
    Camera(id="cam-m2p", name='Mavic 2 Pro 1" 20 MP', sensor_width_mm=13.2, sensor_height_mm=8.8, image_width_px=5472, image_height_px=3648, focal_length_mm=10.3, pixel_size_um=2.41, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic 2 Enterprise Advanced 1/2" 48 MP ---
    Camera(id="cam-m2ea", name='Mavic 2 EA 1/2" 48 MP', sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=8000, image_height_px=6000, focal_length_mm=4.4, pixel_size_um=0.80, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic 2 Enterprise Dual Visual 12 MP ---
    Camera(id="cam-m2ed", name="Mavic 2 ED Visual 12 MP", sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic Pro 1/2.3" 12.3 MP ---
    Camera(id="cam-mp1", name='Mavic Pro 1/2.3" 12.3 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=5, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic Air 1/2.3" 12 MP ---
    Camera(id="cam-ma1", name='Mavic Air 1/2.3" 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Phantom 3 1/2.3" 12.4 MP ---
    Camera(id="cam-p3", name='Phantom 3 1/2.3" 12.4 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=3.5, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic Air 2S (Air 2S) 1" 20 MP ---
    Camera(id="cam-air2s", name='Air 2S 1" 20 MP', sensor_width_mm=13.2, sensor_height_mm=8.8, image_width_px=5472, image_height_px=3648, focal_length_mm=8.8, pixel_size_um=2.41, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Avata 2 1/1.3" 12 MP ---
    Camera(id="cam-avata2", name='Avata 2 1/1.3" 12 MP', sensor_width_mm=8.8, sensor_height_mm=6.6, image_width_px=4000, image_height_px=3000, focal_length_mm=6.1, pixel_size_um=2.20, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Avata 1/1.7" 48 MP ---
    Camera(id="cam-avata1", name='Avata 1/1.7" 48 MP', sensor_width_mm=7.6, sensor_height_mm=5.7, image_width_px=8000, image_height_px=6000, focal_length_mm=5.3, pixel_size_um=0.95, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic 3 Thermal 1/2" 48 MP ---
    Camera(id="cam-m3t", name='M3T 1/2" 48 MP Wide', sensor_width_mm=6.4, sensor_height_mm=4.8, image_width_px=8000, image_height_px=6000, focal_length_mm=4.4, pixel_size_um=0.80, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Matrice 100 X3 1/2.3" 12 MP ---
    Camera(id="cam-m100", name='Matrice 100 X3 1/2.3" 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Matrice 210 Z30 zoom ---
    Camera(id="cam-z30", name="Zenmuse Z30 12 MP Zoom", sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI FlyCart 30 FPV ---
    Camera(id="cam-fc30", name="FlyCart 30 FPV", sensor_width_mm=4.8, sensor_height_mm=3.6, image_width_px=1920, image_height_px=1440, focal_length_mm=3.3, pixel_size_um=2.50, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- DJI Mavic 3 Multiespectral RGB 20 MP ---
    Camera(id="cam-m3m", name='M3M RGB 4/3" 20 MP', sensor_width_mm=17.3, sensor_height_mm=13.0, image_width_px=5280, image_height_px=3956, focal_length_mm=12, pixel_size_um=3.27, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Skydio 2+ Enterprise 1/2.3" 12 MP ---
    Camera(id="cam-skydio2p", name='Skydio 2+ 1/2.3" 12 MP', sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
    # --- Voliro T 12 MP NDT ---
    Camera(id="cam-voliro", name="Voliro T 12 MP NDT", sensor_width_mm=6.17, sensor_height_mm=4.55, image_width_px=4000, image_height_px=3000, focal_length_mm=4.3, pixel_size_um=1.54, shutter_speed_s=0.001, shutter_type="electronic"),
]

# ---------------------------------------------------------------------------
# Drones – each entry lists manufacturer, model, weight, speed, flight time,
# max altitude, and the camera_id from above.
# ---------------------------------------------------------------------------

DRONES: list[Drone] = [
    # DJI
    Drone(id="dji-m3e",   name="Mavic 3 Enterprise (M3E)", manufacturer="DJI", weight_kg=0.915, max_speed_ms=21, flight_time_min=45, max_altitude_m=5000, camera_id="cam-43-20mp"),
    Drone(id="dji-p4rtk", name="Phantom 4 RTK", manufacturer="DJI", weight_kg=1.391, max_speed_ms=20, flight_time_min=30, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="dji-m350-p1-35", name="Matrice 350 RTK (P1 35mm)", manufacturer="DJI", weight_kg=4.0, max_speed_ms=23, flight_time_min=55, max_altitude_m=7000, camera_id="cam-p1-35mm"),
    Drone(id="dji-m350-p1-50", name="Matrice 350 RTK (P1 50mm)", manufacturer="DJI", weight_kg=4.0, max_speed_ms=23, flight_time_min=55, max_altitude_m=7000, camera_id="cam-p1-50mm"),
    Drone(id="dji-m300-p1-24", name="Matrice 300 RTK (P1 24mm)", manufacturer="DJI", weight_kg=3.6, max_speed_ms=23, flight_time_min=55, max_altitude_m=7000, camera_id="cam-p1-24mm"),
    Drone(id="dji-m300-p1-50", name="Matrice 300 RTK (P1 50mm)", manufacturer="DJI", weight_kg=3.6, max_speed_ms=23, flight_time_min=55, max_altitude_m=7000, camera_id="cam-p1-50mm"),
    Drone(id="dji-p4p-v2",  name="Phantom 4 Pro V2.0", manufacturer="DJI", weight_kg=1.375, max_speed_ms=20, flight_time_min=30, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="dji-mavic3-pro",  name="Mavic 3 Pro", manufacturer="DJI", weight_kg=0.963, max_speed_ms=21, flight_time_min=43, max_altitude_m=5000, camera_id="cam-43-20mp"),
    Drone(id="dji-mavic3-classic", name="Mavic 3 Classic", manufacturer="DJI", weight_kg=0.895, max_speed_ms=21, flight_time_min=46, max_altitude_m=5000, camera_id="cam-43-20mp"),
    Drone(id="dji-mavic3m", name="Mavic 3 Multiespectral", manufacturer="DJI", weight_kg=0.951, max_speed_ms=21, flight_time_min=43, max_altitude_m=5000, camera_id="cam-m3m"),
    Drone(id="dji-m30t",    name="Matrice 30T", manufacturer="DJI", weight_kg=3.77, max_speed_ms=23, flight_time_min=41, max_altitude_m=7000, camera_id="cam-1-2-48mp"),
    Drone(id="dji-m30",     name="Matrice 30", manufacturer="DJI", weight_kg=3.55, max_speed_ms=23, flight_time_min=41, max_altitude_m=7000, camera_id="cam-1-2-48mp"),
    Drone(id="dji-i3",      name="Inspire 3", manufacturer="DJI", weight_kg=3.95, max_speed_ms=26, flight_time_min=30, max_altitude_m=5000, camera_id="cam-x9-8k"),
    Drone(id="dji-i2",      name="Inspire 2", manufacturer="DJI", weight_kg=3.44, max_speed_ms=26, flight_time_min=27, max_altitude_m=5000, camera_id="cam-x7"),
    Drone(id="dji-mini4p",  name="Mini 4 Pro", manufacturer="DJI", weight_kg=0.249, max_speed_ms=16, flight_time_min=34, max_altitude_m=4000, camera_id="cam-mini4-48mp"),
    Drone(id="dji-mini3p",  name="Mini 3 Pro", manufacturer="DJI", weight_kg=0.249, max_speed_ms=16, flight_time_min=34, max_altitude_m=4000, camera_id="cam-mini4-48mp"),
    Drone(id="dji-mini3",   name="Mini 3", manufacturer="DJI", weight_kg=0.248, max_speed_ms=16, flight_time_min=38, max_altitude_m=4000, camera_id="cam-mini3-12mp"),
    Drone(id="dji-mini2se", name="Mini 2 SE", manufacturer="DJI", weight_kg=0.246, max_speed_ms=16, flight_time_min=31, max_altitude_m=4000, camera_id="cam-mini2"),
    Drone(id="dji-air3",    name="Air 3", manufacturer="DJI", weight_kg=0.720, max_speed_ms=19, flight_time_min=46, max_altitude_m=5000, camera_id="cam-air3-wide"),
    Drone(id="dji-air2s",   name="Air 2S", manufacturer="DJI", weight_kg=0.595, max_speed_ms=19, flight_time_min=31, max_altitude_m=5000, camera_id="cam-air2s"),
    Drone(id="dji-m2p",     name="Mavic 2 Pro", manufacturer="DJI", weight_kg=0.907, max_speed_ms=18, flight_time_min=31, max_altitude_m=5000, camera_id="cam-m2p"),
    Drone(id="dji-m2ea",    name="Mavic 2 Enterprise Advanced", manufacturer="DJI", weight_kg=0.909, max_speed_ms=18, flight_time_min=31, max_altitude_m=5000, camera_id="cam-m2ea"),
    Drone(id="dji-p4a",     name="Phantom 4 Advanced", manufacturer="DJI", weight_kg=1.380, max_speed_ms=20, flight_time_min=30, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="dji-p4advp",  name="Phantom 4 Advanced+", manufacturer="DJI", weight_kg=1.380, max_speed_ms=20, flight_time_min=30, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="dji-p4obs",   name="Phantom 4 Obsidian", manufacturer="DJI", weight_kg=1.380, max_speed_ms=20, flight_time_min=30, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="dji-p4pv1",   name="Phantom 4 Pro V1.0", manufacturer="DJI", weight_kg=1.388, max_speed_ms=20, flight_time_min=30, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="dji-p4",      name="Phantom 4 Standard", manufacturer="DJI", weight_kg=1.380, max_speed_ms=20, flight_time_min=28, max_altitude_m=5000, camera_id="cam-1-2.3-12mp"),
    Drone(id="dji-p3p",     name="Phantom 3 Professional", manufacturer="DJI", weight_kg=1.280, max_speed_ms=16, flight_time_min=23, max_altitude_m=5000, camera_id="cam-p3"),
    Drone(id="dji-p3a",     name="Phantom 3 Advanced", manufacturer="DJI", weight_kg=1.280, max_speed_ms=16, flight_time_min=23, max_altitude_m=5000, camera_id="cam-p3"),
    Drone(id="dji-m3pc",    name="Mavic 3 Pro Cine", manufacturer="DJI", weight_kg=0.963, max_speed_ms=21, flight_time_min=43, max_altitude_m=5000, camera_id="cam-43-20mp"),
    Drone(id="dji-m2z",     name="Mavic 2 Zoom", manufacturer="DJI", weight_kg=0.905, max_speed_ms=18, flight_time_min=31, max_altitude_m=5000, camera_id="cam-m2z"),
    Drone(id="dji-mp1",     name="Mavic Pro (Original)", manufacturer="DJI", weight_kg=0.734, max_speed_ms=18, flight_time_min=27, max_altitude_m=5000, camera_id="cam-mp1"),
    Drone(id="dji-air2",    name="Mavic Air 2", manufacturer="DJI", weight_kg=0.570, max_speed_ms=19, flight_time_min=34, max_altitude_m=5000, camera_id="cam-1-2-48mp"),
    Drone(id="dji-air2s-fm",name="Mavic Air 2S Fly More", manufacturer="DJI", weight_kg=0.595, max_speed_ms=19, flight_time_min=31, max_altitude_m=5000, camera_id="cam-air2s"),
    Drone(id="dji-ma1",     name="Mavic Air (Original)", manufacturer="DJI", weight_kg=0.430, max_speed_ms=16, flight_time_min=21, max_altitude_m=5000, camera_id="cam-ma1"),
    Drone(id="dji-i2-x5s",  name="Inspire 2 (X5S)", manufacturer="DJI", weight_kg=3.44, max_speed_ms=26, flight_time_min=27, max_altitude_m=5000, camera_id="cam-x5s"),
    Drone(id="dji-i1p",     name="Inspire 1 Pro", manufacturer="DJI", weight_kg=3.0, max_speed_ms=22, flight_time_min=18, max_altitude_m=4500, camera_id="cam-x5"),
    Drone(id="dji-i1",      name="Inspire 1", manufacturer="DJI", weight_kg=2.84, max_speed_ms=22, flight_time_min=18, max_altitude_m=4500, camera_id="cam-x3"),
    Drone(id="dji-mini2se-crop", name="Mini 2 SE (Modo Recortado)", manufacturer="DJI", weight_kg=0.246, max_speed_ms=16, flight_time_min=31, max_altitude_m=4000, camera_id="cam-mini2"),
    Drone(id="dji-mini-se", name="Mini SE", manufacturer="DJI", weight_kg=0.242, max_speed_ms=13, flight_time_min=30, max_altitude_m=3000, camera_id="cam-mini2"),
    Drone(id="dji-m2ed",    name="Mavic 2 Enterprise Dual", manufacturer="DJI", weight_kg=0.909, max_speed_ms=18, flight_time_min=31, max_altitude_m=5000, camera_id="cam-m2ed"),
    Drone(id="dji-m3t",     name="Mavic 3 Thermal (M3T)", manufacturer="DJI", weight_kg=0.961, max_speed_ms=21, flight_time_min=45, max_altitude_m=5000, camera_id="cam-m3t"),
    Drone(id="dji-m300-h20t", name="Matrice 300 RTK (H20T)", manufacturer="DJI", weight_kg=3.6, max_speed_ms=23, flight_time_min=55, max_altitude_m=7000, camera_id="cam-h20t"),
    Drone(id="dji-m210-x7", name="Matrice 210 RTK V2 (X7)", manufacturer="DJI", weight_kg=3.6, max_speed_ms=20, flight_time_min=32, max_altitude_m=5000, camera_id="cam-x7"),
    Drone(id="dji-m200-x5s",name="Matrice 200 V2 (X5S)", manufacturer="DJI", weight_kg=3.6, max_speed_ms=20, flight_time_min=32, max_altitude_m=5000, camera_id="cam-x5s"),
    Drone(id="dji-m600p",   name="Matrice 600 Pro", manufacturer="DJI", weight_kg=9.5, max_speed_ms=18, flight_time_min=36, max_altitude_m=4500, camera_id="cam-a7r4"),
    Drone(id="dji-agras-t50", name="Agras T50", manufacturer="DJI", weight_kg=29.0, max_speed_ms=10, flight_time_min=15, max_altitude_m=2000, camera_id="cam-agras-fpv"),
    Drone(id="dji-agras-t40", name="Agras T40", manufacturer="DJI", weight_kg=29.0, max_speed_ms=10, flight_time_min=15, max_altitude_m=2000, camera_id="cam-agras-fpv"),
    Drone(id="dji-agras-t25", name="Agras T25", manufacturer="DJI", weight_kg=20.0, max_speed_ms=10, flight_time_min=15, max_altitude_m=2000, camera_id="cam-agras-fpv"),
    Drone(id="dji-agras-t20p", name="Agras T20P", manufacturer="DJI", weight_kg=20.0, max_speed_ms=10, flight_time_min=15, max_altitude_m=2000, camera_id="cam-agras-fpv"),
    Drone(id="dji-fc30",    name="FlyCart 30", manufacturer="DJI", weight_kg=42.0, max_speed_ms=20, flight_time_min=18, max_altitude_m=3000, camera_id="cam-fc30"),
    Drone(id="dji-avata2",  name="Avata 2", manufacturer="DJI", weight_kg=0.377, max_speed_ms=8, flight_time_min=23, max_altitude_m=5000, camera_id="cam-avata2"),
    Drone(id="dji-avata",   name="Avata", manufacturer="DJI", weight_kg=0.410, max_speed_ms=8, flight_time_min=18, max_altitude_m=5000, camera_id="cam-avata1"),
    Drone(id="dji-spark",   name="Spark", manufacturer="DJI", weight_kg=0.300, max_speed_ms=14, flight_time_min=16, max_altitude_m=4000, camera_id="cam-1-2.3-12mp"),
    Drone(id="dji-mini4p-12mp", name="Mini 4 Pro (Modo 12MP)", manufacturer="DJI", weight_kg=0.249, max_speed_ms=16, flight_time_min=34, max_altitude_m=4000, camera_id="cam-1-1.3-12mp"),
    Drone(id="dji-mini2",   name="Mini 2", manufacturer="DJI", weight_kg=0.249, max_speed_ms=16, flight_time_min=31, max_altitude_m=4000, camera_id="cam-mini2"),
    Drone(id="dji-m100",    name="Matrice 100", manufacturer="DJI", weight_kg=2.43, max_speed_ms=17, flight_time_min=33, max_altitude_m=4000, camera_id="cam-m100"),
    Drone(id="dji-m350-h30t", name="Matrice 350 RTK (H30T)", manufacturer="DJI", weight_kg=4.0, max_speed_ms=23, flight_time_min=55, max_altitude_m=7000, camera_id="cam-h20t"),
    Drone(id="dji-m210-x5s", name="Matrice 210 RTK V2 (X5S)", manufacturer="DJI", weight_kg=3.6, max_speed_ms=20, flight_time_min=32, max_altitude_m=5000, camera_id="cam-x5s"),
    Drone(id="dji-m210-z30", name="Matrice 210 V2 (Z30)", manufacturer="DJI", weight_kg=3.6, max_speed_ms=20, flight_time_min=32, max_altitude_m=5000, camera_id="cam-z30"),
    Drone(id="dji-m350-l2",  name="Matrice 350 RTK (L2)", manufacturer="DJI", weight_kg=4.0, max_speed_ms=23, flight_time_min=55, max_altitude_m=7000, camera_id="cam-l2"),
    Drone(id="dji-agras-t30",name="Agras T30", manufacturer="DJI", weight_kg=26.0, max_speed_ms=10, flight_time_min=10, max_altitude_m=2000, camera_id="cam-agras-fpv"),

    # Autel Robotics
    Drone(id="autel-evo2p-v3", name="EVO II Pro V3", manufacturer="Autel Robotics", weight_kg=1.130, max_speed_ms=20, flight_time_min=40, max_altitude_m=4000, camera_id="cam-1-20mp"),
    Drone(id="autel-evo2-rtk-v3", name="EVO II RTK V3", manufacturer="Autel Robotics", weight_kg=1.130, max_speed_ms=20, flight_time_min=40, max_altitude_m=4000, camera_id="cam-1-20mp"),
    Drone(id="autel-evo-max-4t", name="EVO Max 4T", manufacturer="Autel Robotics", weight_kg=1.95, max_speed_ms=22, flight_time_min=42, max_altitude_m=5000, camera_id="cam-1-1.28-50mp"),
    Drone(id="autel-evo-max-4n", name="EVO Max 4N", manufacturer="Autel Robotics", weight_kg=1.95, max_speed_ms=22, flight_time_min=42, max_altitude_m=5000, camera_id="cam-1-1.28-50mp"),
    Drone(id="autel-evo2-dual",  name="EVO II Dual 640T V3", manufacturer="Autel Robotics", weight_kg=1.130, max_speed_ms=20, flight_time_min=40, max_altitude_m=4000, camera_id="cam-1-1.28-50mp"),
    Drone(id="autel-evo2p-rtk-v2", name="EVO II Pro RTK V2", manufacturer="Autel Robotics", weight_kg=1.130, max_speed_ms=20, flight_time_min=40, max_altitude_m=4000, camera_id="cam-1-20mp"),
    Drone(id="autel-evo-lite-plus", name="EVO Lite+", manufacturer="Autel Robotics", weight_kg=0.835, max_speed_ms=18, flight_time_min=40, max_altitude_m=4000, camera_id="cam-1-20mp"),
    Drone(id="autel-evo-nano-plus", name="EVO Nano+", manufacturer="Autel Robotics", weight_kg=0.249, max_speed_ms=17, flight_time_min=28, max_altitude_m=4000, camera_id="cam-1-1.28-50mp"),

    # Wingtra
    Drone(id="wingtra-rx1r",  name="WingtraRAY / One Gen II (RX1R)", manufacturer="Wingtra", weight_kg=3.5, max_speed_ms=16, flight_time_min=55, max_altitude_m=5000, camera_id="cam-rx1r2"),
    Drone(id="wingtra-a6100", name="WingtraRAY / One Gen II (a6100)", manufacturer="Wingtra", weight_kg=3.5, max_speed_ms=16, flight_time_min=55, max_altitude_m=5000, camera_id="cam-a6100"),
    Drone(id="wingtra-ca103", name="WingtraRAY VTOL (CA103)", manufacturer="Wingtra", weight_kg=4.0, max_speed_ms=16, flight_time_min=55, max_altitude_m=5000, camera_id="cam-ca103"),

    # senseFly (AgEagle)
    Drone(id="sf-ebee-soda3d", name="eBee X (S.O.D.A. 3D)", manufacturer="senseFly (AgEagle)", weight_kg=1.1, max_speed_ms=18, flight_time_min=59, max_altitude_m=4500, camera_id="cam-soda3d"),
    Drone(id="sf-ebee-aivia",  name="eBee X (Aivia)", manufacturer="senseFly (AgEagle)", weight_kg=1.1, max_speed_ms=18, flight_time_min=59, max_altitude_m=4500, camera_id="cam-aivia"),
    Drone(id="sf-ebee-geo",    name="eBee Geo", manufacturer="senseFly (AgEagle)", weight_kg=0.7, max_speed_ms=18, flight_time_min=45, max_altitude_m=4000, camera_id="cam-soda"),
    Drone(id="sf-ebee-ag",    name="eBee Ag", manufacturer="senseFly (AgEagle)", weight_kg=0.7, max_speed_ms=18, flight_time_min=45, max_altitude_m=4000, camera_id="cam-duet-m"),

    # Skydio
    Drone(id="skydio-x10", name="X10", manufacturer="Skydio", weight_kg=1.6, max_speed_ms=15, flight_time_min=32, max_altitude_m=4000, camera_id="cam-skydio-x10"),
    Drone(id="skydio-x2e", name="X2E", manufacturer="Skydio", weight_kg=1.2, max_speed_ms=15, flight_time_min=35, max_altitude_m=4000, camera_id="cam-skydio-x2e"),
    Drone(id="skydio-2p",  name="2+ Enterprise", manufacturer="Skydio", weight_kg=0.8, max_speed_ms=14, flight_time_min=27, max_altitude_m=4000, camera_id="cam-skydio2p"),

    # JOUAV
    Drone(id="jouav-cw15",   name="CW-15 (VTOL)", manufacturer="JOUAV", weight_kg=6.5, max_speed_ms=20, flight_time_min=90, max_altitude_m=5000, camera_id="cam-ilc7rm4"),
    Drone(id="jouav-cw007",  name="CW-007 (VTOL)", manufacturer="JOUAV", weight_kg=3.2, max_speed_ms=18, flight_time_min=60, max_altitude_m=4000, camera_id="cam-apsc-24mp"),

    # Quantum Systems
    Drone(id="qs-trinity-rx1r", name="Trinity F90+ (RX1R)", manufacturer="Quantum Systems", weight_kg=3.2, max_speed_ms=16, flight_time_min=90, max_altitude_m=5000, camera_id="cam-rx1r2"),
    Drone(id="qs-trinity-oblique", name="Trinity F90+ (Oblique)", manufacturer="Quantum Systems", weight_kg=3.2, max_speed_ms=16, flight_time_min=90, max_altitude_m=5000, camera_id="cam-d2m"),
    Drone(id="qs-vector",    name="Vector / Scorpion", manufacturer="Quantum Systems", weight_kg=2.5, max_speed_ms=18, flight_time_min=90, max_altitude_m=5000, camera_id="cam-umc-r10c"),

    # Parrot
    Drone(id="parrot-anafi-ai", name="ANAFI Ai", manufacturer="Parrot", weight_kg=0.440, max_speed_ms=15, flight_time_min=32, max_altitude_m=5000, camera_id="cam-parrot-ai"),
    Drone(id="parrot-anafi-usa", name="ANAFI USA", manufacturer="Parrot", weight_kg=0.440, max_speed_ms=15, flight_time_min=32, max_altitude_m=5000, camera_id="cam-1-2.4-21mp"),

    # Sony
    Drone(id="sony-airpeak-a7r5", name="Airpeak S1 (a7R V)", manufacturer="Sony", weight_kg=1.5, max_speed_ms=19, flight_time_min=22, max_altitude_m=5000, camera_id="cam-a7r5"),
    Drone(id="sony-airpeak-a1",    name="Airpeak S1 (Alpha 1)", manufacturer="Sony", weight_kg=1.5, max_speed_ms=19, flight_time_min=22, max_altitude_m=5000, camera_id="cam-a1"),

    # Freefly Systems
    Drone(id="freefly-astro-fx3",  name="Astro (FX3)", manufacturer="Freefly Systems", weight_kg=1.2, max_speed_ms=15, flight_time_min=30, max_altitude_m=4000, camera_id="cam-fx3"),
    Drone(id="freefly-astro-a7r4", name="Astro (a7R IV)", manufacturer="Freefly Systems", weight_kg=1.2, max_speed_ms=15, flight_time_min=30, max_altitude_m=4000, camera_id="cam-a7r4"),
    Drone(id="freefly-alta-x",     name="Alta X", manufacturer="Freefly Systems", weight_kg=7.0, max_speed_ms=15, flight_time_min=20, max_altitude_m=4000, camera_id="cam-ixm100"),

    # Yuneec
    Drone(id="yuneec-h520e",   name="H520E", manufacturer="Yuneec", weight_kg=1.6, max_speed_ms=18, flight_time_min=28, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="yuneec-h850r",   name="H850-RTK", manufacturer="Yuneec", weight_kg=4.5, max_speed_ms=18, flight_time_min=30, max_altitude_m=5000, camera_id="cam-1-20mp"),
    Drone(id="yuneec-th-plus", name="Typhoon H Plus", manufacturer="Yuneec", weight_kg=1.6, max_speed_ms=18, flight_time_min=25, max_altitude_m=5000, camera_id="cam-1-20mp"),

    # ACSL
    Drone(id="acsl-soten", name="SOTEN", manufacturer="ACSL", weight_kg=1.2, max_speed_ms=18, flight_time_min=40, max_altitude_m=5000, camera_id="cam-1-20mp"),

    # Acecore
    Drone(id="acecore-noa",    name="Noa (Hexacopter)", manufacturer="Acecore", weight_kg=6.5, max_speed_ms=18, flight_time_min=25, max_altitude_m=4000, camera_id="cam-ixm50"),
    Drone(id="acecore-zoe",    name="Zoe (Quadcopter)", manufacturer="Acecore", weight_kg=2.5, max_speed_ms=18, flight_time_min=30, max_altitude_m=4000, camera_id="cam-a7r4"),

    # Flyability
    Drone(id="flyability-elios3", name="Elios 3", manufacturer="Flyability", weight_kg=1.5, max_speed_ms=5, flight_time_min=10, max_altitude_m=100, camera_id="cam-1-2.3-12mp"),
    Drone(id="flyability-elios2", name="Elios 2", manufacturer="Flyability", weight_kg=1.2, max_speed_ms=5, flight_time_min=10, max_altitude_m=100, camera_id="cam-1-2.3-12mp"),

    # Voliro
    Drone(id="voliro-t", name="Voliro T", manufacturer="Voliro", weight_kg=2.5, max_speed_ms=5, flight_time_min=12, max_altitude_m=100, camera_id="cam-voliro"),

    # Microdrones
    Drone(id="md-md41000",    name="md4-1000", manufacturer="Microdrones", weight_kg=3.0, max_speed_ms=18, flight_time_min=45, max_altitude_m=5000, camera_id="cam-md-24mp"),
    Drone(id="md-md43000",    name="md4-3000", manufacturer="Microdrones", weight_kg=7.0, max_speed_ms=18, flight_time_min=40, max_altitude_m=5000, camera_id="cam-ixm100"),

    # Harris Aerial
    Drone(id="harris-h6", name="Carrier H6", manufacturer="Harris Aerial", weight_kg=7.0, max_speed_ms=15, flight_time_min=20, max_altitude_m=4000, camera_id="cam-a7r4"),

    # INSITU (Boeing)
    Drone(id="insitu-scaneagle3", name="ScanEagle3", manufacturer="INSITU (Boeing)", weight_kg=20.0, max_speed_ms=25, flight_time_min=1440, max_altitude_m=5000, camera_id="cam-eo-ir-12mp"),

    # Delair
    Drone(id="delair-ux11", name="UX11 (Fixed-Wing)", manufacturer="Delair", weight_kg=1.3, max_speed_ms=18, flight_time_min=59, max_altitude_m=5000, camera_id="cam-delair-21mp"),

    # Fixed Wing Aviation
    Drone(id="fwa-alti-transit", name="Alti Transit (VTOL)", manufacturer="Fixed Wing Aviation", weight_kg=4.5, max_speed_ms=20, flight_time_min=120, max_altitude_m=5000, camera_id="cam-rx1r2"),

    # Hubsan
    Drone(id="hubsan-zino-bh2", name="Zino Blackhawk 2", manufacturer="Hubsan", weight_kg=0.470, max_speed_ms=18, flight_time_min=32, max_altitude_m=4000, camera_id="cam-1-2.6-12mp"),

    # Fimi (Xiaomi)
    Drone(id="fimi-x8se", name="X8 SE 2022 V2", manufacturer="Fimi (Xiaomi)", weight_kg=0.530, max_speed_ms=18, flight_time_min=35, max_altitude_m=5000, camera_id="cam-fimi-48mp"),
    Drone(id="fimi-manta", name="Manta (VTOL)", manufacturer="Fimi (Xiaomi)", weight_kg=2.8, max_speed_ms=16, flight_time_min=120, max_altitude_m=5000, camera_id="cam-custom-12mp"),

    # Workswell
    Drone(id="workswell-wiris", name="WIRIS Enterprise Drone", manufacturer="Workswell", weight_kg=1.5, max_speed_ms=15, flight_time_min=30, max_altitude_m=4000, camera_id="cam-workswell-16mp"),

    # Threod Systems
    Drone(id="threod-stream-c", name="Stream C (VTOL)", manufacturer="Threod Systems", weight_kg=4.0, max_speed_ms=20, flight_time_min=120, max_altitude_m=5000, camera_id="cam-custom-eo-24mp"),

    # Event 38
    Drone(id="event38-e400", name="E400 (VTOL)", manufacturer="Event 38", weight_kg=3.0, max_speed_ms=18, flight_time_min=90, max_altitude_m=5000, camera_id="cam-rx1r2"),

    # Skyfront
    Drone(id="skyfront-p8", name="Perimeter 8 (Hibrido)", manufacturer="Skyfront", weight_kg=5.5, max_speed_ms=18, flight_time_min=240, max_altitude_m=5000, camera_id="cam-a7r4"),

    # Inspired Flight
    Drone(id="if-if1200a-a7r5", name="IF1200A (a7R V)", manufacturer="Inspired Flight", weight_kg=6.5, max_speed_ms=18, flight_time_min=30, max_altitude_m=5000, camera_id="cam-a7r5"),
    Drone(id="if-if1200a-ixm50", name="IF1200A (iXM-50)", manufacturer="Inspired Flight", weight_kg=6.5, max_speed_ms=18, flight_time_min=30, max_altitude_m=5000, camera_id="cam-ixm50"),

    # Watts Innovations
    Drone(id="watts-prism-ixm100", name="Prism Sky (iXM-100)", manufacturer="Watts Innovations", weight_kg=7.0, max_speed_ms=18, flight_time_min=25, max_altitude_m=4000, camera_id="cam-ixm100"),
    Drone(id="watts-prism-ilxlr1", name="Prism Sky (ILX-LR1)", manufacturer="Watts Innovations", weight_kg=7.0, max_speed_ms=18, flight_time_min=25, max_altitude_m=4000, camera_id="cam-a7r4"),

    # Atmos UAV
    Drone(id="atmos-marlyn-rx1r", name="Marlyn Cobalt (RX1R)", manufacturer="Atmos UAV", weight_kg=3.5, max_speed_ms=18, flight_time_min=90, max_altitude_m=5000, camera_id="cam-rx1r2"),
    Drone(id="atmos-marlyn-altum", name="Marlyn Cobalt (Altum)", manufacturer="Atmos UAV", weight_kg=3.5, max_speed_ms=18, flight_time_min=90, max_altitude_m=5000, camera_id="cam-altum-pt"),
]
