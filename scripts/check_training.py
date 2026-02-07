#!/usr/bin/env python3
"""Quick script to check training results on server."""
import csv
import sys

csv_path = "/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_phase2/results.csv"
with open(csv_path) as f:
    rows = list(csv.reader(f))

header = rows[0]
data = rows[1:]
print(f"Total epochs completed: {len(data)}")
print()

# Sort by mAP50 (column index 7)
data.sort(key=lambda r: float(r[7].strip()), reverse=True)
print("Top 5 epochs by mAP50:")
for r in data[:5]:
    epoch = r[0].strip()
    p = float(r[5].strip())
    recall = float(r[6].strip())
    map50 = float(r[7].strip())
    map50_95 = float(r[8].strip())
    print(f"  Epoch {epoch:>3s}: P={p:.3f}  R={recall:.3f}  mAP50={map50:.3f}  mAP50-95={map50_95:.3f}")

print()
# Last 10 epochs
print("Last 10 epochs:")
data_by_epoch = sorted(rows[1:], key=lambda r: int(r[0].strip()))
for r in data_by_epoch[-10:]:
    epoch = r[0].strip()
    p = float(r[5].strip())
    recall = float(r[6].strip())
    map50 = float(r[7].strip())
    map50_95 = float(r[8].strip())
    box_loss = float(r[2].strip())
    cls_loss = float(r[3].strip())
    print(f"  Epoch {epoch:>3s}: P={p:.3f}  R={recall:.3f}  mAP50={map50:.3f}  mAP50-95={map50_95:.3f}  box_loss={box_loss:.3f}  cls_loss={cls_loss:.3f}")

# Best epoch info
best = data[0]
print(f"\nBest epoch: {best[0].strip()} with mAP50={float(best[7].strip()):.3f}")
