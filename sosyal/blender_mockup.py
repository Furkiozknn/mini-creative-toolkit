#!/usr/bin/env python3
"""3D phone mockup: plays a video on a phone screen inside a Blender scene,
with a camera move (push-in + slight orbit). Runs headless on CPU (bpy 5.0.1).

usage: python3 blender_mockup.py video.mp4 cikti.mp4 [--sure 6] [--motor cycles|eevee] [--ornek 16] [--olcek 50]
   --olcek: render resolution percent of 1080x1920 (lower = much faster)
"""
import argparse, math, os, subprocess, tempfile, time
import bpy


def sahne(video, sure, motor, ornek, olcek, renk=(0.09, 0.07, 0.05)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    fps = 30
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, int(sure * fps)
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = olcek
    if motor == "cycles":
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = ornek
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 4
    else:
        sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys() else "BLENDER_EEVEE"
    sc.view_settings.view_transform = "Standard"

    # World: soft coloured backdrop
    w = bpy.data.worlds.new("dunya"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*renk, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.6

    # Floor / backdrop plane
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.6))
    zemin = bpy.context.object
    zm = bpy.data.materials.new("zemin"); zm.use_nodes = True
    zm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*[c * 1.6 for c in renk], 1)
    zm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    zemin.data.materials.append(zm)

    # Phone body: bevelled box 7.2 x 15 x 0.8 (units ~ cm)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    govde = bpy.context.object
    govde.scale = (3.6, 7.5, 0.4)
    bpy.ops.object.transform_apply(scale=True)
    b = govde.modifiers.new("bevel", "BEVEL"); b.width = 0.25; b.segments = 12
    gm = bpy.data.materials.new("govde"); gm.use_nodes = True
    p = gm.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1)
    p.inputs["Metallic"].default_value = 0.6; p.inputs["Roughness"].default_value = 0.25
    govde.data.materials.append(gm)

    # Screen: 9:16 plane just above the body, emissive video texture
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0.405))
    ekran = bpy.context.object
    ekran.scale = (6.7, 6.7 * 16 / 9, 1)
    bpy.ops.object.transform_apply(scale=True)
    em = bpy.data.materials.new("ekran"); em.use_nodes = True
    nt = em.node_tree; nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(video)
    img.source = "MOVIE"
    tex.image = img
    tex.image_user.frame_duration = sc.frame_end
    tex.image_user.use_auto_refresh = True
    tex.image_user.use_cyclic = True
    emi = nt.nodes.new("ShaderNodeEmission"); emi.inputs[1].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs[0], emi.inputs[0]); nt.links.new(emi.outputs[0], out.inputs[0])
    ekran.data.materials.append(em)

    # Tilt the phone a little for a product-shot feel
    ekran.parent = govde  # rotate as one object so the screen never dips into the body
    govde.rotation_euler = (math.radians(-8), math.radians(10), math.radians(-6))
    govde.location.z = 1.8  # lift clear of the floor once tilted

    # Lights
    bpy.ops.object.light_add(type="AREA", location=(-8, -6, 14)); l = bpy.context.object
    l.data.energy = 3500; l.data.size = 10
    bpy.ops.object.light_add(type="AREA", location=(9, 8, 6)); l2 = bpy.context.object
    l2.data.energy = 1200; l2.data.size = 6; l2.data.color = (1.0, 0.8, 0.6)

    # Camera: push in + gentle orbit, eased
    bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
    cam.data.lens = 50
    hedef = bpy.data.objects.new("hedef", None); bpy.context.collection.objects.link(hedef)
    k = cam.constraints.new("TRACK_TO"); k.target = hedef; k.track_axis = "TRACK_NEGATIVE_Z"; k.up_axis = "UP_Y"
    for f, (r, a, z) in [(sc.frame_start, (34, -16, 30)), (sc.frame_end, (26, 10, 24))]:
        cam.location = (r * math.sin(math.radians(a)), -r * math.cos(math.radians(a)) * 0.35, z)
        cam.keyframe_insert("location", frame=f)
    for fc in cam.animation_data.action.fcurves if hasattr(cam.animation_data.action, "fcurves") else []:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    return sc


def render(video, cikti, sure=6, motor="cycles", ornek=16, olcek=50):
    sc = sahne(os.path.abspath(video), sure, motor, ornek, olcek)
    td = tempfile.mkdtemp()
    sc.render.filepath = os.path.join(td, "k_")
    sc.render.image_settings.file_format = "PNG"
    t = time.time()
    bpy.ops.render.render(animation=True)
    sure_s = time.time() - t
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-i", os.path.join(td, "k_%04d.png"),
                    "-i", video, "-map", "0:v", "-map", "1:a?", "-shortest", "-vf", "scale=1080:1920:flags=lanczos",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
                    cikti], check=True)
    return dict(kare=sc.frame_end, saniye=round(sure_s, 1), kare_basi=round(sure_s / sc.frame_end, 2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("video"); p.add_argument("cikti")
    p.add_argument("--sure", type=float, default=6); p.add_argument("--motor", default="cycles")
    p.add_argument("--ornek", type=int, default=16); p.add_argument("--olcek", type=int, default=50)
    x = p.parse_args()
    print(render(x.video, x.cikti, x.sure, x.motor, x.ornek, x.olcek))
