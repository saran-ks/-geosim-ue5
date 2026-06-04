# -*- coding: utf-8 -*-
# build_world.py
# Builds Herzogenaurach 3D world in UE5
# from real OSM GeoJSON data
# Run this inside UE5 via:
# Tools -> Execute Python Script

import unreal
import json
import math
import os

# Origin point - centre of our area
# All coordinates calculated relative to this
ORIGIN_LAT = 49.5691
ORIGIN_LON = 10.8887

# Scale factor
# UE5 uses centimetres
# 1 metre = 100 UE5 units
METRES_TO_UE5 = 100.0

# Default values for missing data
DEFAULT_ROAD_WIDTH = 6.0
DEFAULT_BUILDING_HEIGHT = 6.0

# Global cube mesh - loaded once, used everywhere
CUBE_MESH = None

# Path to our GeoJSON files
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
ROADS_FILE     = os.path.join(SCRIPT_DIR, "roads.geojson")
BUILDINGS_FILE = os.path.join(SCRIPT_DIR, "buildings.geojson")
AREAS_FILE     = os.path.join(SCRIPT_DIR, "open_areas.geojson")


def get_cube_mesh():
    """
    Load the built-in UE5 cube mesh
    We use this for all objects
    roads, buildings, open areas
    
    /Engine/BasicShapes/Cube
    is a built-in mesh in every UE5 project
    always available, no import needed
    """
    cube = unreal.load_asset('/Engine/BasicShapes/Cube')
    return cube


def gps_to_ue5(lat, lon):
    """
    Convert GPS coordinates to UE5 coordinates
    Origin point = (0, 0, 0) in UE5
    Returns (x, y) in UE5 centimetres
    """
    metres_per_lat = 111320.0
    metres_per_lon = 111320.0 * math.cos(
        math.radians(ORIGIN_LAT)
    )

    delta_lat = lat - ORIGIN_LAT
    delta_lon = lon - ORIGIN_LON

    y_metres = delta_lat * metres_per_lat
    x_metres = delta_lon * metres_per_lon

    x_ue5 = x_metres * METRES_TO_UE5
    y_ue5 = y_metres * METRES_TO_UE5

    return x_ue5, y_ue5


def get_road_width(properties):
    """
    Get road width in metres
    Use OSM value if available
    Otherwise use German road standard RASt 06
    """
    WIDTH_BY_TYPE = {
        "tertiary":      10.0,
        "residential":    6.0,
        "service":        4.0,
        "living_street":  6.0,
        "footway":        2.0,
        "path":           1.5,
        "cycleway":       2.0,
        "steps":          2.0,
        "track":          3.0,
    }

    osm_width = properties.get("width")
    if osm_width and osm_width != "None":
        try:
            return float(str(osm_width).replace("m", "").strip())
        except:
            pass

    highway_type = properties.get("highway", "residential")
    if isinstance(highway_type, list):
        highway_type = highway_type[0]

    return WIDTH_BY_TYPE.get(highway_type, DEFAULT_ROAD_WIDTH)


def get_building_height(properties):
    """
    Get building height in metres
    Use OSM value if available
    Otherwise estimate from floors or type
    """
    height = properties.get("height")
    if height and height != "None":
        try:
            return float(str(height).replace("m", "").strip())
        except:
            pass

    levels = properties.get("building:levels")
    if levels and levels != "None":
        try:
            return float(levels) * 3.0
        except:
            pass

    building_type = properties.get("building", "yes")

    HEIGHT_BY_TYPE = {
        "residential": 6.0,
        "house":       6.0,
        "apartments":  12.0,
        "commercial":  8.0,
        "retail":      5.0,
        "school":      9.0,
        "church":      15.0,
        "garage":      3.0,
        "shed":        2.5,
        "industrial":  8.0,
    }

    return HEIGHT_BY_TYPE.get(
        str(building_type),
        DEFAULT_BUILDING_HEIGHT
    )


def place_road(coordinates, width_m, road_name="road"):
    """
    Place a road segment in UE5
    Creates a flat cube for each segment
    Assigns cube mesh so it is visible
    """
    if len(coordinates) < 2:
        return

    for i in range(len(coordinates) - 1):

        lon1, lat1 = coordinates[i]
        lon2, lat2 = coordinates[i + 1]

        x1, y1 = gps_to_ue5(lat1, lon1)
        x2, y2 = gps_to_ue5(lat2, lon2)

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        if length < 1:
            continue

        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))

        width_ue5 = width_m * METRES_TO_UE5
        thickness = 10.0

        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(cx, cy, 0),
            unreal.Rotator(0, angle, 0)
        )

        if actor:
            actor.set_actor_label(f"Road_{road_name}_{i}")
            actor.set_actor_scale3d(unreal.Vector(
                length / 100.0,
                width_ue5 / 100.0,
                thickness / 100.0
            ))
            # Assign cube mesh so actor is visible
            mesh_component = actor.static_mesh_component
            mesh_component.set_static_mesh(CUBE_MESH)


