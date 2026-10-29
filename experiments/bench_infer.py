"""Mäter inferenstid för föreslagna nätverk med ONNX Runtime på CPU.

A  tillväxt/avtagande-nät på 8 km över Sverigedomänen (224 x 120),
   64 indatakanaler, U-Net med 32/64/128 kanaler, 48 utkanaler (24 ledtider x 2 termer).
B  finskaligt restnät på 2 km (896 x 480), 8 indatakanaler, U-Net 16/32/64, 24 utkanaler.

Nätverken har slumpvikter; bara storlek och tid är relevanta här.
"""

from __future__ import annotations

import time

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper, numpy_helper


def unet(name, cin, chans, cout, h, w):
    nodes, inits, flops = [], [], 0
    rng = np.random.default_rng(0)

    def conv(x, ci, co, hh, ww, tag):
        nonlocal flops
        wname, bname = f"{tag}_w", f"{tag}_b"
        inits.append(numpy_helper.from_array((rng.standard_normal((co, ci, 3, 3)) * 0.05).astype(np.float32), wname))
        inits.append(numpy_helper.from_array(np.zeros(co, np.float32), bname))
        nodes.append(helper.make_node("Conv", [x, wname, bname], [f"{tag}_c"], pads=[1, 1, 1, 1]))
        nodes.append(helper.make_node("Relu", [f"{tag}_c"], [f"{tag}_r"]))
        flops += 2 * ci * co * 9 * hh * ww
        return f"{tag}_r"

    x, ci, hh, ww, skips = "x", cin, h, w, []
    for lvl, c in enumerate(chans):
        x = conv(x, ci, c, hh, ww, f"d{lvl}a")
        x = conv(x, c, c, hh, ww, f"d{lvl}b")
        ci = c
        if lvl < len(chans) - 1:
            skips.append((x, c, hh, ww))
            nodes.append(helper.make_node("MaxPool", [x], [f"p{lvl}"], kernel_shape=[2, 2], strides=[2, 2]))
            x, hh, ww = f"p{lvl}", hh // 2, ww // 2
    for lvl in reversed(range(len(chans) - 1)):
        sx, sc, sh, sw = skips[lvl]
        scales = numpy_helper.from_array(np.array([1, 1, 2, 2], np.float32), f"s{lvl}")
        inits.append(scales)
        nodes.append(helper.make_node("Resize", [x, "", f"s{lvl}"], [f"u{lvl}"], mode="nearest"))
        nodes.append(helper.make_node("Concat", [f"u{lvl}", sx], [f"k{lvl}"], axis=1))
        x = conv(f"k{lvl}", ci + sc, sc, sh, sw, f"u{lvl}a")
        x = conv(x, sc, sc, sh, sw, f"u{lvl}b")
        ci, hh, ww = sc, sh, sw
    inits.append(numpy_helper.from_array((rng.standard_normal((cout, ci, 1, 1)) * 0.05).astype(np.float32), "out_w"))
    nodes.append(helper.make_node("Conv", [x, "out_w"], ["y"]))
    flops += 2 * ci * cout * hh * ww
    g = helper.make_graph(
        nodes, name,
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, cin, h, w])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, cout, h, w])],
        inits,
    )
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 17)])
    m.ir_version = 9
    onnx.checker.check_model(m)
    params = sum(int(np.prod(i.dims)) for i in inits)
    return m, flops, params


def bench(model, cin, h, w, threads):
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    s = ort.InferenceSession(model.SerializeToString(), so, providers=["CPUExecutionProvider"])
    x = np.random.default_rng(1).standard_normal((1, cin, h, w)).astype(np.float32)
    s.run(None, {"x": x})
    t = time.perf_counter()
    for _ in range(3):
        s.run(None, {"x": x})
    return (time.perf_counter() - t) / 3


if __name__ == "__main__":
    for name, cin, chans, cout, h, w in [
        ("A tillväxt/avtagande 8 km", 64, [32, 64, 128], 48, 224, 120),
        ("B finskaligt rest 2 km", 8, [16, 32, 64], 24, 896, 480),
    ]:
        m, flops, params = unet(name, cin, chans, cout, h, w)
        t1 = bench(m, cin, h, w, 1)
        t2 = bench(m, cin, h, w, 2)
        print(f"{name}: {flops / 1e9:.1f} GFLOP, {params / 1e6:.2f} M parametrar, {t1:.2f} s (1 tråd), {t2:.2f} s (2 trådar)")
