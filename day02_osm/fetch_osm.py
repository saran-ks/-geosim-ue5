# -*- coding: utf-8 -*-
# fetch_osm.py
# Day 2 - Fetch OSM data for Herzogenaurach town centre
# Area: 300m radius around town centre
# We fetch: roads, buildings, open areas

import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('TkAgg')
import os

# Configuration
# Change these to fetch any location

CENTER_LAT  = 49.5691    # Herzogenaurach town centre
CENTER_LON  = 10.8887    # latitude and longitude
RADIUS      = 300        # metres radius around centre
OUTPUT_DIR  = "data/osm" # where to save files

def fetch_roads(center_lat, center_lon, radius):
    """
    Fetch all roads within radius metres
    of the given GPS coordinate
    Returns a GeoDataFrame with road geometry
    """
    print(f"Fetching roads within {radius}m of "
          f"{center_lat}, {center_lon}...")
    
    graph = ox.graph_from_point(
        center_point=(center_lat, center_lon),
        dist=radius,
        network_type="all"
    )
    
    nodes, edges = ox.graph_to_gdfs(graph)
    
    print(f"Found {len(edges)} road segments")
    return edges

def fetch_buildings(center_lat, center_lon, radius):
    """
    Fetch all building footprints within radius
    Returns a GeoDataFrame with building polygons
    """
    print(f"Fetching buildings...")
    
    buildings = ox.features_from_point(
        center_point=(center_lat, center_lon),
        tags={"building": True},
        dist=radius
    )
    
    print(f"Found {len(buildings)} buildings")
    
    buildings = buildings[
        buildings.geometry.geom_type == "Polygon"
    ]
    
    print(f"After filtering: {len(buildings)} building polygons")
    return buildings

def fetch_open_areas(center_lat, center_lon, radius):
    """
    Fetch parks, squares, parking lots
    filtered to remove large municipality polygons
    """
    print(f"Fetching open areas...")
    
    import pandas as pd
    
    leisure = ox.features_from_point(
        center_point=(center_lat, center_lon),
        tags={"leisure": True},
        dist=radius
    )
    
    landuse = ox.features_from_point(
        center_point=(center_lat, center_lon),
        tags={"landuse": True},
        dist=radius
    )
    
    amenity = ox.features_from_point(
        center_point=(center_lat, center_lon),
        tags={"amenity": ["parking", "marketplace"]},
        dist=radius
    )
    
    open_areas = pd.concat([leisure, landuse, amenity])
    
    # Keep only polygons
    open_areas = open_areas[
        open_areas.geometry.geom_type == "Polygon"
    ]
    
    # Filter out huge polygons
    # Large polygons = municipality boundaries
    # We only want small meaningful areas
    # Area in degrees squared
    # 0.001 degrees squared = roughly one city block
    open_areas = open_areas[
        open_areas.geometry.area < 0.001
    ]
    
    print(f"Found {len(open_areas)} open areas")
    return open_areas

def save_geojson(gdf, filename):
    """
    Save a GeoDataFrame to a GeoJSON file
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    gdf.to_file(filename, driver="GeoJSON")
    print(f"Saved: {filename}")

def visualise(roads, buildings, open_areas):
    """
    Draw all three layers on one map
    """
    print("Drawing map...")
    
    fig, ax = plt.subplots(1, 1, figsize=(12, 12))
    
    # Draw open areas first (bottom layer)
    if len(open_areas) > 0:
        open_areas.plot(
            ax=ax,
            color="lightgreen",
            alpha=0.7
        )
    
    # Draw buildings on top
    if len(buildings) > 0:
        buildings.plot(
            ax=ax,
            color="grey",
            alpha=0.9
        )
    
    # Draw roads on top of everything
    if len(roads) > 0:
        roads.plot(
            ax=ax,
            color="black",
            linewidth=1.2
        )
    
    # Manual legend patches
    import matplotlib.patches as mpatches
    import matplotlib.lines as mlines
    
    road_line    = mlines.Line2D(
        [], [], color="black", linewidth=1.2,
        label=f"Roads ({len(roads)})"
    )
    building_patch = mpatches.Patch(
        color="grey",
        label=f"Buildings ({len(buildings)})"
    )
    area_patch = mpatches.Patch(
        color="lightgreen",
        label=f"Open areas ({len(open_areas)})"
    )
    
    ax.legend(
        handles=[road_line, building_patch, area_patch],
        loc="upper right",
        fontsize=10
    )
    
    ax.set_title(
        "Herzogenaurach Town Centre\n"
        f"OSM Data - {RADIUS}m radius",
        fontsize=14
    )
    
    # Zoom to roads bounds
    if len(roads) > 0:
        bounds = roads.total_bounds
        margin = 0.001
        ax.set_xlim(bounds[0] - margin, bounds[2] + margin)
        ax.set_ylim(bounds[1] - margin, bounds[3] + margin)
    
    # White background
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    
    output_path = "outputs/herzogenaurach_osm.png"
    os.makedirs("outputs", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Map saved to: {output_path}")
    
    plt.show()
if __name__ == "__main__":
    
    print("=== OSM Data Fetcher ===")
    print(f"Location: {CENTER_LAT}, {CENTER_LON}")
    print(f"Radius: {RADIUS}m")
    print("")
    
    # Fetch all three data types
    roads      = fetch_roads(CENTER_LAT, CENTER_LON, RADIUS)
    buildings  = fetch_buildings(CENTER_LAT, CENTER_LON, RADIUS)
    open_areas = fetch_open_areas(CENTER_LAT, CENTER_LON, RADIUS)
    
    print("")
    print("=== Saving files ===")
    
    # Save each as GeoJSON
    save_geojson(roads,      f"{OUTPUT_DIR}/roads.geojson")
    save_geojson(buildings,  f"{OUTPUT_DIR}/buildings.geojson")
    save_geojson(open_areas, f"{OUTPUT_DIR}/open_areas.geojson")
    
    print("")
    print("=== Summary ===")
    print(f"Roads:      {len(roads)}")
    print(f"Buildings:  {len(buildings)}")
    print(f"Open areas: {len(open_areas)}")
    
    # Visualise
    visualise(roads, buildings, open_areas)
    
    print("")
    print("Done! Check outputs/herzogenaurach_osm.png")