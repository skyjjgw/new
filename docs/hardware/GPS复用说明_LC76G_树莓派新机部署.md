# LC76G GPS 复用说明（树莓派纯新机可用版）

## 1. 结论

这套 GPS 配置已经在项目里做成了可直接复用的串口读取方案，核心硬件为 `LC76G` 系列 GNSS 模块，程序通过 `pyserial + pynmea2` 读取 `NMEA 0183` 串口数据，并在进入业务层前完成：

- 串口自动探测
- NMEA 解析
- WGS84 -> GCJ02 坐标转换
- 行人场景平滑滤波
- 速度 / 卫星数 / HDOP / 海拔提取
- 心跳包上报

如果你是一个纯新机，要让这个 GPS 设备成功使用，最关键的是：

1. 确认设备型号与串口连接方式
2. 安装 Python 依赖 `pyserial`、`pynmea2`
3. 确认系统识别出 `/dev/ttyUSB*`、`/dev/ttyACM*`、`/dev/ttyAMA*` 之一
4. 保持波特率为 `115200`
5. 保持坐标系配置为 `GPS_COORD_SYSTEM=gcj02`

---

## 2. 当前项目使用的 GPS 产品型号

### 2.1 代码中明确指向的型号

项目代码中多处明确写的是：

- `LC76G`

对应位置：

