[OPEN] debug session: iotedge-cloud-sync

## Symptom
- 修改本地 IoTEdge 的云端 DCCS 配置后，`IoTSuiteIoTEdgeAPI` 曾出现无法稳定启动/页面残缺。
- 本地 `sub001` 曾恢复在线，但切回云端配置后再次全部离线。
- 日志中已出现 `The service credential does not exist.`。

## Hypotheses
1. 云端协同导入虽然成功，但没有为业务网关 `gateway001` 生成可用的 service credential。
2. `iothub.ini` / `config.ini` 的云端参数与业务网关对象不匹配，导致 IoTEdge 以错误身份请求 DCCS。
3. 本地 IoTEdge 连接云端成功，但业务对象 `gateway001/sub001` 与云端对象映射不完整，导致业务数据同步失败。
4. MQTT 消息已进入本地 Broker，但因为设备 worker 状态异常或对象状态机错误，`sub001` 在线状态没有被正确点亮。
5. 服务重启后存在配置缓存或状态残留，导致同一套参数在不同阶段表现不一致。

## Evidence To Collect
- 当前 `IoTSuiteIoTEdgeAPI` 服务状态和关键端口状态。
- 最新 `iotedge_*.log` 中 DCCS、service credential、device state 的报错。
- 本地 MQTT 发消息后是否出现 `receive a report message`。
- 云端对象导入后，`gateway001` / `sub001` 是否真正具备匹配的 credential/绑定关系。

## Confirmed Evidence
- 本地切到云端 DCCS 后，日志多次出现 `The service credential does not exist.`，对象为业务网关 `gateway001`。
- 出现上述报错时，本地 UI 会退化为登录页/残缺页，且 `sub001` 同步离线。
- 将配置切回本地 DCCS 并重启 `IoTSuiteIoTEdgeAPI` 后，本地链路可恢复，`sub001` 能重新在线并刷新温度。
- `iothub.ini` 中多次被回写出裸行 `API_LICENSE_ID`，会直接触发配置解析失败并导致 `IoTSuiteIoTEdgeAPI` 无法稳定启动。
- 将 `iothub.ini` 的 `[dccs]` 段恢复为本地模式后，`10019` 已重新监听，且 `IoTSuiteIoTEdgeAPI`/`IoTSuiteKeeper`/`IoTSuiteRealTimeAnalysis` 当前均为 `Running`。
- 最新日志显示 `running device: 2`，并再次出现 `deviceStatus:online` 与 `temperature` 上报，说明本地采集链已恢复。

## Current Decision
- 暂停继续通过直接修改本地 `ini` 的方式推进上云。
- 先固定“纯本地稳定版”作为工作基线。
- 后续云端改走“对象与凭据完整匹配后再切换”的路线，优先考虑独立云桥接方案，避免再次破坏本地业务链路。
- 当前本地基线修复动作包括：
  - `C:\IoTSuite\iotedge\iothub.ini` 恢复为 `externalMQTTBrokerHost=0.0.0.0` 与 `externalDCCSAddress=http://127.0.0.1:10019`
  - `C:\IoTSuite\config.ini` 与模板中的 `API_LICENSE_ID` 改为显式值 `iotedgewindows30`，避免空值键再次被错误回写为裸行
