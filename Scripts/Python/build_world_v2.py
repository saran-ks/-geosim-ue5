# -*- coding: utf-8 -*-
# build_world_v9.py
# Foolproof flat roads
# No rotation on roads
# Axis-aligned bounding box approach
# Run inside UE5 via Tools -> Execute Python Script

import unreal
import json
import math
import os

# ============================================
# CONFIGURATION
# ============================================

ORIGIN_LAT = 49.5691
ORIGIN_LON = 10.8887
METRES_TO_UE5 = 100.0

DEFAULT_ROAD_WIDTH = 6.0
DEFAULT_BUILDING_HEIGHT = 6.0
MIN_ROAD_WIDTH = 3.0
GROUND_SIZE = 80000.0

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
ROADS_FILE     = os.path.join(SCRIPT_DIR, "roads.geojson")
BUILDINGS_FILE = os.path.join(SCRIPT_DIR, "buildings.geojson")
AREAS_FILE     = os.path.join(SCRIPT_DIR, "open_areas.geojson")

CUBE_MESH = None
MATERIALS = {}


# ============================================
# CLEANUP
# ============================================

def delete_all_geosim_actors():
    unreal.log("Deleting previous actors...")
    subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    all_actors = subsystem.get_all_level_actors()
    deleted = 0
    for actor in all_actors:
        label = actor.get_actor_label()
        if (label.startswith("Road_") or
            label.startswith("Building_") or
            label.startswith("Area_") or
            label.startswith("Ground_")):
            subsystem.destroy_actor(actor)
            deleted += 1
    unreal.log(f"Deleted {deleted} actors")


# ============================================
# MATERIALS
# ============================================

def create_flat_material(name, r, g, b):
    asset_path = f"/Game/GeoSim/Materials/{name}"
    existing = unreal.load_asset(asset_path)
    if existing:
        return existing

    mat_factory = unreal.MaterialFactoryNew()
    asset_tools = unreal.AssetToolsHelpers\
        .get_asset_tools()
    material = asset_tools.create_asset(
        name, "/Game/GeoSim/Materials",
        unreal.Material, mat_factory
    )
    if not material:
        return None

    constant = unreal.MaterialEditingLibrary\
        .create_material_expression(
            material,
            unreal.MaterialExpressionConstant3Vector,
            -300, 0
        )
    constant.set_editor_property(
        "constant",
        unreal.LinearColor(r, g, b, 1.0)
    )
    unreal.MaterialEditingLibrary\
        .connect_material_property(
            constant, "",
            unreal.MaterialProperty.MP_BASE_COLOR
        )
    unreal.MaterialEditingLibrary\
        .recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(asset_path)
    return material


def load_assets():
    global CUBE_MESH, MATERIALS
    CUBE_MESH = unreal.load_asset(
        '/Engine/BasicShapes/Cube'
    )
    if not CUBE_MESH:
        unreal.log_error("No cube mesh")
        return False

    MATERIALS = {
        "road":     create_flat_material(
                        "M_Road",
                        0.15, 0.15, 0.15),
        "building": create_flat_material(
                        "M_Building",
                        0.75, 0.72, 0.68),
        "park":     create_flat_material(
                        "M_Park",
                        0.12, 0.45, 0.12),
        "parking":  create_flat_material(
                        "M_Parking",
                        0.45, 0.45, 0.45),
        "ground":   create_flat_material(
                        "M_Ground",
                        0.35, 0.28, 0.20),
        "water":    create_flat_material(
                        "M_Water",
                        0.05, 0.18, 0.50),
        "path":     create_flat_material(
                        "M_Path",
                        0.68, 0.62, 0.52),
    }
    unreal.log("Assets loaded")
    return True


# ============================================
# COORDINATE CONVERSION
# ============================================

def gps_to_ue5(lat, lon):
    metres_per_lat = 111320.0
    metres_per_lon = 111320.0 * math.cos(
        math.radians(ORIGIN_LAT)
    )
    x = (lon - ORIGIN_LON) * metres_per_lon \
        * METRES_TO_UE5
    y = (lat - ORIGIN_LAT) * metres_per_lat \
        * METRES_TO_UE5
    return x, y


# ============================================
# PROPERTY HELPERS
# ============================================

