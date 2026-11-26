extends SceneTree

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 1:
		push_error("Usage: godot --headless --script godot_import_check.gd -- <file.glb>")
		quit(2)
		return

	var glb_path := args[0]
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(glb_path, state)
	if err != OK:
		push_error("GLTFDocument.append_from_file failed with code %d for %s" % [err, glb_path])
		quit(1)
		return

	var scene := doc.generate_scene(state)
	if scene == null:
		push_error("GLTFDocument.generate_scene returned null for %s" % glb_path)
		quit(1)
		return

	var counts := {
		"bones": 0,
		"meshes": 0,
		"shape_keys": 0,
		"anims": 0,
		"max_len": 0.0,
	}
	_walk(scene, counts)
	scene.free()

	if counts["bones"] < 1 or counts["meshes"] < 1 or counts["shape_keys"] < 1:
		push_error(
			"ENGINE_CHECK_FAIL | engine=godot | file=%s | bones=%d | meshes=%d | shape_keys=%d"
			% [glb_path.get_file(), counts["bones"], counts["meshes"], counts["shape_keys"]]
		)
		quit(1)
		return

	print(
		"ENGINE_CHECK_OK | engine=godot | file=%s | bones=%d | meshes=%d | shape_keys=%d | anims=%d | max_len=%.2fs"
		% [
			glb_path.get_file(),
			counts["bones"],
			counts["meshes"],
			counts["shape_keys"],
			counts["anims"],
			counts["max_len"],
		]
	)
	quit(0)


func _walk(node: Node, counts: Dictionary) -> void:
	if node is Skeleton3D:
		counts["bones"] += (node as Skeleton3D).get_bone_count()
	elif node is MeshInstance3D or node.is_class("ImporterMeshInstance3D"):
		var mesh_res = node.get("mesh")
		if mesh_res != null:
			counts["meshes"] += 1
			counts["shape_keys"] += mesh_res.get_blend_shape_count()
	elif node is AnimationPlayer:
		var ap := node as AnimationPlayer
		for anim_name in ap.get_animation_list():
			counts["anims"] += 1
			var anim := ap.get_animation(anim_name)
			if anim != null and anim.length > counts["max_len"]:
				counts["max_len"] = anim.length

	for child in node.get_children():
		_walk(child, counts)
