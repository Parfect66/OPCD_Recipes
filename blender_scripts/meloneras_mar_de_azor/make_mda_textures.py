"""Make the Mar de Azor PBR sets on the PC with Blender's own Python (numpy + bpy, no Pillow).

    blender.exe -b --factory-startup --python make_mda_textures.py -- <out Textures dir> <clubhouse Textures dir>

Downloads CC0 sets from Poly Haven (2k PNG), derives the tinted variants, and writes per set:
    <SET>_ALBEDO / NORMAL (OpenGL) / METALNESS / AO / DISPLACEMENT / ROUGHNESS (white = rough) .png
    <SET>_MAHS.png (R = Metalness, G = AO, B = Displacement, A = Roughness)
All 2048 x 2048. The clubhouse folder must hold MEL_CH_Render and Meloneras_Concrete.
Sets: MDA_RenderWhite, MDA_RenderCream, MDA_FlatRoof (from the clubhouse sets),
MDA_RenderRed (red_plaster_weathered), MDA_Blockwork (concrete_block_wall),
MDA_CorrugatedRed / Green / White (corrugated_iron_02, painted: metalness 0).
"""
import json
import os
import sys
import tempfile
import urllib.request

import bpy
import numpy as np

N = 2048
UA = {"User-Agent": "opcd-texture-fetch"}
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else r"H:\Meloneras\Support_Files\Buildings\MarDeAzor\Textures"
CLUB = argv[1] if len(argv) > 1 else r"H:\Meloneras\Meloneras_Golf_Club_v4_2025_12_02\Assets\Buildings\Meloneras Clubhouse\Latest\Textures"
TMP = tempfile.mkdtemp(prefix="mda_tex_")


def load(path):
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = "Non-Color"   # raw stored values, no conversion
    if tuple(im.size) != (N, N):
        im.scale(N, N)
    a = np.empty(N * N * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(N, N, 4)


def save(arr, path, alpha=False):
    arr = np.clip(arr, 0, 1).astype(np.float32)
    if arr.ndim == 2:
        arr = np.dstack([arr, arr, arr])
    if arr.shape[2] == 3:
        arr = np.dstack([arr, np.ones((N, N), np.float32)])
    im = bpy.data.images.new("tmp", N, N, alpha=alpha)
    im.colorspace_settings.name = "Non-Color"
    im.pixels.foreach_set(arr.ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def get(url, dest):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def polyhaven(aid):
    files = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"https://api.polyhaven.com/files/{aid}", headers=UA), timeout=60).read())
    want = {"ALBEDO": "Diffuse", "NORMAL": "nor_gl", "ROUGHNESS": "Rough", "AO": "AO",
            "DISPLACEMENT": "Displacement", "METALNESS": "Metal"}
    out = {}
    for k, v in want.items():
        if v in files:
            out[k] = load(get(files[v]["2k"]["png"]["url"], os.path.join(TMP, f"{aid}_{k}.png")))
    return out


def set_from_folder(folder, name):
    base = os.path.join(CLUB, name, name + "_")
    return {k: load(base + k + ".png") for k in ("ALBEDO", "NORMAL", "ROUGHNESS", "AO", "DISPLACEMENT", "METALNESS")}


def grey(a):
    return a[..., :3].mean(axis=2)


def write_set(name, m, albedo=None, metal=None, rough=None):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    alb = albedo if albedo is not None else m["ALBEDO"][..., :3]
    met = metal if metal is not None else (grey(m["METALNESS"]) if "METALNESS" in m else np.zeros((N, N), np.float32))
    rgh = rough if rough is not None else grey(m["ROUGHNESS"])
    ao = grey(m["AO"]) if "AO" in m else np.ones((N, N), np.float32)
    disp = grey(m["DISPLACEMENT"]) if "DISPLACEMENT" in m else np.full((N, N), 0.5, np.float32)
    save(alb, os.path.join(d, f"{name}_ALBEDO.png"))
    save(m["NORMAL"][..., :3], os.path.join(d, f"{name}_NORMAL.png"))
    for k, a in (("METALNESS", met), ("AO", ao), ("DISPLACEMENT", disp), ("ROUGHNESS", rgh)):
        save(a, os.path.join(d, f"{name}_{k}.png"))
    save(np.dstack([met, ao, disp, rgh]), os.path.join(d, f"{name}_MAHS.png"), alpha=True)
    print("wrote", name)


def norm_mean(alb, mean, mul=(1, 1, 1), cap=0.88):
    return np.clip(alb / max(alb.mean(), 1e-4) * mean * np.array(mul, np.float32), 0, cap)


def main():
    render = set_from_folder(CLUB, "MEL_CH_Render")
    a = render["ALBEDO"][..., :3]
    write_set("MDA_RenderWhite", render, albedo=norm_mean(a, 0.72, (1.0, 1.0, 0.97)))
    write_set("MDA_RenderCream", render, albedo=norm_mean(a, 0.78, (1.0, 0.92, 0.78)))
    conc = set_from_folder(CLUB, "Meloneras_Concrete")
    write_set("MDA_FlatRoof", conc, albedo=norm_mean(conc["ALBEDO"][..., :3], 0.58, (1.08, 0.98, 0.84)))

    write_set("MDA_RenderRed", polyhaven("red_plaster_weathered"))

    blk = polyhaven("concrete_block_wall")
    b = blk["ALBEDO"][..., :3]
    b = (b - b.mean()) * 1.6 + 0.50
    b = b * 0.85 + b.mean(axis=2, keepdims=True) * 0.15
    write_set("MDA_Blockwork", blk, albedo=np.clip(b, 0, 1))

    cor = polyhaven("corrugated_iron_02")
    L = grey(cor["ALBEDO"])[..., None]
    L = L / max(L.mean(), 1e-4)
    rough = np.clip(grey(cor["ROUGHNESS"]) * 0.4 + 120 / 255, 0, 1)
    zero = np.zeros((N, N), np.float32)
    for n, col in (("Red", (0.55, 0.26, 0.24)), ("Green", (0.22, 0.46, 0.42)), ("White", (0.78, 0.78, 0.75))):
        write_set("MDA_Corrugated" + n, cor, albedo=np.clip(L * np.array(col, np.float32), 0, 1), metal=zero, rough=rough)

    with open(os.path.join(OUT, "SOURCES.txt"), "w") as f:
        f.write(
            "Mar de Azor PBR sets, 2048x2048 PNG, NORMAL OpenGL, ROUGHNESS white = rough,\n"
            "MAHS R=Metalness G=AO B=Displacement A=Roughness. All sources CC0.\n\n"
            "MDA_RenderWhite / MDA_RenderCream: MEL_CH_Render (Poly Haven white_plaster_02), albedo rescaled/tinted\n"
            "MDA_FlatRoof: Meloneras_Concrete (procedural), albedo warmed\n"
            "MDA_RenderRed: Poly Haven red_plaster_weathered\n"
            "MDA_Blockwork: Poly Haven concrete_block_wall, albedo lifted to mid grey\n"
            "MDA_CorrugatedRed / Green / White: Poly Haven corrugated_iron_02, luminance tinted, metalness 0\n")
    print("DONE textures ->", OUT)


main()
