"""Quick script to analyze the introspection results"""
import json

with open('pto_introspection_result.json', 'r') as f:
    data = json.load(f)

types = data['data']['__schema']['types']

# Find BetMarketListingType
listing_type = next((t for t in types if t.get('name') == 'BetMarketListingType'), None)
if listing_type:
    print("=== BetMarketListingType fields ===")
    for field in listing_type.get('fields', [])[:30]:
        field_type = field['type']
        type_name = field_type.get('name')
        if not type_name and field_type.get('ofType'):
            type_name = field_type['ofType'].get('name')
        print(f"  - {field['name']}: {type_name}")

# Find BetMarketTypeEnumTypeTwo
enum_type = next((t for t in types if t.get('name') == 'BetMarketTypeEnumTypeTwo'), None)
if enum_type:
    print("\n=== BetMarketTypeEnumTypeTwo values (ALL) ===")
    all_values = enum_type.get('enumValues', [])
    print(f"Total: {len(all_values)} values")
    # Look for mainlines
    mainline_keywords = ['MONEYLINE', 'SPREAD', 'TOTAL', 'OVER', 'UNDER', 'TEAM', 'GAME']
    mainlines = [v for v in all_values if any(kw in v['name'] for kw in mainline_keywords)]
    if mainlines:
        print("\nMainline-related values:")
        for val in mainlines:
            print(f"  - {val['name']}")
    # Print first 20 and last 20
    print("\nFirst 20 values:")
    for val in all_values[:20]:
        print(f"  - {val['name']}")
    print("\n... (showing all would be too many) ...")
    print("\nLast 20 values:")
    for val in all_values[-20:]:
        print(f"  - {val['name']}")

# Find BetMarketConditionType
condition_type = next((t for t in types if t.get('name') == 'BetMarketConditionType'), None)
if condition_type:
    print("\n=== BetMarketConditionType fields ===")
    for field in condition_type.get('fields', [])[:30]:
        field_type = field['type']
        type_name = field_type.get('name')
        if not type_name and field_type.get('ofType'):
            type_name = field_type['ofType'].get('name')
        print(f"  - {field['name']}: {type_name}")

