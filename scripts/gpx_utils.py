#!/usr/bin/env python3
"""
GPX 파일 관리 유틸리티
- GPX -> CSV/JSON 변환
- 중복 포인트 검출
- 통계 출력
"""

import xml.etree.ElementTree as ET
import pandas as pd
import json
import os
import sys
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from datetime import datetime

GPX_NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}


def haversine_distance(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 거리 계산 (미터)"""
    R = 6371000  # 지구 반경 (미터)
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


def parse_gpx(gpx_path):
    """GPX 파일 파싱하여 waypoint 리스트 반환"""
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    
    waypoints = []
    for wpt in root.findall('.//gpx:wpt', GPX_NS):
        lat = float(wpt.get('lat'))
        lon = float(wpt.get('lon'))
        
        name_elem = wpt.find('gpx:name', GPX_NS) or wpt.find('gpx:n', GPX_NS)
        name = name_elem.text if name_elem is not None and name_elem.text else ''
        
        desc_elem = wpt.find('gpx:desc', GPX_NS)
        desc = desc_elem.text if desc_elem is not None and desc_elem.text else ''
        
        cmt_elem = wpt.find('gpx:cmt', GPX_NS)
        cmt = cmt_elem.text if cmt_elem is not None and cmt_elem.text else ''
        
        time_elem = wpt.find('gpx:time', GPX_NS)
        time = time_elem.text if time_elem is not None and time_elem.text else ''
        
        sym_elem = wpt.find('gpx:sym', GPX_NS)
        sym = sym_elem.text if sym_elem is not None and sym_elem.text else ''
        
        waypoints.append({
            'lat': lat,
            'lon': lon,
            'name': name,
            'description': desc,
            'comment': cmt,
            'time': time,
            'symbol': sym,
            'source_file': os.path.basename(gpx_path)
        })
    
    return waypoints


def find_duplicates(waypoints, distance_threshold=10):
    """
    중복 포인트 검출 (지정된 거리 이내)
    distance_threshold: 미터 단위
    """
    duplicates = []
    n = len(waypoints)
    
    for i in range(n):
        for j in range(i+1, n):
            dist = haversine_distance(
                waypoints[i]['lat'], waypoints[i]['lon'],
                waypoints[j]['lat'], waypoints[j]['lon']
            )
            if dist <= distance_threshold:
                duplicates.append({
                    'point1_idx': i,
                    'point1_name': waypoints[i]['name'] or waypoints[i]['description'],
                    'point1_source': waypoints[i]['source_file'],
                    'point1_lat': waypoints[i]['lat'],
                    'point1_lon': waypoints[i]['lon'],
                    'point2_idx': j,
                    'point2_name': waypoints[j]['name'] or waypoints[j]['description'],
                    'point2_source': waypoints[j]['source_file'],
                    'point2_lat': waypoints[j]['lat'],
                    'point2_lon': waypoints[j]['lon'],
                    'distance_m': round(dist, 2)
                })
    
    return duplicates


def export_to_csv(waypoints, output_path):
    """waypoint 리스트를 CSV로 내보내기"""
    df = pd.DataFrame(waypoints)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    return df


def export_to_json(waypoints, output_path):
    """waypoint 리스트를 JSON으로 내보내기"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(waypoints, f, ensure_ascii=False, indent=2)


def get_statistics(waypoints):
    """waypoint 통계 정보"""
    df = pd.DataFrame(waypoints)
    
    stats = {
        'total_points': len(waypoints),
        'by_source': df['source_file'].value_counts().to_dict(),
        'lat_range': {
            'min': df['lat'].min(),
            'max': df['lat'].max()
        },
        'lon_range': {
            'min': df['lon'].min(),
            'max': df['lon'].max()
        }
    }
    
    return stats


def process_all_gpx(gpx_dir, output_dir, check_duplicates=True, distance_threshold=50):
    """모든 GPX 파일 처리"""
    gpx_files = list(Path(gpx_dir).glob('*.gpx'))
    all_waypoints = []
    
    print(f"\n{'='*60}")
    print(f"GPX 파일 처리 시작")
    print(f"{'='*60}")
    
    for gpx_file in gpx_files:
        waypoints = parse_gpx(gpx_file)
        all_waypoints.extend(waypoints)
        print(f"  {gpx_file.name}: {len(waypoints)} 포인트")
    
    print(f"\n총 포인트 수: {len(all_waypoints)}")
    
    # 개별 파일별 CSV 내보내기
    for gpx_file in gpx_files:
        waypoints = parse_gpx(gpx_file)
        base_name = gpx_file.stem
        export_to_csv(waypoints, os.path.join(output_dir, f'{base_name}.csv'))
    
    # 전체 통합 파일
    export_to_csv(all_waypoints, os.path.join(output_dir, 'all_points.csv'))
    export_to_json(all_waypoints, os.path.join(output_dir, 'all_points.json'))
    
    print(f"\n내보내기 완료:")
    print(f"  - 개별 CSV: {output_dir}/*.csv")
    print(f"  - 통합 CSV: {output_dir}/all_points.csv")
    print(f"  - 통합 JSON: {output_dir}/all_points.json")
    
    # 중복 검사
    if check_duplicates:
        print(f"\n{'='*60}")
        print(f"중복 검사 (거리 임계값: {distance_threshold}m)")
        print(f"{'='*60}")
        
        duplicates = find_duplicates(all_waypoints, distance_threshold)
        
        if duplicates:
            print(f"\n발견된 중복: {len(duplicates)}건")
            dup_df = pd.DataFrame(duplicates)
            dup_path = os.path.join(output_dir, 'duplicates.csv')
            dup_df.to_csv(dup_path, index=False, encoding='utf-8-sig')
            print(f"중복 목록 저장: {dup_path}")
            
            # 상위 10개만 출력
            print(f"\n상위 10개 중복:")
            for i, dup in enumerate(duplicates[:10]):
                print(f"  {i+1}. [{dup['point1_source']}] {dup['point1_name'][:20]}...")
                print(f"     [{dup['point2_source']}] {dup['point2_name'][:20]}...")
                print(f"     거리: {dup['distance_m']}m")
        else:
            print("중복 없음")
    
    # 통계
    stats = get_statistics(all_waypoints)
    print(f"\n{'='*60}")
    print("통계")
    print(f"{'='*60}")
    print(f"총 포인트: {stats['total_points']}")
    print(f"\n파일별 포인트 수:")
    for src, cnt in stats['by_source'].items():
        print(f"  {src}: {cnt}")
    print(f"\n좌표 범위:")
    print(f"  위도: {stats['lat_range']['min']:.6f} ~ {stats['lat_range']['max']:.6f}")
    print(f"  경도: {stats['lon_range']['min']:.6f} ~ {stats['lon_range']['max']:.6f}")
    
    return all_waypoints, stats


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='GPX 파일 관리 유틸리티')
    parser.add_argument('--gpx-dir', default='../gpx', help='GPX 파일 디렉토리')
    parser.add_argument('--output-dir', default='../data', help='출력 디렉토리')
    parser.add_argument('--distance', type=int, default=10, help='중복 검사 거리 임계값 (미터)')
    parser.add_argument('--no-duplicates', action='store_true', help='중복 검사 건너뛰기')
    
    args = parser.parse_args()
    
    process_all_gpx(
        args.gpx_dir, 
        args.output_dir, 
        check_duplicates=not args.no_duplicates,
        distance_threshold=args.distance
    )
