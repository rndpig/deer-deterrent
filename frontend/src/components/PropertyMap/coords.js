export const clamp01 = (v) => Math.max(0, Math.min(1, v));

export const snap = (v) => Math.round(v / 0.005) * 0.005;

export const pixelToNormalized = (px, py, rect) => ({
  x: snap(clamp01((px - rect.left) / rect.width)),
  y: snap(clamp01((py - rect.top) / rect.height)),
});

export const normalizedToPercent = (n) => `${(n * 100).toFixed(2)}%`;
