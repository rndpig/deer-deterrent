# Repository Cleanup Plan

## Current Status Analysis

### ✅ Active/Production Files (KEEP)
**Dell Server Deployment** (Current production system):
- `docker-compose.dell.yml` - Production compose file
- `Dockerfile.coordinator` - Coordinator service
- `Dockerfile.ml-detector` - ML detection service
- `.env.example` - Environment template
- `DELL_README.md` - Main Dell documentation
- `QUICKSTART_DELL.md` - Quick start guide
- `DELL_DEPLOYMENT.md` - Comprehensive deployment guide
- `DELL_CHECKLIST.md` - Deployment checklist

**Core Application Code**:
- `backend/` - Backend API service
- `frontend/` - React dashboard
- `configs/` - Configuration files (zones.yaml, training_config.yaml)
- `models/deer_detector_best.pt` - Trained ML model
- `notebooks/train_deer_detector_colab.ipynb` - Training notebook

**Utility Scripts**:
- `scripts/demo_system.py` - System testing
- `scripts/setup_ring_auth.py` - Ring authentication
- `scripts/discover_rainbird_api.py` - Rainbird discovery
- `manage.sh` - Management utilities

**Project Files**:
- `README.md` - Main project readme (needs updating)
- `.gitignore` - Git ignore rules
- `requirements.txt` - Python dependencies

---

### ⚠️ Deprecated Files (DELETE)

**Obsolete Deployment Guides**:
- ❌ `QNAP_DEPLOYMENT.md` - QNAP NAS deployment (not used)
- ❌ `QNAP_SETUP_DETAILED.md` - Detailed QNAP setup (not used)
- ❌ `RPI_DEPLOYMENT.md` - Raspberry Pi deployment (not used)
- ❌ `VERCEL_DEPLOY.md` - Vercel cloud deployment (not used)
- ❌ `DEPLOYMENT.md` - Generic/old deployment guide
- ❌ `DEPLOYMENT_CHECKLIST.md` - Old checklist
- ❌ `GETTING_STARTED.md` - Outdated getting started
- ❌ `QUICKSTART.md` - Old quickstart (superseded by QUICKSTART_DELL.md)

**Redundant Dell Documentation**:
- ❌ `DELL_INDEX.md` - Redundant index page
- ❌ `DELL_REFERENCE.md` - Reference material (can be consolidated)
- ❌ `DELL_SUMMARY.md` - Summary (redundant with README)

**Session/Temp Files**:
- ❌ `SESSION_STATUS.md` - Temporary session tracking
- ❌ `dell-update-coordinator.sh` - One-time update script

**Obsolete Compose Files**:
- ❌ `docker-compose.yml` - Old/generic compose file (replaced by docker-compose.dell.yml)

**Unused Source Directories**:
- ❌ `src/` - Old monolithic source structure (replaced by containerized services)

---

## Proposed New Structure

```
deer-deterrent/
├── README.md                          # Updated main readme
├── QUICKSTART.md                      # Renamed from QUICKSTART_DELL.md
├── DEPLOYMENT.md                      # Renamed from DELL_DEPLOYMENT.md
├── CHECKLIST.md                       # Renamed from DELL_CHECKLIST.md
├── .env.example                       # Environment template
├── .gitignore                         # Git ignore
├── requirements.txt                   # Python dependencies
│
├── docker-compose.yml                 # Renamed from docker-compose.dell.yml
├── Dockerfile.coordinator             # Coordinator service
├── Dockerfile.ml-detector             # ML detector service
│
├── backend/                           # Backend API
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── frontend/                          # React dashboard
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│
├── configs/                           # Configuration
│   ├── training_config.yaml
│   └── zones.yaml
│
├── models/                            # ML models
│   └── deer_detector_best.pt
│
├── notebooks/                         # Jupyter notebooks
│   └── train_deer_detector_colab.ipynb
│
├── scripts/                           # Utility scripts
│   ├── demo_system.py
│   ├── setup_ring_auth.py
│   └── discover_rainbird_api.py
│
├── docs/                              # Additional documentation
│   ├── ARCHITECTURE.md               # System architecture
│   ├── API.md                        # API documentation
│   ├── TROUBLESHOOTING.md            # Common issues
│   └── CONTRIBUTING.md               # Contribution guidelines
│
└── tests/                             # Tests (future)
```

---

## Cleanup Actions

### Phase 1: Delete Obsolete Files
```bash
# Deployment guides for unused platforms
rm QNAP_DEPLOYMENT.md
rm QNAP_SETUP_DETAILED.md
rm RPI_DEPLOYMENT.md
rm VERCEL_DEPLOY.md
rm DEPLOYMENT.md
rm DEPLOYMENT_CHECKLIST.md
rm GETTING_STARTED.md
rm QUICKSTART.md

# Redundant Dell docs
rm DELL_INDEX.md
rm DELL_REFERENCE.md
rm DELL_SUMMARY.md

# Temp/session files
rm SESSION_STATUS.md
rm dell-update-coordinator.sh

# Old compose file
rm docker-compose.yml

# Unused source directory (if no longer needed)
rm -rf src/  # VERIFY FIRST - check if any scripts reference this
```

### Phase 2: Rename Dell-Specific Files
```bash
# Remove "DELL" prefix since it's now the only deployment method
mv docker-compose.dell.yml docker-compose.yml
mv DELL_README.md README_OLD.md  # Backup
mv QUICKSTART_DELL.md QUICKSTART.md
mv DELL_DEPLOYMENT.md DEPLOYMENT.md
mv DELL_CHECKLIST.md CHECKLIST.md
```

### Phase 3: Update README.md
- Remove references to QNAP, RPi, Vercel deployments
- Simplify to focus on Docker Compose deployment
- Update file structure documentation
- Add link to QUICKSTART.md for beginners

### Phase 4: Create docs/ Directory
```bash
mkdir docs/
# Move any architecture/troubleshooting content from old files
```

---

## Files Requiring Content Updates

### README.md
- Remove "Deployment Options" section listing QNAP/RPi/Cloud
- Simplify to single Docker Compose deployment
- Update project structure diagram
- Link to QUICKSTART.md and DEPLOYMENT.md

### QUICKSTART.md (from QUICKSTART_DELL.md)
- Remove "Dell" references (it's just "the" deployment now)
- Update docker-compose file name references

### DEPLOYMENT.md (from DELL_DEPLOYMENT.md)
- Remove "Dell" references
- Update docker-compose file name references
- Consolidate any useful content from DELL_REFERENCE.md

### .gitignore
- Ensure temporary files are ignored
- Add common development artifacts

---

## Validation Checklist

Before finalizing cleanup:
- [ ] Verify no scripts reference deleted files
- [ ] Update all docker-compose command references
- [ ] Test deployment with renamed files
- [ ] Ensure all links in documentation work
- [ ] Verify .env.example is complete
- [ ] Check that manage.sh still works
- [ ] Confirm frontend/backend build successfully

---

## Post-Cleanup Benefits

1. **Clearer Structure** - Single deployment path, no confusion
2. **Easier Maintenance** - Fewer files to update
3. **Better Onboarding** - New developers/users see only relevant docs
4. **Reduced Clutter** - Repository focuses on production system
5. **Simplified CI/CD** - Single docker-compose file to test

---

## Rollback Plan

If issues arise:
1. All deletions committed separately for easy revert
2. Renamed files backed up with `_OLD` suffix
3. Git history preserves everything
4. Can cherry-pick individual file restorations

