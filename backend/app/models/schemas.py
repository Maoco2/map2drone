import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    client = Column(String(255), default="")
    location = Column(String(255), default="")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    date = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Mission(Base):
    __tablename__ = "missions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    mission_type = Column(String(50), default="grid")
    polygon_geojson = Column(Text, default="")
    waypoints_json = Column(Text, default="")
    parameters_json = Column(Text, default="")
    grid_result_json = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Drone(Base):
    __tablename__ = "drones"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    manufacturer = Column(String(255), default="")
    weight_kg = Column(Float, default=0)
    max_speed_ms = Column(Float, default=0)
    flight_time_min = Column(Float, default=0)
    max_altitude_m = Column(Float, default=0)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    country = Column(String(255), default="")
    city = Column(String(255), default="")
    phone = Column(String(50), default="")
    gender = Column(String(50), default="")
    profession = Column(String(255), default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    sensor_width_mm = Column(Float, default=0)
    sensor_height_mm = Column(Float, default=0)
    image_width_px = Column(Integer, default=0)
    image_height_px = Column(Integer, default=0)
    focal_length_mm = Column(Float, default=0)
    pixel_size_um = Column(Float, default=0)
    shutter_speed_s = Column(Float, default=0.001)
    shutter_type = Column(String(20), default="electronic")
