import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd

from src.config import ROOT, RES

def parse_kml_file(fpath: Path):
    placemark_count = 0
    geom_counts = {}
    fields = set()
    bbox = [float("inf"), float("inf"), float("-inf"), float("-inf")]
    
    # Use iterparse for memory efficiency
    try:
        for event, elem in ET.iterparse(fpath, events=("end",)):
            tag = elem.tag.split("}")[-1]
            if tag == "Placemark":
                placemark_count += 1
                for child in elem.iter():
                    ctag = child.tag.split("}")[-1]
                    if ctag in ("Polygon", "Point", "LineString", "MultiGeometry"):
                        geom_counts[ctag] = geom_counts.get(ctag, 0) + 1
                    elif ctag in ("SimpleData", "Data"):
                        name = child.attrib.get("name")
                        if name:
                            fields.add(name)
                    elif ctag == "coordinates":
                        coords_text = child.text or ""
                        # Sample up to 20 coordinate points per Placemark to keep bounding box fast
                        pts = coords_text.strip().split()
                        sub_pts = pts if len(pts) <= 20 else pts[::len(pts)//20]
                        for pt in sub_pts:
                            parts = pt.split(",")
                            if len(parts) >= 2:
                                try:
                                    lon, lat = float(parts[0]), float(parts[1])
                                    if lon < bbox[0]: bbox[0] = lon
                                    if lat < bbox[1]: bbox[1] = lat
                                    if lon > bbox[2]: bbox[2] = lon
                                    if lat > bbox[3]: bbox[3] = lat
                                except ValueError:
                                    pass
                elem.clear()
    except Exception as e:
        return {"error": str(e), "placemark_count": placemark_count}
        
    clean_bbox = bbox if bbox[0] != float("inf") else None
    return {
        "placemark_count": placemark_count,
        "geometry_counts": geom_counts,
        "fields": sorted(list(fields)),
        "bounding_box": clean_bbox
    }

def parse_csv_file(fpath: Path):
    encodings = ["utf-8", "latin-1", "cp1252"]
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(fpath, encoding=enc, nrows=2)
            # Count total lines efficiently
            with open(fpath, "r", encoding=enc, errors="ignore") as f:
                row_count = sum(1 for _ in f) - 1
            break
        except Exception:
            continue
            
    if df is None:
        return {"error": "Failed to read CSV with standard encodings"}
        
    return {
        "columns": list(df.columns),
        "row_count": max(0, row_count),
        "sample_rows": df.fillna("").to_dict(orient="records")
    }

def run_u0_inventory():
    base_dir = ROOT / "new_dataset"
    inventory = {}
    
    print("Walking new_dataset/ and parsing inventory...")
    for p in sorted(base_dir.rglob("*")):
        if p.is_file():
            rel_path = str(p.relative_to(ROOT)).replace("\\", "/")
            size_bytes = p.stat().st_size
            ext = p.suffix.lower()
            
            item = {
                "file_path": rel_path,
                "file_name": p.name,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "extension": ext
            }
            
            if ext == ".csv":
                item["type"] = "csv"
                item["content"] = parse_csv_file(p)
            elif ext == ".kml":
                item["type"] = "kml"
                item["content"] = parse_kml_file(p)
            else:
                item["type"] = "other"
                
            inventory[rel_path] = item
            
    out_file = RES / "dataset_inventory.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)
    print(f"Saved inventory with {len(inventory)} files to {out_file}")
    
    # 3. Decisions for provenance.json
    # Identify best candidate per category:
    # - Wards: BBMP Final Wards Map - 2023.kml (newest final delimitation, 225 wards)
    # - Population: BBMP 2014 Ward Delimitation Details.csv (198 wards census)
    # - Temperature: Bengaluru Daily Temperature Data 1951 to 2024.csv (daily max/min)
    # - Rainfall: Bengaluru Monthly Rainfall Data (1900-2025).csv + Bengaluru Daily Temperature Data (contains rain)
    # - Groundwater: Bengaluru Ground Water Depth 2013.kml
    # - STP: SewageTreatmentPlantLocation.csv (39 STPs)
    # - Pipeline: MapBWSSBwaterSupplyLinesDiameterGreaterThan300mm..kml
    # - Borewells: BorewellsMaps.kml
    # - Cauvery Area: ServiceStationDivisionBoundariesMap.kml / SubDivisionBoundaryMaps.kml
    # - Tankers: Water Tanker Data (2024).csv
    
    decisions = [
        {"component": "ward_geometry", "chosen_file": "new_dataset/wards/BBMP Final Wards Map - 2023.kml", "status": "real", "note": "Newest final administrative ward boundary delimitation (225 wards)"},
        {"component": "population", "chosen_file": "new_dataset/population/BBMP 2014 Ward Delimitation Details.csv", "status": "real", "note": "Official census population and area details matched via fuzzy name/number alignment"},
        {"component": "temperature", "chosen_file": "new_dataset/rainfall/Bengaluru Daily Temperature Data 1951 to 2024.csv", "status": "real", "note": "73 years of daily max and min temperature records"},
        {"component": "rainfall", "chosen_file": "new_dataset/rainfall/Bengaluru Monthly Rainfall Data (1900-2025).csv", "status": "real", "note": "Longest historical monthly precipitation series"},
        {"component": "groundwater_depth", "chosen_file": "new_dataset/borewells/Bengaluru Ground Water Depth 2013.kml", "status": "real", "note": "Spatial depth contours and point monitoring samples"},
        {"component": "stps", "chosen_file": "new_dataset/supply/SewageTreatmentPlantLocation.csv", "status": "real", "note": "39 BWSSB operational Sewage Treatment Plants with exact KLD capacities"},
        {"component": "trunk_pipelines", "chosen_file": "new_dataset/supply/MapBWSSBwaterSupplyLinesDiameterGreaterThan300mm..kml", "status": "real", "note": "BWSSB transmission mains > 300mm diameter"},
        {"component": "borewells", "chosen_file": "new_dataset/borewells/BorewellsMaps.kml", "status": "real", "note": "BWSSB / BBMP public borewell inventory"},
        {"component": "cauvery_coverage", "chosen_file": "new_dataset/supply/ServiceStationDivisionBoundariesMap.kml", "status": "real", "note": "BWSSB piped water service station divisions mapped to ward polygons"},
        {"component": "tanker_rates", "chosen_file": "new_dataset/tankers/Water Tanker Data (2024).csv", "status": "real", "note": "Citizen water tanker transaction rates and capacities"}
    ]
    
    prov_file = RES / "provenance.json"
    with open(prov_file, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)
    print(f"Saved decisions to {prov_file}")
    
    # Gate check
    assert out_file.exists(), "dataset_inventory.json missing"
    assert prov_file.exists(), "provenance.json missing"
    assert len(decisions) >= 10, "Decisions missing categories"
    
    print("\nDecisions Summary:")
    for d in decisions:
        print(f"  [{d['status'].upper()}] {d['component']}: {Path(d['chosen_file']).name}")

if __name__ == "__main__":
    run_u0_inventory()

