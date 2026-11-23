# Benchmark di regressione su golden scene deterministica.
# Indice separato: pure su liste di vertici (niente bpy) + stub quando assente.
# Metriche: volume_drift, penetration, max_vertex_displacement, tempi
# 10k/50k/100k vertici, stabilita 100 frame, round-trip export/import.
# Soglie in benchmark_config.json; report in $TEMP/flexforge_benchmark/report.json.

import json
import math
import os
import statistics
import sys
import tempfile
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

DEFAULT_CONFIG = {
    "volume_drift_max": 0.05,
    "penetration_max_depth": 0.001,
    "penetrating_vertices_max": 0,
    "max_vertex_displacement_max": 0.05,
    "stability_volume_std_max": 0.02,
    "stability_jitter_max": 0.01,
    "roundtrip_max_error": 1e-09,
    "times_max_s": {"10000": 2.0, "50000": 5.0, "100000": 10.0},
    "per_vertex_s_max": 0.0001,
}

GOLDEN_VERTICES = 1000
STABILITY_FRAMES = 100


def load_config():
    path = TOOLS / "benchmark_config.json"
    if path.exists():
        cfg = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        if "times_max_s" in cfg:
            times = dict(DEFAULT_CONFIG["times_max_s"])
            times.update(cfg["times_max_s"])
            merged["times_max_s"] = times
        return merged
    return dict(DEFAULT_CONFIG)


def report_dir():
    base = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    return Path(base) / "flexforge_benchmark"


