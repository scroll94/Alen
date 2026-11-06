"""
Простой low-poly домик для Blender.

Запуск: Blender → вкладка Scripting → Open → этот файл → Run Script (Alt+P).
Скрипт создаёт один объект «Домик» (все части в одном меше, цвета через
слоты материалов) и плоскость «Домик_Земля». Повторный запуск пересоздаёт
домик, не трогая остальную сцену.

Размеры можно поменять в блоке НАСТРОЙКИ ниже.
"""

import math
import bpy
import bmesh

# ----------------------------- НАСТРОЙКИ -----------------------------
W = 4.0            # длина дома по X (вдоль конька), м
D = 3.0            # глубина дома по Y, м
H = 2.5            # высота стен, м
R = 1.4            # высота крыши над стенами, м
BASE = 0.2         # высота фундамента, м
ROOF_T = 0.12      # толщина крыши, м
OVER_EAVE = 0.3    # свес крыши по бокам (над входом и сзади), м
OVER_GABLE = 0.25  # свес крыши над фронтонами, м
ADD_GROUND = True  # добавить плоскость земли
NAME = "Домик"
# ---------------------------------------------------------------------

COLORS = {
    "Стены":     (0.93, 0.85, 0.70, 1),
    "Крыша":     (0.60, 0.16, 0.10, 1),
    "Фундамент": (0.45, 0.45, 0.45, 1),
    "Дверь":     (0.40, 0.23, 0.12, 1),
    "Рама":      (0.95, 0.95, 0.95, 1),
    "Стекло":    (0.40, 0.65, 0.85, 1),
    "Кирпич":    (0.55, 0.25, 0.18, 1),
    "Земля":     (0.30, 0.55, 0.25, 1),
}


def get_material(name):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    color = COLORS[name]
    mat.diffuse_color = color  # цвет в режиме Solid
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.15 if name == "Стекло" else 0.8
    return mat


def remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0:
        bpy.data.meshes.remove(data)


