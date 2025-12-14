#!/usr/bin/env python3
"""
GPX Waypoint Deduplication Script
- Removes duplicate waypoints within 10m radius
- Separates into west (서해) and east (동해) regions
- Renames waypoints for Lowrance fish finder compatibility
"""

import xml.etree.ElementTree as ET
from math import radians, cos, sin, asin, sqrt
from pathlib import Path
from datetime import datetime, timezone

# Constants
DUPLICATE_RADIUS_M = 10  # meters
LON_BOUNDARY = 127.5  # longitude boundary between west and east

# GPX namespace
NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}

# Reef type abbreviation mapping (어초 약어 매핑)
REEF_ABBREV = {
    # 주요 어초 (빈도순)
    '사각형어초': '사각',
    '사각형': '사각',
    '사각': '사각',
    '잠보형어초': '잠보',
    '잠보형': '잠보',
    '테트라형어초': '테트라',
    '테트라형': '테트라',
    '테트라': '테트라',
    '대형전주어초': '대전주',
    '신요철형어초': '신요철',
    '신요철': '신요철',
    '팔각상자형강제어초': '팔각',
    '팔각상자형강제': '팔각',
    '팔각상자형어초': '팔각',
    '폴리콘어초': '폴리콘',
    '대형강제어초': '대강제',
    '강제고기굴어초': '고기굴',
    '뿔삼각형어초': '뿔삼각',
    '연약지반용강제어초': '연약',
    '돔형증식어초': '돔형',
    '돔형중식': '돔형',
    '원통형': '원통',
    '원통': '원통',
    '2단상자형강제어초': '2단상자',
    '2단상자강제형어초': '2단상자',
    '단상자형강제어초': '2단상자',
    '단상자형강제': '2단상자',
    '날개부를가진어초': '날개',
    '날개부': '날개',
    '석재조합식어초': '석재',
    '텐트형어초': '텐트',
    '텐트형인공어초': '텐트',
    '텐트형': '텐트',
    '다면체인공어초': '다면체',
    '아치형어초': '아치',
    '아치형': '아치',
    '사각전주어초': '사전주',
    '시험어초사각전주': '사전주',
    '정삼각뿔어초': '정삼각',
    '정삼각뿔형어초': '정삼각',
    '시험어초': '시험',
    '피라미드강제어초': '피라미드',
    '이중돔형어초': '이중돔',
    '계단형인공어초': '계단',
    '계단식어초': '계단',
    '탑기단형강제어초': '탑기단',
    '삼단격실형강제어초': '삼단격실',
    '삼단격실형인공어초': '삼단격실',
    '사다리꼴복합강제어초': '사다리',
    '사다리꼴복합어초': '사다리',
    '팔각별강제어초': '팔각별',
    '터널형어초': '터널',
    '터널형': '터널',
    '방사형인공어초': '방사형',
    '방사형어초': '방사형',
    '원통2단강제어초': '원통2단',
    '유선형어초': '유선형',
    '유선형격판이있는대형사각어초': '유선사각',
    '용승유도형인공어초': '용승',
    '상자형강제': '상자강제',
    '빔어초': '빔',
    '다기능성어초': '다기능',
    '다기능삼각형어초': '다기능삼각',
    '패조류용황토어초': '황토',
    '팔각반구형중형': '팔각반구',
    '팔각반구형소형강제어초': '팔각반구',
    '트리톤': '트리톤',
    '사단경사형어초': '사단경사',
    '복합형': '복합',
    '침목': '침목',
    '육각패널': '육각',
    '삼곡면어패류용어초': '삼곡면',
    '단강제어초': '단강제',
    # 보강/추가 태그
    '보강': '',
    '추가': '',
}

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters using Haversine formula"""
    R = 6371000  # Earth radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c

def extract_reef_type(name, desc=''):
    """Extract and abbreviate reef type from waypoint name or description"""
    # Try name first, then desc
    for text in [name, desc]:
        if not text:
            continue

        # Try to find matching reef type (longer patterns first for better matching)
        sorted_items = sorted(REEF_ABBREV.items(), key=lambda x: -len(x[0]))
        for full_name, abbrev in sorted_items:
            if full_name in text:
                if abbrev:  # Skip empty abbreviations (보강, 추가 등)
                    return abbrev

    return None

def parse_waypoints(gpx_file, source_type='reef'):
    """
    Parse waypoints from GPX file
    source_type: 'reef' (어초), 'other' (다른사람), 'own' (개인)
    """
    waypoints = []
    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()

        # Handle namespace
        wpt_elements = root.findall('.//gpx:wpt', NS)
        if not wpt_elements:
            wpt_elements = root.findall('.//wpt')

        for wpt in wpt_elements:
            lat = float(wpt.get('lat'))
            lon = float(wpt.get('lon'))

            name = wpt.find('gpx:name', NS)
            if name is None:
                name = wpt.find('name')

            desc = wpt.find('gpx:desc', NS)
            if desc is None:
                desc = wpt.find('desc')

            cmt = wpt.find('gpx:cmt', NS)
            if cmt is None:
                cmt = wpt.find('cmt')

            sym = wpt.find('gpx:sym', NS)
            if sym is None:
                sym = wpt.find('sym')

            name_text = name.text if name is not None else ''
            desc_text = desc.text if desc is not None else ''

            waypoints.append({
                'lat': lat,
                'lon': lon,
                'original_name': name_text or desc_text,
                'desc': desc_text,
                'cmt': cmt.text if cmt is not None else '',
                'sym': sym.text if sym is not None else 'Fish',
                'source_type': source_type
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

def generate_short_names(waypoints):
    """Generate short names for waypoints based on source type and reef type"""
    # Group by naming category
    counters = {}  # {'reef_type': count, 'own': count, 'oth': count}

    for wpt in waypoints:
        source_type = wpt['source_type']

        if source_type == 'own':
            prefix = 'own'
        elif source_type == 'other':
            prefix = 'oth'
        else:  # reef
            reef_type = extract_reef_type(wpt['original_name'], wpt.get('desc', ''))
            if reef_type:
                prefix = reef_type
            else:
                # Fallback: 어초 종류 미상
                prefix = '어초'

        # Increment counter
        if prefix not in counters:
            counters[prefix] = 0
        counters[prefix] += 1

        # Generate short name
        wpt['short_name'] = f"{prefix}_{counters[prefix]:03d}"

    return waypoints

def write_gpx(waypoints, output_file, region_name):
    """Write waypoints to GPX file (Lowrance compatible)"""
    gpx_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Fishing Points Deduplicator"
     xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{region_name} Fishing Points</name>
    <desc>Deduplicated fishing points (10m radius)</desc>
    <time>{datetime.now(timezone.utc).isoformat()}</time>
  </metadata>
'''

    gpx_footer = '</gpx>'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(gpx_header)

        for wpt in waypoints:
            name = wpt['short_name']
            # Store original name in desc for reference
            original = wpt['original_name'] or ''
            original = original.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            f.write(f'  <wpt lat="{wpt["lat"]:.9f}" lon="{wpt["lon"]:.9f}">\n')
            f.write(f'    <name>{name}</name>\n')
            if original:
                f.write(f'    <desc>{original}</desc>\n')
            f.write(f'    <sym>{wpt["sym"]}</sym>\n')
            f.write('  </wpt>\n')

        f.write(gpx_footer)

def main():
    base_dir = Path(__file__).parent.parent
    gpx_dir = base_dir / 'gpx'
    result_dir = base_dir / 'result'
    result_dir.mkdir(exist_ok=True)

    # Define source files with their types
    # West (서해): 충남(어초) + 충청(다른사람) + my_own 중 서해
    # East (동해): 강원(어초) + my_own 중 동해

    west_reef_files = [
        gpx_dir / 'chungnam_points.gpx',
    ]

    west_other_files = [
        gpx_dir / 'new_points_chungcheong.gpx',
    ]

    east_reef_files = [
        gpx_dir / 'gangwon_points.gpx',
    ]

    my_own_file = gpx_dir / 'my_own_points.gpx'

    # Collect waypoints
    west_points = []
    east_points = []

    # Parse west reef files
    for f in west_reef_files:
        if f.exists():
            points = parse_waypoints(f, source_type='reef')
            west_points.extend(points)
            print(f"West reef - {f.name}: {len(points)} points")

    # Parse west other files
    for f in west_other_files:
        if f.exists():
            points = parse_waypoints(f, source_type='other')
            west_points.extend(points)
            print(f"West other - {f.name}: {len(points)} points")

    # Parse east reef files
    for f in east_reef_files:
        if f.exists():
            points = parse_waypoints(f, source_type='reef')
            east_points.extend(points)
            print(f"East reef - {f.name}: {len(points)} points")

    # Parse my_own_points and classify by longitude
    if my_own_file.exists():
        my_points = parse_waypoints(my_own_file, source_type='own')
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

    # Generate short names
    west_unique = generate_short_names(west_unique)
    east_unique = generate_short_names(east_unique)

    # Print naming summary
    print(f"\nNaming summary (West):")
    west_prefixes = {}
    for wpt in west_unique:
        prefix = wpt['short_name'].rsplit('_', 1)[0]
        west_prefixes[prefix] = west_prefixes.get(prefix, 0) + 1
    for prefix, count in sorted(west_prefixes.items(), key=lambda x: -x[1])[:10]:
        print(f"  {prefix}: {count}")

    print(f"\nNaming summary (East):")
    east_prefixes = {}
    for wpt in east_unique:
        prefix = wpt['short_name'].rsplit('_', 1)[0]
        east_prefixes[prefix] = east_prefixes.get(prefix, 0) + 1
    for prefix, count in sorted(east_prefixes.items(), key=lambda x: -x[1])[:10]:
        print(f"  {prefix}: {count}")

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
