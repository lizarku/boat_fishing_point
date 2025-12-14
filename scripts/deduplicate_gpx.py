#!/usr/bin/env python3
"""
GPX Waypoint Deduplication Script
- Removes duplicate waypoints within 10m radius
- Separates into west (서해) and east (동해) regions
- For Lowrance fish finder compatibility
"""

import xml.etree.ElementTree as ET
from math import radians, cos, sin, asin, sqrt
from pathlib import Path
from datetime import datetime

# Constants
DUPLICATE_RADIUS_M = 10  # meters
LON_BOUNDARY = 127.5  # longitude boundary between west and east

# GPX namespace
NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters using Haversine formula"""
    R = 6371000  # Earth radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c

def parse_waypoints(gpx_file):
    """Parse waypoints from GPX file"""
    waypoints = []
    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()

        # Handle namespace
        for wpt in root.findall('.//gpx:wpt', NS):
            lat = float(wpt.get('lat'))
            lon = float(wpt.get('lon'))

            name = wpt.find('gpx:name', NS)
            desc = wpt.find('gpx:desc', NS)
            cmt = wpt.find('gpx:cmt', NS)
            sym = wpt.find('gpx:sym', NS)
            time = wpt.find('gpx:time', NS)

            waypoints.append({
                'lat': lat,
                'lon': lon,
                'name': name.text if name is not None else '',
                'desc': desc.text if desc is not None else '',
                'cmt': cmt.text if cmt is not None else '',
                'sym': sym.text if sym is not None else 'Fish',
                'time': time.text if time is not None else ''
            })

        # Try without namespace if no waypoints found
        if not waypoints:
            for wpt in root.findall('.//wpt'):
                lat = float(wpt.get('lat'))
                lon = float(wpt.get('lon'))

                name = wpt.find('name')
                desc = wpt.find('desc')
                cmt = wpt.find('cmt')
                sym = wpt.find('sym')
                time = wpt.find('time')

                waypoints.append({
                    'lat': lat,
                    'lon': lon,
                    'name': name.text if name is not None else '',
                    'desc': desc.text if desc is not None else '',
                    'cmt': cmt.text if cmt is not None else '',
                    'sym': sym.text if sym is not None else 'Fish',
                    'time': time.text if time is not None else ''
                })
    except Exception as e:
        print(f"Error parsing {gpx_file}: {e}")

    return waypoints

def remove_duplicates(waypoints, radius_m=DUPLICATE_RADIUS_M):
    """Remove duplicate waypoints within specified radius"""
    if not waypoints:
        return []

    unique = []
    for wpt in waypoints:
        is_duplicate = False
        for existing in unique:
            dist = haversine(wpt['lat'], wpt['lon'], existing['lat'], existing['lon'])
            if dist <= radius_m:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(wpt)

    return unique

def write_gpx(waypoints, output_file, region_name):
    """Write waypoints to GPX file (Lowrance compatible)"""
    gpx_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Fishing Points Deduplicator"
     xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{region_name} Fishing Points</name>
    <desc>Deduplicated fishing points (10m radius)</desc>
    <time>{datetime.utcnow().isoformat()}Z</time>
  </metadata>
'''

    gpx_footer = '</gpx>'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(gpx_header)

        for wpt in waypoints:
            name = wpt['name'] or wpt['desc'] or 'Point'
            # Escape XML special characters
            name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            desc = (wpt['desc'] or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            cmt = (wpt['cmt'] or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            f.write(f'  <wpt lat="{wpt["lat"]:.9f}" lon="{wpt["lon"]:.9f}">\n')
            f.write(f'    <name>{name}</name>\n')
            if desc:
                f.write(f'    <desc>{desc}</desc>\n')
            if cmt:
                f.write(f'    <cmt>{cmt}</cmt>\n')
            f.write(f'    <sym>{wpt["sym"]}</sym>\n')
            f.write('  </wpt>\n')

        f.write(gpx_footer)

def main():
    base_dir = Path(__file__).parent.parent
    gpx_dir = base_dir / 'gpx'
    result_dir = base_dir / 'result'
    result_dir.mkdir(exist_ok=True)

    # Define source files
    west_files = [
        gpx_dir / 'chungnam_points.gpx',
        gpx_dir / 'new_points_chungcheong.gpx'
    ]

    east_files = [
        gpx_dir / 'gangwon_points.gpx'
    ]

    my_own_file = gpx_dir / 'my_own_points.gpx'

    # Collect waypoints
    west_points = []
    east_points = []

    # Parse west files
    for f in west_files:
        if f.exists():
            points = parse_waypoints(f)
            west_points.extend(points)
            print(f"West - {f.name}: {len(points)} points")

    # Parse east files
    for f in east_files:
        if f.exists():
            points = parse_waypoints(f)
            east_points.extend(points)
            print(f"East - {f.name}: {len(points)} points")

    # Parse my_own_points and classify by longitude
    if my_own_file.exists():
        my_points = parse_waypoints(my_own_file)
        my_west = [p for p in my_points if p['lon'] < LON_BOUNDARY]
        my_east = [p for p in my_points if p['lon'] >= LON_BOUNDARY]
        west_points.extend(my_west)
        east_points.extend(my_east)
        print(f"My own points - West: {len(my_west)}, East: {len(my_east)}")

    print(f"\nBefore deduplication:")
    print(f"  West total: {len(west_points)}")
    print(f"  East total: {len(east_points)}")

    # Remove duplicates
    west_unique = remove_duplicates(west_points)
    east_unique = remove_duplicates(east_points)

    print(f"\nAfter deduplication (10m radius):")
    print(f"  West: {len(west_points)} -> {len(west_unique)} ({len(west_points) - len(west_unique)} removed)")
    print(f"  East: {len(east_points)} -> {len(east_unique)} ({len(east_points) - len(east_unique)} removed)")

    # Write result files
    west_output = result_dir / 'west_result.gpx'
    east_output = result_dir / 'east_result.gpx'

    write_gpx(west_unique, west_output, 'West Sea (서해)')
    write_gpx(east_unique, east_output, 'East Sea (동해)')

    print(f"\nOutput files:")
    print(f"  {west_output}")
    print(f"  {east_output}")

if __name__ == '__main__':
    main()
