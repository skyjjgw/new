"""Resize a fixed-shape Ultralytics YOLOv8 detect ONNX export.

The original competition model was exported at 320x320 with its DFL anchor
grid folded into constants. Merely changing the model input shape is therefore
invalid. This utility updates the input/output metadata, DFL reshapes, anchor
grid and stride table together so a smaller fixed input can be benchmarked on
Raspberry Pi CPU inference.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper


ANCHOR_NAME = "/model.22/Constant_12_output_0"
STRIDE_NAME = "/model.22/Constant_15_output_0"
DFL_SHAPE_NAME = "/model.22/dfl/Constant_output_0"
DFL_OUTPUT_SHAPE_NAME = "/model.22/dfl/Constant_1_output_0"


def replace_initializer(model: onnx.ModelProto, name: str, value: np.ndarray) -> None:
    for index, item in enumerate(model.graph.initializer):
        if item.name == name:
            model.graph.initializer[index].CopyFrom(numpy_helper.from_array(value, name))
            return
    raise ValueError(f"initializer not found: {name}")


def build_grids(size: int) -> tuple[np.ndarray, np.ndarray]:
    anchors: list[np.ndarray] = []
    strides: list[np.ndarray] = []
    for stride in (8, 16, 32):
        cells = size // stride
        yy, xx = np.meshgrid(
            np.arange(cells, dtype=np.float32) + 0.5,
            np.arange(cells, dtype=np.float32) + 0.5,
            indexing="ij",
        )
        anchors.append(np.stack((xx, yy)).reshape(2, -1))
        strides.append(np.full(cells * cells, stride, dtype=np.float32))
    return np.concatenate(anchors, axis=1)[None], np.concatenate(strides)[None]


def resize_model(source: Path, destination: Path, size: int) -> None:
    if size < 160 or size % 32:
        raise ValueError("size must be at least 160 and divisible by 32")

    model = onnx.load(str(source))
    anchors, strides = build_grids(size)
    anchor_count = anchors.shape[-1]

    input_shape = model.graph.input[0].type.tensor_type.shape.dim
    input_shape[0].dim_value = 1
    input_shape[1].dim_value = 3
    input_shape[2].dim_value = size
    input_shape[3].dim_value = size

    output_shape = model.graph.output[0].type.tensor_type.shape.dim
    output_shape[0].dim_value = 1
    output_shape[2].dim_value = anchor_count

    # The simplified source contains static intermediate shape annotations for
    # 320x320. Let the runtime infer them again from the resized graph.
    del model.graph.value_info[:]

    replace_initializer(
        model, DFL_SHAPE_NAME, np.array([1, 4, 16, anchor_count], dtype=np.int64)
    )
    replace_initializer(
        model, DFL_OUTPUT_SHAPE_NAME, np.array([1, 4, anchor_count], dtype=np.int64)
    )
    replace_initializer(model, ANCHOR_NAME, anchors)
    replace_initializer(model, STRIDE_NAME, strides)

    onnx.checker.check_model(model)
    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(destination))
    print(f"wrote {destination} input={size} anchors={anchor_count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--size", type=int, required=True)
    args = parser.parse_args()
    resize_model(args.source, args.destination, args.size)


if __name__ == "__main__":
    main()
