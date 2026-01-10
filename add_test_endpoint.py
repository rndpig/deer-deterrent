"""Add test-irrigation endpoint to coordinator service"""
import sys

# Read the coordinator service file
with open(sys.argv[1], 'r') as f:
    lines = f.readlines()

# Find where to insert (after the stats endpoint, before if __name__)
insert_index = None
for i, line in enumerate(lines):
    if 'if __name__ == "__main__"' in line:
        insert_index = i
        break

if insert_index is None:
    print("Could not find insertion point")
    sys.exit(1)

# New endpoint code
new_endpoint = '''
@app.post("/test-irrigation")
async def test_irrigation(request: dict):
    """Manually test irrigation system"""
    try:
        zone = request.get("zone", CONFIG.get("RAINBIRD_ZONE", "1"))
        duration = request.get("duration", 10)  # Short test duration
        
        logger.info(f"Manual irrigation test: Zone {zone} for {duration}s")
        
        success = await activate_rainbird(zone, duration)
        
        if success:
            return {
                "status": "success",
                "message": f"Irrigation activated: Zone {zone} for {duration} seconds",
                "zone": zone,
                "duration": duration
            }
        else:
            return {
                "status": "failed",
                "message": "Failed to activate irrigation (check Rainbird connection)",
                "zone": zone,
                "duration": duration
            }
    except Exception as e:
        logger.error(f"Test irrigation error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

'''

# Insert the new endpoint
lines.insert(insert_index, new_endpoint)

# Write back
with open(sys.argv[1], 'w') as f:
    f.writelines(lines)

print("Successfully added test-irrigation endpoint")
