# Google Drive API Setup Guide

## Overview
This guide walks through setting up Google Drive API access for automated model training workflow.

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name: `deer-deterrent-ml`
4. Click "Create"

## Step 2: Enable Google Drive API

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click "Enable"

## Step 3: Create Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Name: `deer-deterrent-training`
4. Description: `Automated ML training data sync`
5. Click "Create and Continue"
6. Skip role assignment (optional)
7. Click "Done"

## Step 4: Create Service Account Key

1. Click on the newly created service account
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose "JSON" format
5. Click "Create"
6. **Save the downloaded JSON file** - you'll need this!

## Step 5: Share Google Drive Folder

1. Go to your Google Drive
2. Navigate to "Deer video detection" folder
3. Right-click → "Share"
4. Add the service account email (looks like: `deer-deterrent-training@deer-deterrent-ml.iam.gserviceaccount.com`)
5. Give "Editor" permissions
6. Click "Share"

## Step 6: Configure Local Environment

1. Copy the service account JSON file to your project:
   ```bash
   cp ~/Downloads/deer-deterrent-ml-*.json ./configs/google-credentials.json
   ```

2. Add to `.env` file:
   ```bash
   GOOGLE_DRIVE_CREDENTIALS_PATH=./configs/google-credentials.json
   GOOGLE_DRIVE_TRAINING_FOLDER_ID=<folder-id>
   ```

3. Get folder ID from Google Drive:
   - Open "Deer video detection" folder
   - Copy ID from URL: `https://drive.google.com/drive/folders/[THIS-IS-THE-ID]`

## Step 7: Install Python Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Step 8: Test Connection

Run the test script:
```bash
python scripts/test_drive_connection.py
```

You should see:
```
✓ Successfully connected to Google Drive
✓ Found folder: Deer video detection
✓ Ready to sync training data
```

## Folder Structure in Google Drive

The automation will maintain this structure:

```
Deer video detection/
├── videos/
│   └── annotations/
│       ├── images/          # Original training images
│       └── result.json      # COCO annotations
├── training_data/           # Auto-synced from production
│   ├── v1_2024_11_15/      # Versioned datasets
│   │   ├── images/
│   │   ├── labels/
│   │   └── dataset.yaml
│   └── v2_2024_11_22/
│       ├── images/
│       ├── labels/
│       └── dataset.yaml
└── trained_models/          # Output from Colab
    ├── v1_best.pt
    └── v2_best.pt
```

## Security Notes

- ⚠️ Never commit `google-credentials.json` to git (already in `.gitignore`)
- ⚠️ Keep service account key secure
- ✓ Service account has minimal permissions (only Drive access)
- ✓ Can revoke access anytime from Google Drive

## Troubleshooting

### Error: "Insufficient permissions"
- Make sure you shared the Drive folder with the service account email
- Give "Editor" (not just "Viewer") permissions

### Error: "API not enabled"
- Go to Cloud Console → APIs & Services → Library
- Search for "Google Drive API" and enable it

### Error: "Invalid credentials"
- Check that the JSON file path in `.env` is correct
- Verify the JSON file is valid (should start with `{"type": "service_account"...`)

## Next Steps

Once setup is complete:
1. Run detection review UI to start labeling data
2. Automated sync will upload to Drive
3. Trigger Colab training
4. Download and deploy new model

See `ML_REFINEMENT_STRATEGY.md` for full workflow details.