class MeshBuilder:
    """Собирает вершины и грани нескольких частей в один меш."""

    def __init__(self, mat_names):
        self.verts, self.faces, self.face_mats = [], [], []
        self.mat_index = {n: i for i, n in enumerate(mat_names)}
        self.mat_names = mat_names

    def add(self, verts, faces, mat):
        base = len(self.verts)
        self.verts.extend(verts)
        for f in faces:
            self.faces.append([base + i for i in f])
            self.face_mats.append(self.mat_index[mat])

    def box(self, x0, x1, y0, y1, z0, z1, mat):
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.add(v, f, mat)

    def build(self, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        for n in self.mat_names:
            me.materials.append(get_material(n))
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        for f, m in zip(bm.faces, self.face_mats):
            f.material_index = m
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
        me.update()
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        return obj


def wall_box(mb, side, u, zc, w, h, out, mat, into=0.02):
    """Прямоугольная деталь на стене: дверь, окно, подоконник.
    side: 'front' (-Y), 'back' (+Y), 'left' (-X), 'right' (+X).
    u — центр по горизонтали вдоль стены, zc — центр по высоте."""
    z0, z1 = zc - h / 2, zc + h / 2
    a0, a1 = u - w / 2, u + w / 2
    if side == "front":
        mb.box(a0, a1, -D / 2 - out, -D / 2 + into, z0, z1, mat)
    elif side == "back":
        mb.box(a0, a1, D / 2 - into, D / 2 + out, z0, z1, mat)
    elif side == "left":
        mb.box(-W / 2 - out, -W / 2 + into, a0, a1, z0, z1, mat)
    elif side == "right":
        mb.box(W / 2 - into, W / 2 + out, a0, a1, z0, z1, mat)


def window(mb, side, u, zc, size=0.8):
    wall_box(mb, side, u, zc, size + 0.12, size + 0.12, 0.03, "Рама")   # рамка
    wall_box(mb, side, u, zc, size, size, 0.045, "Стекло")              # стекло
    wall_box(mb, side, u, zc, 0.06, size, 0.06, "Рама")                 # крестовина
    wall_box(mb, side, u, zc, size, 0.06, 0.06, "Рама")
    wall_box(mb, side, u, zc - size / 2 - 0.09, size + 0.2, 0.06, 0.12, "Рама")  # подоконник


def make_house():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    remove_object(NAME)
    remove_object(NAME + "_Земля")

    mb = MeshBuilder(["Стены", "Крыша", "Фундамент", "Дверь",
                      "Рама", "Стекло", "Кирпич"])
    z_wall = BASE
    z_eave = BASE + H
    z_ridge = BASE + H + R
    hx = W / 2

    # Фундамент
    mb.box(-hx - 0.08, hx + 0.08, -D / 2 - 0.08, D / 2 + 0.08, 0, BASE, "Фундамент")

    # Стены + фронтоны одной пятиугольной призмой (10 вершин, 7 граней)
    prof = [(-D / 2, z_wall), (D / 2, z_wall), (D / 2, z_eave),
            (0, z_ridge), (-D / 2, z_eave)]
    v = [(-hx, y, z) for y, z in prof] + [(hx, y, z) for y, z in prof]
    f = [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5)] + \
        [(i, i + 5, (i + 1) % 5 + 5, (i + 1) % 5) for i in range(5)]
    mb.add(v, f, "Стены")

    # Двускатная крыша с толщиной и свесами (12 вершин, 10 граней)
    k = R / (D / 2)                                   # уклон ската
    ln = math.hypot(R, D / 2)
    ny, nz = R / ln, (D / 2) / ln                     # нормаль ската
    ey = D / 2 + OVER_EAVE
    ez = z_eave - OVER_EAVE * k
    sec = [(-ey, ez), (0, z_ridge), (ey, ez),                       # низ
           (ey + ROOF_T * ny, ez + ROOF_T * nz),                    # верх
           (0, z_ridge + ROOF_T / nz),
           (-ey - ROOF_T * ny, ez + ROOF_T * nz)]
    rx = hx + OVER_GABLE
    v = [(-rx, y, z) for y, z in sec] + [(rx, y, z) for y, z in sec]
    a, b = 0, 6
    f = [(a + 0, a + 1, a + 4, a + 5), (a + 1, a + 2, a + 3, a + 4),
         (b + 0, b + 5, b + 4, b + 1), (b + 1, b + 4, b + 3, b + 2),
         (a + 0, b + 0, b + 1, a + 1), (a + 1, b + 1, b + 2, a + 2),
         (a + 3, b + 3, b + 4, a + 4), (a + 4, b + 4, b + 5, a + 5),
         (a + 2, b + 2, b + 3, a + 3), (a + 5, b + 5, b + 0, a + 0)]
    mb.add(v, f, "Крыша")

    # Труба на заднем скате
    cx, cy0, cy1 = hx * 0.55, 0.45, 0.85
    roof_top_at = lambda y: z_ridge + ROOF_T / nz - k * y
    mb.box(cx - 0.2, cx + 0.2, cy0, cy1, roof_top_at(cy1) - 0.1,
           z_ridge + 0.55, "Кирпич")
    mb.box(cx - 0.25, cx + 0.25, cy0 - 0.05, cy1 + 0.05, z_ridge + 0.55,
           z_ridge + 0.63, "Фундамент")

    # Дверь и ступенька
    wall_box(mb, "front", 0, z_wall + 0.95, 1.0, 1.9, 0.03, "Рама")
    wall_box(mb, "front", 0, z_wall + 0.92, 0.84, 1.84, 0.05, "Дверь")
    mb.box(-0.6, 0.6, -D / 2 - 0.45, -D / 2, 0, BASE * 0.6, "Фундамент")

    # Окна
    zc = z_wall + 1.45
    window(mb, "front", -hx * 0.62, zc)
    window(mb, "front", hx * 0.62, zc)
    window(mb, "back", 0, zc)
    window(mb, "left", 0, zc)
    window(mb, "right", 0, zc)

    house = mb.build(NAME)

    if ADD_GROUND:
        g = MeshBuilder(["Земля"])
        s = 8.0
        g.add([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)],
              [(0, 1, 2, 3)], "Земля")
        g.build(NAME + "_Земля")

    # Солнце, если в сцене нет света
    if not any(o.type == "LIGHT" for o in bpy.context.scene.objects):
        light = bpy.data.lights.new("Солнце", type="SUN")
        light.energy = 3.0
        sun = bpy.data.objects.new("Солнце", light)
        sun.rotation_euler = (math.radians(50), 0, math.radians(30))
        bpy.context.scene.collection.objects.link(sun)

    for o in bpy.context.selected_objects:
        o.select_set(False)
    house.select_set(True)
    bpy.context.view_layer.objects.active = house

    me = house.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    print(f"{NAME}: вершин {len(me.vertices)}, граней {len(me.polygons)}, треугольников {tris}")
    return house


make_house()
