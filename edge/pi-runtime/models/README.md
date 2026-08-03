# 边缘模型

模型权重不进入 Git 历史。将经过验证的模型放在边缘设备 `/opt/visionbridge/models/`，并在 `/etc/visionbridge/edge.env` 中设置 `MODEL_PATH` 与 `INPUT_SIZE`。

当前实机使用固定输入 `256×256` 的 YOLOv8 ONNX 模型，类别为 `person`、`bicycle`、`motorcycle`、`obstacle_other`、`traffic_light_red`、`traffic_light_green` 和 `zebra_crossing`。

正式发布模型时应使用 GitHub Release 或模型仓库，并同时提供：

- 文件名、版本、SHA-256 和字节数；
- 输入尺寸、归一化和类别顺序；
- 训练数据来源与许可证；
- 精度指标、测试集定义和边缘设备性能；
- 导出工具版本和回滚模型。

本地历史区保留了本次整理前的三个模型文件；它们不会被 Git 上传。转换工具 `../tools/resize_fixed_yolov8_onnx.py` 只用于固定结构模型，转换后必须重新做精度回归。