def get_road_width(properties):
    WIDTH_BY_TYPE = {
        "tertiary":      10.0,
        "residential":    6.0,
        "service":        4.0,
        "living_street":  6.0,
        "footway":        3.0,
        "path":           3.0,
        "cycleway":       3.0,
        "steps":          3.0,
        "track":          3.0,
    }
    osm_width = properties.get("width")
    if osm_width and osm_width != "None":
        try:
            w = float(
                str(osm_width).replace("m","").strip()
            )
            return max(w, MIN_ROAD_WIDTH)
        except:
            pass
    highway_type = properties.get(
        "highway", "residential"
    )
    if isinstance(highway_type, list):
        highway_type = highway_type[0]
    width = WIDTH_BY_TYPE.get(
        highway_type, DEFAULT_ROAD_WIDTH
    )
    return max(width, MIN_ROAD_WIDTH)


def get_building_height(properties):
    height = properties.get("height")
    if height and height != "None":
        try:
            return float(
                str(height).replace("m","").strip()
            )
        except:
            pass
    levels = properties.get("building:levels")
    if levels and levels != "None":
        try:
            return float(levels) * 3.0
        except:
            pass
    building_type = properties.get("building","yes")
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


def get_area_material_key(properties):
    leisure = properties.get("leisure") or ""
    landuse = properties.get("landuse") or ""
    amenity = properties.get("amenity") or ""
    if amenity == "parking":
        return "parking"
    if leisure in ["park","garden","playground"]:
        return "park"
    if leisure in ["pitch","track","sports_centre"]:
        return "park"
    if landuse in ["grass","meadow","farmland"]:
        return "park"
    if landuse == "cemetery":
        return "park"
    return "ground"


# ============================================
# CORE SPAWN - ZERO ROTATION ALWAYS
# ============================================

def spawn_box_flat(cx, cy, cz,
                   size_x, size_y, size_z,
                   label, material_key):
    """
    Spawn a flat box with ZERO rotation
    Always pitch=0 yaw=0 roll=0
    No rotation = no tilt ever

    cx, cy, cz:          centre position
    size_x/y/z:          dimensions in UE5 units
    """
    subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )

    actor = subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(cx, cy, cz),
        unreal.Rotator(0.0, 0.0, 0.0)
    )

    if not actor:
        return None

    actor.set_actor_label(label)

    # UE5 cube default = 100x100x100 units
    # Scale to desired size
    actor.set_actor_scale3d(unreal.Vector(
        size_x / 100.0,
        size_y / 100.0,
        size_z / 100.0
    ))

    mesh_comp = actor.static_mesh_component
    mesh_comp.set_static_mesh(CUBE_MESH)

    material = MATERIALS.get(material_key)
    if material:
        mesh_comp.set_material(0, material)

    return actor


# ============================================
# PLACE OBJECTS
# ============================================

def place_ground():
    """
    Large flat ground
    Zero rotation - always flat
    """
    size = GROUND_SIZE * METRES_TO_UE5

    spawn_box_flat(
        cx=0, cy=0, cz=-10,
        size_x=size,
        size_y=size,
        size_z=2,
        label="Ground_Base",
        material_key="ground"
    )
    unreal.log("Ground placed")


def place_road(coordinates, width_m, road_id):
    """
    FOOLPROOF FLAT ROAD APPROACH:

    For each segment between two points:
    1. Calculate the bounding box of the segment
       including road width padding
    2. Place a flat box at bounding box centre
    3. Zero rotation always

    The road will not be perfectly oriented
    along its direction for diagonal roads
    BUT it will always be perfectly flat

    This is the MVP approach
    We improve orientation later
    with proper rotated mesh approach
    """
    if len(coordinates) < 2:
        return 0

    placed = 0

    for i in range(len(coordinates) - 1):

        lon1 = coordinates[i][0]
        lat1 = coordinates[i][1]
        lon2 = coordinates[i + 1][0]
        lat2 = coordinates[i + 1][1]

        x1, y1 = gps_to_ue5(lat1, lon1)
        x2, y2 = gps_to_ue5(lat2, lon2)

        # Road width in UE5 units
        half_width = max(
            width_m, MIN_ROAD_WIDTH
        ) * METRES_TO_UE5 / 2.0

        # Bounding box of this road segment
        # with width padding on all sides
        min_x = min(x1, x2) - half_width
        max_x = max(x1, x2) + half_width
        min_y = min(y1, y2) - half_width
        max_y = max(y1, y2) + half_width

        # Centre of bounding box
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0

        # Size of bounding box
        size_x = max_x - min_x
        size_y = max_y - min_y

        # Skip tiny or huge segments
        if size_x < 10 or size_y < 10:
            continue
        if size_x > 25000 or size_y > 25000:
            continue

        spawn_box_flat(
            cx=cx, cy=cy, cz=3,
            size_x=size_x,
            size_y=size_y,
            size_z=5,
            label=f"Road_{road_id}_{i}",
            material_key="road"
        )
        placed += 1

    return placed


