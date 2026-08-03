import argparse
import datetime
import math
import threading
import time

from edgesync360edgehubedgesdk.EdgeAgent import EdgeAgent
from edgesync360edgehubedgesdk.Model.Edge import (
    AnalogTagConfig,
    DCCSOptions,
    DeviceConfig,
    EdgeAgentOptions,
    EdgeConfig,
    EdgeData,
    EdgeDeviceStatus,
    EdgeStatus,
    EdgeTag,
    NodeConfig,
)
import edgesync360edgehubedgesdk.Common.Constants as constant


NODE_ID = "uno-cloud-gateway-01"
API_URL = "https://api-dccs-ensaas.edu.advantech.com.cn"
DCCS_KEY = "dd5dc7cde5e65a4be23982dc675c6e19"
DEVICE_ID = NODE_ID
TAG_NAME = "temperature"


connected_event = threading.Event()
disconnected_event = threading.Event()


def on_connected(is_connected):
    print(f"[EVENT] connected={is_connected}")
    if is_connected:
        connected_event.set()


def on_disconnected(is_disconnected):
    print(f"[EVENT] disconnected={is_disconnected}")
    if is_disconnected:
        disconnected_event.set()


def on_message(message_event):
    print(f"[EVENT] message_type={message_event.type}")


def build_agent():
    options = EdgeAgentOptions(
        nodeId=NODE_ID,
        deviceId=NODE_ID,
        type=constant.EdgeType["Gateway"],
        heartbeat=60,
        dataRecover=False,
        connectType=constant.ConnectType["MQTT"],
        DCCS=DCCSOptions(apiUrl=API_URL, credentialKey=DCCS_KEY),
    )
    agent = EdgeAgent(options)
    agent.on_connected = on_connected
    agent.on_disconnected = on_disconnected
    agent.on_message = on_message
    return agent


def build_config():
    config = EdgeConfig()
    config.node = NodeConfig(nodeType=constant.EdgeType["Gateway"])

    device = DeviceConfig(
        id=DEVICE_ID,
        name=NODE_ID,
        deviceType="UnoCloudGatewayModel01",
        description="UNO cloud gateway self report",
    )
    device.analogTagList.append(
        AnalogTagConfig(
            name=TAG_NAME,
            description="temperature",
            readOnly=False,
            arraySize=0,
            spanHigh=100,
            spanLow=-20,
            engineerUnit="C",
            integerDisplayFormat=5,
            fractionDisplayFormat=2,
        )
    )
    config.node.deviceList.append(device)
    return config


def upload_config(agent):
    config = build_config()
    for action_name in ("Create", "Update"):
        action = constant.ActionType[action_name]
        try:
            result = agent.uploadConfig(action, config)
            print(f"[STEP] uploadConfig action={action_name} result={result}")
            return result
        except Exception as exc:
            print(f"[WARN] uploadConfig action={action_name} failed: {exc!r}")
    return False


def send_status(agent):
    device_status = EdgeDeviceStatus()
    device_status.deviceList.append(
        EdgeStatus(id=DEVICE_ID, status=constant.Status["Online"])
    )
    agent.sendDeviceStatus(device_status)
    print(f"[STEP] sendDeviceStatus device={DEVICE_ID} status=Online")


def send_temperature(agent, value):
    edge_data = EdgeData()
    edge_data.tagList.append(EdgeTag(deviceId=DEVICE_ID, tagName=TAG_NAME, value=value))
    edge_data.timestamp = datetime.datetime.now()
    result = agent.sendData(edge_data)
    print(f"[STEP] sendData device={DEVICE_ID} tag={TAG_NAME} value={value} result={result}")


def generate_temperature(index, base, amplitude):
    # Add a gentle wave so the cloud chart shows visible movement instead of flat values.
    return round(base + math.sin(index / 3.0) * amplitude + index * 0.03, 2)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-minutes", type=int, default=0)
    parser.add_argument("--interval-seconds", type=int, default=5)
    parser.add_argument("--base-temperature", type=float, default=26.2)
    parser.add_argument("--amplitude", type=float, default=1.1)
    return parser.parse_args()


def main():
    args = parse_args()
    agent = build_agent()
    try:
        print(f"[INFO] connecting node={NODE_ID}")
        agent.connect()
        if not connected_event.wait(20):
            raise TimeoutError("timeout waiting for connected event")

        time.sleep(2)
        upload_config(agent)
        time.sleep(2)
        send_status(agent)
        time.sleep(1)

        if args.duration_minutes > 0:
            total_count = max(1, int(args.duration_minutes * 60 / args.interval_seconds))
        else:
            total_count = 6

        print(
            f"[INFO] reporting count={total_count} interval={args.interval_seconds}s "
            f"duration_minutes={args.duration_minutes}"
        )

        for index in range(total_count):
            value = generate_temperature(
                index=index,
                base=args.base_temperature,
                amplitude=args.amplitude,
            )
            send_temperature(agent, value)
            if index < total_count - 1:
                time.sleep(args.interval_seconds)

        time.sleep(3)
        print("[INFO] report cycle finished")
    finally:
        print("[INFO] disconnecting")
        try:
            agent.disconnect()
        finally:
            disconnected_event.wait(5)
            print("[INFO] disconnected")


if __name__ == "__main__":
    main()