- [blind_client_pi5_csi.py](file:///d:/aivoice/new_server_unified/client/blind_client_pi5_csi.py)
- [test_gps_pc.py](file:///d:/aivoice/new_server_unified/client/test_gps_pc.py)

代码里能直接看到的关键信息：

- `LC76G Serial Provider`
- 向 LC76G 发送 `PAIR050` 指令，把刷新率设到 `5Hz`

### 2.2 设备协议特征

当前实现假定 GPS 设备具备以下特征：

- 串口输出 `NMEA 0183`
- 可解析 `RMC` / `GGA`
- 波特率 `115200`
- 支持通过串口发送：

```text
$PAIR050,200*21
```

这个指令在项目中用于把更新频率设置为 `5Hz (200ms)`。

---

## 3. 这套 GPS 复用时必须用到的文件

## 3.1 主文件

最核心文件只有一个：

- [blind_client_pi5_csi.py](file:///d:/aivoice/new_server_unified/client/blind_client_pi5_csi.py)

这个文件里已经包含了完整的：

- GPS 串口读取
- 坐标转换
- 平滑滤波
- 自动端口探测
- 航向角提取
- 业务上报

## 3.2 依赖文件

- [client/requirements.txt](file:///d:/aivoice/new_server_unified/client/requirements.txt)
- [new_server_unified/requirements.txt](file:///d:/aivoice/new_server_unified/requirements.txt)

其中 GPS 相关最关键依赖是：

- `pynmea2`
- `pyserial`

## 3.3 参考与排障文件

- [README_DOCKER.md](file:///d:/aivoice/new_server_unified/client/README_DOCKER.md)
- [USB供电与设备掉线问题记录_20260409.md](file:///d:/aivoice/new_server_unified/client/USB供电与设备掉线问题记录_20260409.md)
- [test_gps_pc.py](file:///d:/aivoice/new_server_unified/client/test_gps_pc.py)

用途分别是：

- `README_DOCKER.md`：容器里如何映射串口设备
- `USB供电与设备掉线问题记录`：树莓派上 USB 串口掉线问题排查
- `test_gps_pc.py`：Windows/电脑端串口读 GPS 的参考版本

---

## 4. 如果要把 GPS 单独抽出来，最少需要保留哪些代码

如果你不是直接整份复用 `blind_client_pi5_csi.py`，而是要抽成单独模块，最少保留下面这些逻辑：

### 4.1 坐标转换函数

必须保留：

- `out_of_china`
- `transformlat`
- `transformlng`
- `wgs84_to_gcj02`

原因：

- GPS 原始输出是 `WGS84`
- 你们地图链路和高德前端使用的是 `GCJ02`
- 不做转换，地图上会偏

### 4.2 行人 GPS 滤波器

必须保留：

- `PedestrianGPSFilter`

当前参数：

- `alpha=0.3`
- `max_jump_meters=15.0`

作用：

- 抑制原地漂移
- 避免瞬时飞点
- 减少导航播报误触发

### 4.3 GPS Provider 抽象层

建议保留：

- `BaseGPSProvider`
- `NoGPSProvider`
- `MockGPSProvider`
- `SerialGPSProvider`

如果你是纯硬件复用，最低限度也应保留：

- `SerialGPSProvider`
- `NoGPSProvider`

### 4.4 自动端口探测

必须保留当前这组候选端口：

```text
/dev/ttyUSB1
/dev/ttyUSB0
/dev/ttyACM0
/dev/ttyS0
/dev/ttyAMA0
/dev/ttyAMA10
```

原因：

- USB 转串口模块常见是 `ttyUSB*`
- 某些板卡或内置串口会落到 `ttyAMA*` / `ttyS*`

### 4.5 全局位置更新接口

必须保留：

- `update_global_location()`

它负责统一输出：

- `lat`
- `lng`
- `angle`
- `nmea`
- `speed`
- `sats`
- `hdop`
- `alt`
- `raw_wgs84_lat`
- `raw_wgs84_lng`

---

## 5. 新机最少要准备的依赖

## 5.1 Python 依赖

至少安装：

```bash
pip install pyserial pynmea2
```

如果你要按项目正式环境装：

```bash
pip install -r d:/aivoice/new_server_unified/client/requirements.txt
pip install -r d:/aivoice/new_server_unified/requirements.txt
```

其中和 GPS 直接相关的就是：

- `pyserial`
- `pynmea2`

## 5.2 系统层要求

树莓派新机至少需要：

- Raspberry Pi OS / Debian 系 Linux
- Python 3
- 串口设备权限

建议额外安装调试工具：

```bash
sudo apt-get update
sudo apt-get install -y minicom screen
```

---

## 6. 驱动问题：到底要不要额外装

## 6.1 USB 接法

如果你的 LC76G 模块是通过 USB 转串口接入树莓派，通常 **不需要单独安装 GPS 专用驱动**。

系统一般会把它识别为：

- `/dev/ttyUSB0`
- `/dev/ttyUSB1`
- `/dev/ttyACM0`

项目现有排查记录里出现过：

- `cp210x ttyUSB1: failed set request ..., status: -110`

见：

- [USB供电与设备掉线问题记录_20260409.md](file:///d:/aivoice/new_server_unified/client/USB供电与设备掉线问题记录_20260409.md)

这说明你们手上的实际 USB 转串口桥接芯片至少有一套是 `cp210x` 路线。

### 建议判断

如果设备插上后能看到：

- `/dev/ttyUSB0`
- `/dev/ttyUSB1`

那多数情况下已经是系统驱动正常工作，不需要额外装厂商驱动。

## 6.2 GPIO UART 接法

如果不是 USB，而是直接走树莓派串口针脚，那么通常需要：

- 开启 Raspberry Pi UART
- 检查端口是 `/dev/ttyAMA0` 还是 `/dev/ttyS0`

这种情况下，重点不是安装驱动，而是：

- 打开串口
- 关闭串口登录控制台占用

---

## 7. 当前项目中的关键配置

## 7.1 波特率

当前固定使用：

```text
115200
```

位置：

- [blind_client_pi5_csi.py](file:///d:/aivoice/new_server_unified/client/blind_client_pi5_csi.py)

## 7.2 默认串口

`SerialGPSProvider` 默认写的是：

```text
/dev/ttyUSB1
```

但程序实际上会自动扫描多个端口。

## 7.3 坐标系

环境变量：

```text
GPS_COORD_SYSTEM
```

默认值：

```text
gcj02
```

这符合你们当前高德地图和导航链路。

## 7.4 刷新率

代码会主动发送：

```text
$PAIR050,200*21
```

把 LC76G 更新率设置为：

```text
5Hz
```

## 7.5 平滑滤波参数

项目当前配置：

- `alpha=0.3`
- `max_jump_meters=15.0`

这套参数是为行人导航场景调的，不建议新机一上来乱改。

---

## 8. 纯新机复用时建议保留的目录结构

如果你只是复用 GPS，不需要整套项目，建议最小目录如下：

```text
gps_reuse/
├─ gps_provider.py
├─ requirements.txt
├─ test_read_gps.py
└─ README.md
```

其中：

- `gps_provider.py`
  - 抽出坐标转换
  - 抽出 `PedestrianGPSFilter`
  - 抽出 `SerialGPSProvider`
  - 抽出 `update_global_location`

- `requirements.txt`
  - `pyserial`
  - `pynmea2`

- `test_read_gps.py`
  - 只负责打印实时经纬度、航向、速度、卫星数、原始 NMEA

如果你直接复用当前项目，不拆模块，那就只要保留：

```text
new_server_unified/client/blind_client_pi5_csi.py
new_server_unified/client/requirements.txt
new_server_unified/requirements.txt
```

---

## 9. 树莓派新机部署步骤

## 9.1 接设备后先看系统有没有识别

```bash
ls /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyS*
dmesg | tail -n 50
```

你要看到的典型结果是：

- 新增了某个 `ttyUSB*` / `ttyACM*`
- 内核日志里出现串口桥接芯片或 USB 设备挂载信息

## 9.2 处理权限

如果串口存在但 Python 打不开：

```bash
sudo usermod -aG dialout $USER
```

然后重新登录或重启。

## 9.3 装 Python 依赖

```bash
python3 -m pip install pyserial pynmea2
```

## 9.4 先做串口层验证

```bash
python3 - <<'PY'
import serial
port = '/dev/ttyUSB0'
ser = serial.Serial(port, 115200, timeout=1)
for _ in range(10):
    line = ser.readline().decode('ascii', errors='ignore').strip()
    if line:
        print(line)
ser.close()
PY
```

如果能看到：

- `$GPRMC`
- `$GNRMC`
- `$GPGGA`
- `$GNGGA`

就说明串口层已经通了。

## 9.5 再做 NMEA 解析验证

直接复用项目逻辑即可，优先用：

- [blind_client_pi5_csi.py](file:///d:/aivoice/new_server_unified/client/blind_client_pi5_csi.py)

或者电脑端参考：

- [test_gps_pc.py](file:///d:/aivoice/new_server_unified/client/test_gps_pc.py)

---

## 10. 容器部署时的额外配置

如果你不是直接在宿主机跑，而是在 Docker 里跑，需要把串口设备映射进去。

项目现有说明已经写了：

- [README_DOCKER.md](file:///d:/aivoice/new_server_unified/client/README_DOCKER.md)

关键参数示例：

```bash
--device=/dev/ttyUSB0:/dev/ttyUSB0
```

如果 GPS 走的是板载 UART，则要改成：

```bash
--device=/dev/ttyAMA0:/dev/ttyAMA0
```

或者：

```bash
--device=/dev/ttyS0:/dev/ttyS0
```

---

## 11. 当前项目的 GPS 输出内容

这套 GPS 代码最终不仅输出经纬度，还会输出以下附加信息：

- 当前坐标
- 原始 `NMEA`
- 原始 `WGS84`
- 转换后的 `GCJ02`
- 真实航向角 `true_course`
- 速度 `speed_kmh`
- 卫星数 `num_sats`
- `HDOP`
- 海拔 `altitude`

这意味着它不只是“能定位”，而是已经具备给导航链路、前端显示和后端诊断提供较完整数据的能力。

---

## 12. 最常见的失败点

## 12.1 有串口，但没有 NMEA 输出

优先排查：

- USB 线是不是只有供电没有数据
- 波特率是否正确
- 模块是否真正搜到星
- 模块是否供电稳定

## 12.2 设备反复掉线

你们项目里已经真实遇到过 USB 串口掉线和重枚举，见：

- [USB供电与设备掉线问题记录_20260409.md](file:///d:/aivoice/new_server_unified/client/USB供电与设备掉线问题记录_20260409.md)

典型风险：

- USB 供电不足
- 设备共享 USB 总线过载
- 串口号频繁变化

## 12.3 地图位置偏

这不是 GPS 坏，而是：

- 原始输出是 `WGS84`
- 地图使用的是 `GCJ02`

所以一定要保留项目中的坐标转换逻辑。

## 12.4 室内收不到星

这是 GNSS 本身限制，不是代码问题。

当前项目的策略是：

- 没拿到有效 GPS 时，不注入虚拟默认位置覆盖真实数据
- 保持最后一次有效值或不上报新值

---

## 13. 推荐的新机验收清单

纯新机第一次接这套 GPS，建议按下面顺序验收：

1. `ls /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA*`
2. `dmesg | tail -n 50`
3. `python3 -c "import serial, pynmea2; print('ok')"`
4. 串口读原始 NMEA 是否成功
5. 能否解析出经纬度
6. 能否输出 `RMC/GGA`
7. 坐标转换后能否正常落在高德地图
8. 行走时位置是否连续变化
9. 原地静止时是否没有明显飞点

---

## 14. 外部参考资料

这些资料适合配合本项目一起看：

### 14.1 产品与协议资料

- Quectel LC76G 官方产品页  
  https://www.quectel.com/product/gnss-lc76g-series

- Waveshare LC76G 模块 Wiki  
  https://www.waveshare.com/wiki/LC76G_GNSS_Module

### 14.2 Python 串口与 NMEA 解析

- pySerial 文档  
  https://pyserial.readthedocs.io/en/latest/

- pySerial GPS/NMEA 示例  
  https://www.pyserial.org/docs/gps-nmea

- pynmea2 示例  
  https://github.com/Knio/pynmea2/blob/master/examples/read_serial.py

---

## 15. 最终建议

如果你的目标是“一个纯新机快速把这套 GPS 跑通”，最务实的做法不是完全重写，而是：

1. 直接复用 [blind_client_pi5_csi.py](file:///d:/aivoice/new_server_unified/client/blind_client_pi5_csi.py) 里的 GPS 段
2. 保留 `WGS84 -> GCJ02`
3. 保留 `PedestrianGPSFilter`
4. 保留端口自动探测列表
5. 保持 `115200 + GPS_COORD_SYSTEM=gcj02`
6. 新机先做串口/NMEA 验证，再接入业务

如果后面你要把这套 GPS 真正拆成独立 Python 模块，建议再单独做一个：

- `gps_provider.py`
- `test_read_gps.py`
- `README.md`

这样后续换树莓派、换项目、换服务端都更好复用。