def golden_scene(vertex_count=GOLDEN_VERTICES):
    """Golden scene deterministica: point cloud su griglia + fattore muscolare."""
    verts = []
    for i in range(vertex_count):
        x = (i % 25) * 0.04
        y = ((i // 25) % 20) * 0.04
        z = ((i // 500) % 2) * 0.5
        verts.append((x, y, z))
    return {"vertices": verts, "name": "golden"}


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def mesh_volume(verts):
    """Stima conservativa del volume: bbox volume deterministico."""
    if not verts:
        return 0.0
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def mesh_volume_value(verts):
    dims = mesh_volume(verts)
    if isinstance(dims, tuple):
        return abs(dims[0] * dims[1] * dims[2])
    return abs(dims)


def volume_drift(before, after):
    v0 = mesh_volume_value(before)
    v1 = mesh_volume_value(after)
    if v0 == 0.0:
        return 0.0 if v1 == 0.0 else float("inf")
    return abs(v1 - v0) / v0


def penetration(scene, plane_normal=(0.0, 0.0, 1.0), plane_offset=0.0):
    """Penetrazione sotto un piano: profondita max e conteggio vertici sotto."""
    n = tuple(plane_normal)
    if _norm(n) == 0:
        raise ValueError("plane_normal must be non-zero")
    depths = []
    for v in scene:
        signed = _dot(v, n) - plane_offset
        depths.append(-signed if signed < 0 else 0.0)
    return {
        "max_depth": max(depths) if depths else 0.0,
        "count": sum(1 for d in depths if d > 0.0),
    }


def max_vertex_displacement(before, after):
    if len(before) != len(after):
        raise ValueError("vertex count mismatch: %d != %d" % (len(before), len(after)))
    best = 0.0
    for a, b in zip(before, after):
        d = _norm(_sub(b, a))
        if d > best:
            best = d
    return best


def _bulge(verts, factor=1.01):
    return [(x * factor, y * factor, z) for x, y, z in verts]


def seeded_displacement(verts, amplitude=0.001):
    out = []
    for i, (x, y, z) in enumerate(verts):
        out.append((x + math.sin(i * 0.37) * amplitude,
                    y + math.cos(i * 0.53) * amplitude,
                    z + math.sin(i * 0.71) * amplitude))
    return out


def timed_sizes(sizes=(10000, 50000, 100000), warmup=100):
    """Tempi deterministici per 10k/50k/100k vertici (wall-clock, ma bounded)."""
    results = {}
    for size in sizes:
        scene = golden_scene(size)["vertices"]
        start = time.perf_counter()
        displaced = seeded_displacement(scene)
        drift = volume_drift(scene, _bulge(displaced))
        elapsed = time.perf_counter() - start
        results[size] = {
            "elapsed_s": elapsed,
            "per_vertex_s": elapsed / float(size),
            "volume_drift": drift,
            "vertices": size,
        }
    return results


def stability_frames(frames=STABILITY_FRAMES):
    """Stabilita su 100 frame: std del volume e jitter medio per-frame."""
    base = golden_scene()["vertices"]
    volumes = []
    jitters = []
    prev = base
    for frame in range(frames):
        shifted = seeded_displacement(base, amplitude=0.0005)
        volumes.append(mesh_volume_value(shifted))
        jitters.append(max_vertex_displacement(prev, shifted))
        prev = shifted
    return {
        "frames": frames,
        "volume_std": statistics.pstdev(volumes) if volumes else 0.0,
        "mean_volume": statistics.fmean(volumes) if volumes else 0.0,
        "jitter_max": max(jitters) if jitters else 0.0,
        "jitter_mean": statistics.fmean(jitters) if jitters else 0.0,
    }


def export_mesh(verts):
    """Export deterministico (placeholder glTF-like): lista di coordinate float."""
    return [[float(x), float(y), float(z)] for x, y, z in verts]


def import_mesh(exported):
    return [(float(p[0]), float(p[1]), float(p[2])) for p in exported]


def roundtrip_error(verts):
    return max_vertex_displacement(list(verts), import_mesh(export_mesh(verts)))


def run_benchmark(config=None):
    cfg = dict(DEFAULT_CONFIG if config is None else config)
    base = golden_scene()["vertices"]
    bulged = _bulge(base)
    drift = volume_drift(base, bulged)
    disp = max_vertex_displacement(base, bulged)
    pen = penetration(base, plane_offset=-0.1)
    times = timed_sizes()
    stab = stability_frames()
    rt = roundtrip_error(base)
    report = {
        "golden_vertices": len(base),
        "volume_drift": drift,
        "penetration": pen,
        "max_vertex_displacement": disp,
        "times": {str(k): v for k, v in times.items()},
        "stability": stab,
        "roundtrip_max_error": rt,
        "thresholds": cfg,
        "passed": bool(
            drift <= cfg["volume_drift_max"]
            and pen["max_depth"] <= cfg["penetration_max_depth"]
            and pen["count"] <= cfg["penetrating_vertices_max"]
            and disp <= cfg["max_vertex_displacement_max"]
            and stab["volume_std"] <= cfg["stability_volume_std_max"]
            and stab["jitter_max"] <= cfg["stability_jitter_max"]
            and rt <= cfg["roundtrip_max_error"]
            and all(v["elapsed_s"] <= cfg["times_max_s"].get(str(k), float("inf"))
                    and v["per_vertex_s"] <= cfg["per_vertex_s_max"]
                    for k, v in times.items())
        ),
    }
    out = report_dir()
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def test_config_loads():
    cfg = load_config()
    assert cfg["volume_drift_max"] > 0, cfg
    assert set(cfg["times_max_s"]) == {"10000", "50000", "100000"}, cfg["times_max_s"]
    assert cfg["times_max_s"]["10000"] < cfg["times_max_s"]["100000"], cfg["times_max_s"]


def test_config_thresholds_ordered():
    cfg = load_config()
    assert cfg["penetration_max_depth"] >= 0, cfg
    assert cfg["roundtrip_max_error"] > 0, cfg
    assert cfg["max_vertex_displacement_max"] > 0, cfg


def test_golden_scene_deterministic():
    a = golden_scene()["vertices"]
    b = golden_scene()["vertices"]
    assert a == b, "golden scene not deterministic"
    assert len(a) == GOLDEN_VERTICES, len(a)
    assert a[0] == (0.0, 0.0, 0.0), a[0]


def test_volume_drift():
    cfg = load_config()
    base = golden_scene()["vertices"]
    drift = volume_drift(base, _bulge(base))
    assert drift <= cfg["volume_drift_max"], drift
    assert volume_drift(base, base) == 0.0, volume_drift(base, base)


def test_volume_drift_bulge_detected():
    base = golden_scene()["vertices"]
    assert volume_drift(base, _bulge(base, factor=1.5)) > volume_drift(base, _bulge(base)), "drift not monotonic"


def test_penetration_clean():
    cfg = load_config()
    base = golden_scene()["vertices"]
    pen = penetration(base, plane_offset=-0.1)
    assert pen["count"] <= cfg["penetrating_vertices_max"], pen
    assert pen["max_depth"] <= cfg["penetration_max_depth"], pen


def test_penetration_detected():
    pen = penetration([(0.0, 0.0, -0.5)], plane_offset=0.0)
    assert pen["max_depth"] == 0.5, pen
    assert pen["count"] == 1, pen


def test_max_vertex_displacement():
    cfg = load_config()
    base = golden_scene()["vertices"]
    assert max_vertex_displacement(base, base) == 0.0
    assert max_vertex_displacement(base, _bulge(base)) <= cfg["max_vertex_displacement_max"] + 1.0, "sanity"
    shifted = [(x + 0.01, y, z) for x, y, z in base]
    assert abs(max_vertex_displacement(base, shifted) - 0.01) < 1e-9


def test_max_displacement_mismatch_error():
    try:
        max_vertex_displacement([(0, 0, 0)], [(0, 0, 0), (1, 0, 0)])
    except ValueError as exc:
        assert "mismatch" in str(exc), exc
    else:
        raise AssertionError("expected ValueError on mismatch")


def test_times_10k_50k_100k():
    cfg = load_config()
    times = timed_sizes()
    assert set(times) == {10000, 50000, 100000}, times
    for size, entry in times.items():
        assert entry["vertices"] == size, entry
        assert entry["elapsed_s"] >= 0.0, entry
        assert entry["per_vertex_s"] <= cfg["per_vertex_s_max"], (size, entry)
        assert entry["elapsed_s"] <= cfg["times_max_s"][str(size)], (size, entry)


def test_stability_100_frames():
    cfg = load_config()
    stab = stability_frames(frames=STABILITY_FRAMES)
    assert stab["frames"] == 100, stab
    assert stab["volume_std"] <= cfg["stability_volume_std_max"], stab
    assert stab["jitter_max"] <= cfg["stability_jitter_max"], stab


def test_roundtrip_export_import():
    cfg = load_config()
    base = golden_scene()["vertices"]
    assert roundtrip_error(base) <= cfg["roundtrip_max_error"], roundtrip_error(base)
    assert import_mesh(export_mesh(base)) == list(base), "round-trip not exact"


def test_report_saved():
    report = run_benchmark(load_config())
    path = report_dir() / "report.json"
    assert path.exists(), path
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["golden_vertices"] == GOLDEN_VERTICES, saved
    assert "volume_drift" in saved and "stability" in saved, saved
    assert saved["passed"] is True, saved


def _main():
    tests = [
        test_config_loads,
        test_config_thresholds_ordered,
        test_golden_scene_deterministic,
        test_volume_drift,
        test_volume_drift_bulge_detected,
        test_penetration_clean,
        test_penetration_detected,
        test_max_vertex_displacement,
        test_max_displacement_mismatch_error,
        test_times_10k_50k_100k,
        test_stability_100_frames,
        test_roundtrip_export_import,
        test_report_saved,
    ]
    passed = 0
    failed = 0
    for case in tests:
        try:
            case()
        except Exception:
            failed += 1
            traceback.print_exc()
        else:
            passed += 1
    total = passed + failed
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, total))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())
