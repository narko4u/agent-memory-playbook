#!/usr/bin/env python3
"""Generate og-cover.png (1200x630) for agent-memory-playbook - dark layered memory stack."""
from PIL import Image, ImageDraw

W, H = 1200, 630
img = Image.new("RGB", (W, H), "#0b1020")
d = ImageDraw.Draw(img)

# subtle vertical gradient
for y in range(H):
    t = y / H
    r = int(11 + 6 * t)
    g = int(16 + 10 * t)
    b = int(32 + 18 * t)
    d.line([(0, y), (W, y)], fill=(r, g, b))

# faint grid
for x in range(0, W, 40):
    d.line([(x, 0), (x, H)], fill=(30, 42, 72), width=1)
for y in range(0, H, 40):
    d.line([(0, y), (W, y)], fill=(30, 42, 72), width=1)

# layered memory stack: 4 horizontal slabs (hot memory / state files / session search / verify)
slabs = [
    (0.14, "#3b82f6", "HOT MEMORY"),
    (0.34, "#8b5cf6", "STATE FILES"),
    (0.54, "#06b6d4", "SESSION SEARCH"),
    (0.74, "#10b981", "VERIFY BEFORE ASSERT"),
]
for fy, color, label in slabs:
    x0, y0 = 220, int(H * fy)
    x1, y1 = 620, y0 + 58
    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=color, outline=None)
    # node dots
    for i in range(7):
        cx = x0 + 24 + i * 58
        cy = y0 + 29
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill="#0b1020")

# central connector line
d.line([(620, int(H * 0.14) + 29), (620, int(H * 0.74) + 29)], fill="#334155", width=3)

# title text (simple, no font dependency beyond default)
d.text((220, 110), "Twelve Agents, One Memory", fill="#e2e8f0")
d.text((220, 560), "Persistent Recall for an Autonomous Agent Fleet", fill="#94a3b8")

img.save("/mnt/c/VaultSentinel/HermesGenesis/content/agent-memory-playbook/og-cover.png")
print("cover written")