def place_building(coordinates, height_m, building_id="building"):
    """
    Place a building in UE5
    Creates a cube scaled to footprint and height
    Assigns cube mesh so it is visible
    """
    if len(coordinates) < 3:
        return

    lons = [c[0] for c in coordinates]
    lats = [c[1] for c in coordinates]

    centre_lon = sum(lons) / len(lons)
    centre_lat = sum(lats) / len(lats)

    cx, cy = gps_to_ue5(centre_lat, centre_lon)

    x_coords = []
    y_coords = []
    for lon, lat in coordinates:
        x, y = gps_to_ue5(lat, lon)
        x_coords.append(x)
        y_coords.append(y)

    width = max(x_coords) - min(x_coords)
    depth = max(y_coords) - min(y_coords)

    width = max(width, 100)
    depth = max(depth, 100)

    height_ue5 = height_m * METRES_TO_UE5
    z = height_ue5 / 2

    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(cx, cy, z),
        unreal.Rotator(0, 0, 0)
    )

    if actor:
        actor.set_actor_label(f"Building_{building_id}")
        actor.set_actor_scale3d(unreal.Vector(
            width / 100.0,
            depth / 100.0,
            height_ue5 / 100.0
        ))
        # Assign cube mesh so actor is visible
        mesh_component = actor.static_mesh_component
        mesh_component.set_static_mesh(CUBE_MESH)


def place_open_area(coordinates, area_type="park", area_id="area"):
    """
    Place an open area ground plane in UE5
    Creates a flat cube
    Assigns cube mesh so it is visible
    """
    if len(coordinates) < 3:
        return

    lons = [c[0] for c in coordinates]
    lats = [c[1] for c in coordinates]

    centre_lon = sum(lons) / len(lons)
    centre_lat = sum(lats) / len(lats)

    cx, cy = gps_to_ue5(centre_lat, centre_lon)

    x_coords = []
    y_coords = []
    for lon, lat in coordinates:
        x, y = gps_to_ue5(lat, lon)
        x_coords.append(x)
        y_coords.append(y)

    width = max(x_coords) - min(x_coords)
    depth = max(y_coords) - min(y_coords)

    width = max(width, 100)
    depth = max(depth, 100)

    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(cx, cy, -5),
        unreal.Rotator(0, 0, 0)
    )

    if actor:
        actor.set_actor_label(f"Area_{area_type}_{area_id}")
        actor.set_actor_scale3d(unreal.Vector(
            width / 100.0,
            depth / 100.0,
            0.05
        ))
        # Assign cube mesh so actor is visible
        mesh_component = actor.static_mesh_component
        mesh_component.set_static_mesh(CUBE_MESH)


def build_world():
    """
    Main function
    Reads all GeoJSON files
    Places all objects in UE5 scene
    """
    global CUBE_MESH

    unreal.log("=== GeoSim World Builder ===")
    unreal.log(f"Origin: {ORIGIN_LAT}, {ORIGIN_LON}")

    # Load cube mesh first
    # All actors share this same mesh
    unreal.log("Loading cube mesh...")
    CUBE_MESH = get_cube_mesh()

    if not CUBE_MESH:
        unreal.log_error("Could not load cube mesh. Stopping.")
        return

    unreal.log("Cube mesh loaded successfully")

    # --- ROADS ---
    unreal.log("Building roads...")
    road_count = 0

    with open(ROADS_FILE, 'r', encoding='utf-8') as f:
        roads_data = json.load(f)

    for feature in roads_data['features']:
        geometry   = feature['geometry']
        properties = feature['properties']

        if geometry['type'] != 'LineString':
            continue

        coords = geometry['coordinates']
        width  = get_road_width(properties)

        place_road(coords, width, road_count)
        road_count += 1

        if road_count % 50 == 0:
            unreal.log(f"Roads placed: {road_count}")

    unreal.log(f"Roads complete: {road_count} placed")

    # --- BUILDINGS ---
    unreal.log("Building structures...")
    building_count = 0

    with open(BUILDINGS_FILE, 'r', encoding='utf-8') as f:
        buildings_data = json.load(f)

    for feature in buildings_data['features']:
        geometry   = feature['geometry']
        properties = feature['properties']

        if geometry['type'] != 'Polygon':
            continue

        coords = geometry['coordinates'][0]
        height = get_building_height(properties)

        place_building(coords, height, building_count)
        building_count += 1

    unreal.log(f"Buildings complete: {building_count} placed")

    # --- OPEN AREAS ---
    unreal.log("Building open areas...")
    area_count = 0

    with open(AREAS_FILE, 'r', encoding='utf-8') as f:
        areas_data = json.load(f)

    for feature in areas_data['features']:
        geometry   = feature['geometry']
        properties = feature['properties']

        if geometry['type'] != 'Polygon':
            continue

        coords = geometry['coordinates'][0]
        area_type = (
            properties.get('leisure') or
            properties.get('landuse') or
            properties.get('amenity') or
            'open'
        )

        place_open_area(coords, area_type, area_count)
        area_count += 1

    unreal.log(f"Open areas complete: {area_count} placed")

    unreal.log("=== World Build Complete ===")
    unreal.log(f"Total objects placed:")
    unreal.log(f"  Roads:      {road_count}")
    unreal.log(f"  Buildings:  {building_count}")
    unreal.log(f"  Open areas: {area_count}")


# Run the builder
build_world()