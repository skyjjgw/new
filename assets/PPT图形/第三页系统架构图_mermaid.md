# 第三页系统架构图

这版适合放在“课题方案设计 / 系统总体架构”页，风格偏课程设计汇报，强调端边云协同与业务闭环。

```mermaid
flowchart LR
    subgraph A["感知端"]
        A1["道路场景<br/>USB摄像头"]
        A2["位置感知<br/>LC76G GPS"]
    end

    subgraph B["边缘端"]
        B1["UNO220 工业计算平台"]
        B2["YOLOv8 目标检测"]
        B3["ROI 命中判定"]
        B4["事件状态机<br/>suspected → active → cleared"]
        B5["冻结 GPS / 抓拍图"]
        B6["MQTT 数据上报"]
    end

    subgraph C["云端平台"]
        C1["IoTSuite 设备模型"]
        C2["DataHub 数据接入"]
        C3["Notification 告警规则"]
        C4["事件数据存储与消费"]
    end

    subgraph D["应用层"]
        D1["城市盲道巡检地图"]
        D2["状态指标卡片"]
        D3["趋势分析图表"]
        D4["派单工作流 / 闭环治理"]
    end

    A1 --> B2
    A2 --> B5

    B1 --> B2 --> B3 --> B4 --> B5 --> B6
    B6 --> C1 --> C2 --> C4
    C4 --> C3
    C4 --> D1
    C4 --> D2
    C4 --> D3
    C3 --> D4

    style A fill:#EAF4FF,stroke:#4A90E2,stroke-width:2px
    style B fill:#EEF8F1,stroke:#35A16B,stroke-width:2px
    style C fill:#FFF5E8,stroke:#F39C12,stroke-width:2px
    style D fill:#F5F1FF,stroke:#7D5CE6,stroke-width:2px
```

## PPT 中的标题建议

- 主标题：课题方案设计
- 副标题：基于边云协同的城市盲道违规占用监测系统总体架构

## 页面右侧可配的三句说明

1. 感知端采集道路视频与位置信息，为事件识别提供原始输入。
2. 边缘端基于 UNO220 完成目标检测、状态判定、坐标冻结与 MQTT 上报。
3. 云端平台实现地图展示、指标分析、告警联动与治理闭环。

