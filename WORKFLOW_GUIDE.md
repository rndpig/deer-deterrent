# Model Improvement Workflow Guide

## Overview

The Model Improvement tab provides a complete workflow for collecting training data from Ring camera footage and preparing it for YOLOv8 model retraining.

## How It Works

### 1. Video Upload & Frame Extraction

When you upload a video:
- The system extracts **every Nth frame** based on your sampling rate
- Each extracted frame is saved to disk (`data/frames/`)
- The YOLOv8 model runs detection on each frame
- Detection results are added to the **review queue**

**Frames remain in the review queue until you take action** (review, annotate, or delete them).

### 2. Frame Sampling Rates

Choose based on your needs:
- **High Detail (every 10th frame)**: ~3 frames/sec - Use for fast-moving deer or complex scenes
- **Balanced (every 15th frame)**: ~2 frames/sec - **Recommended** for most cases
- **Quick Review (every 30th frame)**: ~1 frame/sec - For static scenes or quick scanning
- **Sparse (every 60th frame)**: ~0.5 frame/sec - Very selective sampling

**Example**: A 30-second video at 30fps has 900 frames
- With "Balanced" (15): You review ~60 frames
- With "Quick" (30): You review ~30 frames

### 3. Frame Persistence

**Important**: Once frames are extracted, they stay in the review queue until you explicitly:
- ✅ Mark them as reviewed (Correct/False Positive/Wrong Count)
- 📦 Draw bounding boxes (for missed detections)
- 🗑️ Delete them (individually or in bulk)

**You do NOT need to upload the same video again** - all frames from your first upload are already there waiting for review.

### 4. Review Process

For each frame:
1. **Review the detection**: 
   - Correct ✓ - Model detected correctly
   - False Positive ✗ - No deer present but model detected one
   - Wrong Count # - Deer present but count is wrong

2. **Annotate missed detections**:
   - If deer are visible but not detected, click "Draw Bounding Boxes"
   - Click and drag to create boxes around each deer
   - These manual annotations improve the model's training

3. **Delete redundant frames**:
   - If frames are too similar or not useful, delete them
   - Keeps your training dataset high-quality

### 5. Filters

- **Unreviewed**: Frames that need your attention (new uploads, unannotated)
- **All**: Everything in the queue
- **Reviewed**: Frames you've already processed

### 6. Bulk Actions

- **Clear Unreviewed/Reviewed/All**: Delete multiple frames at once
  - Useful for clearing out false positives or redundant frames
  - Makes room for better training examples

### 7. Export & Training

Once you have 50+ reviewed detections:
1. Click "Export & Sync to Drive"
2. System creates COCO-format dataset with your annotations
3. Uploads to Google Drive training folder
4. Ready for Colab notebook to download and retrain YOLOv8

## Common Workflows

### Scenario A: Video with Missed Detections
1. Upload video with "Balanced" sampling
2. Navigate through frames (arrow keys)
3. For frames where deer are visible but not detected:
   - Click "Draw Bounding Boxes"
   - Draw boxes around each deer
   - Save
4. Continue reviewing all frames
5. Export when ready

### Scenario B: Cleaning Up False Positives
1. Filter by "All" to see everything
2. Navigate through frames
3. Mark false positives (no deer but detection triggered)
4. Delete truly bad frames
5. Keep good examples for training

### Scenario C: Multiple Videos Over Time
1. Upload Video 1 → Review some frames
2. Upload Video 2 → More frames added to queue
3. Filter "Unreviewed" to see what still needs attention
4. Review at your own pace
5. All frames accumulate until you delete them

## Why This Approach?

**Persistent Queue**: Frames stay until you act on them
- You can review in multiple sessions
- No need to re-upload videos
- Build up a dataset over days/weeks

**Frame Sampling**: Avoid redundancy
- 30-sec video has 900 frames (too many similar ones)
- Sampling gives you diverse examples without overwhelming review
- You still capture important moments

**Manual Annotations**: Fill detection gaps
- Model learns from what it missed
- You become the teacher showing the model where deer actually are

## Tips

1. **Start with Balanced sampling** - Good tradeoff between coverage and review time
2. **Delete similar frames** - Keep your dataset diverse
3. **Annotate missed detections** - Most valuable for improving the model
4. **Review in batches** - Use keyboard shortcuts (←→ 1 2 3) for speed
5. **Export regularly** - Get improved models sooner

## Keyboard Shortcuts

- **←** / **→**: Navigate frames
- **1**: Mark Correct
- **2**: Mark False Positive  
- **3**: Enter Wrong Count