def place_building(coordinates, height_m,
                   building_id):
    """
    Place building
    Zero rotation always
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

    size_x = max(x_coords) - min(x_coords)
    size_y = max(y_coords) - min(y_coords)

    size_x = max(size_x, 300)
    size_y = max(size_y, 300)
    size_x = min(size_x, 10000)
    size_y = min(size_y, 10000)

    size_z = height_m * METRES_TO_UE5

    spawn_box_flat(
        cx=cx, cy=cy,
        cz=size_z / 2.0,
        size_x=size_x,
        size_y=size_y,
        size_z=size_z,
        label=f"Building_{building_id}",
        material_key="building"
    )


def place_open_area(coordinates, properties,
                    area_id):
    """
    Place open area
    Zero rotation always
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

    size_x = max(x_coords) - min(x_coords)
    size_y = max(y_coords) - min(y_coords)

    size_x = max(size_x, 100)
    size_y = max(size_y, 100)

    if size_x > 100000 or size_y > 100000:
        return

    mat_key = get_area_material_key(properties)
    area_type = (
        properties.get("leisure") or
        properties.get("landuse") or
        properties.get("amenity") or
        "open"
    )

    spawn_box_flat(
        cx=cx, cy=cy, cz=1,
        size_x=size_x,
        size_y=size_y,
        size_z=2,
        label=f"Area_{area_type}_{area_id}",
        material_key=mat_key
    )


# ============================================
# MAIN
# ============================================

def build_world():
    unreal.log("=" * 50)
    unreal.log("GeoSim World Builder v9")
    unreal.log("Zero rotation - always flat")
    unreal.log("=" * 50)

    delete_all_geosim_actors()

    if not load_assets():
        unreal.log_error("Asset loading failed")
        return

    place_ground()

    unreal.log("Building roads...")
    road_count = segment_count = 0

    with open(ROADS_FILE, 'r',
              encoding='utf-8') as f:
        roads_data = json.load(f)

    for feature in roads_data['features']:
        geom  = feature['geometry']
        props = feature['properties']
        if geom['type'] != 'LineString':
            continue
        coords = geom['coordinates']
        width  = get_road_width(props)
        placed = place_road(
            coords, width, road_count
        )
        segment_count += placed
        road_count    += 1
        if road_count % 100 == 0:
            unreal.log(f"Roads: {road_count}")

    unreal.log(f"Roads: {road_count}")
    unreal.log(f"Segments: {segment_count}")

    unreal.log("Building structures...")
    building_count = 0

    with open(BUILDINGS_FILE, 'r',
              encoding='utf-8') as f:
        buildings_data = json.load(f)

    for feature in buildings_data['features']:
        geom  = feature['geometry']
        props = feature['properties']
        if geom['type'] != 'Polygon':
            continue
        coords = geom['coordinates'][0]
        height = get_building_height(props)
        place_building(coords, height, building_count)
        building_count += 1

    unreal.log(f"Buildings: {building_count}")

    unreal.log("Building open areas...")
    area_count = 0

    with open(AREAS_FILE, 'r',
              encoding='utf-8') as f:
        areas_data = json.load(f)

    for feature in areas_data['features']:
        geom  = feature['geometry']
        props = feature['properties']
        if geom['type'] != 'Polygon':
            continue
        coords = geom['coordinates'][0]
        place_open_area(coords, props, area_count)
        area_count += 1

    unreal.log(f"Areas: {area_count}")

    unreal.log("=" * 50)
    unreal.log("Complete")
    unreal.log(f"Segments:  {segment_count}")
    unreal.log(f"Buildings: {building_count}")
    unreal.log(f"Areas:     {area_count}")
    unreal.log("=" * 50)
    unreal.log("Ctrl+A then F to view")


build_world()