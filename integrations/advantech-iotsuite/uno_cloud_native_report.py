import argparse
import datetime
import json
import os
import time
import urllib.request

import paho.mqtt.client as mqtt


def fetch_mqtt_credential(api_url, dccs_key):
    url = f"{api_url.rstrip('/')}/v1/serviceCredentials/{dccs_key}"
    payload = json.loads(urllib.request.urlopen(url).read().decode("utf-8"))
    mqtt_cred = payload["credential"]["protocols"]["mqtt"]
    return {
        "host": payload.get("serviceHost") or payload["serviceHost"],
        "port": int(mqtt_cred["port"]),
        "username": mqtt_cred["username"],
        "password": mqtt_cred["password"],
    }


def iso_ts(offset_seconds=0):
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz) + datetime.timedelta(seconds=offset_seconds)
    return now.isoformat(timespec="seconds")


def make_payload(device_id, *, online=None, temperature=None, offset_seconds=0):
    services = {}
    if online is not None:
        services["#SYS"] = {
            "properties": {
                "deviceStatus": {
                    "value": "online" if online else "offline",
                    "dataType": "string",
                }
            }
        }
    if temperature is not None:
        services["defaultModule"] = {
            "properties": {
                "temperature": {
                    "value": int(temperature),
                    "dataType": "int",
                }
            }
        }
    payload = {
        "d_id": device_id,
        "ts": iso_ts(offset_seconds),
    }
    if services:
        payload["services"] = services
    return payload


def publish_json(client, topic, payload):
    body = json.dumps(payload, ensure_ascii=False)
    info = client.publish(topic, body, qos=0, retain=False)
    info.wait_for_publish()
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"publish failed rc={info.rc} topic={topic}")
    print(f"[PUB] {topic}")
    print(body)


def main():
    parser = argparse.ArgumentParser(description="Publish native IoTSuite MQTT report/heartbeat data")
    parser.add_argument("--api-url", default=os.environ.get("IOTSUITE_API_URL"))
    parser.add_argument("--dccs-key", default=os.environ.get("IOTSUITE_DCCS_KEY"))
    parser.add_argument("--gateway-id", default=os.environ.get("IOTSUITE_GATEWAY_ID"))
    parser.add_argument("--device-id", default=os.environ.get("IOTSUITE_DEVICE_ID"))
    parser.add_argument("--interval", type=int, default=20)
    parser.add_argument("--count", type=int, default=0, help="0 means run forever")
    parser.add_argument("--base-temperature", type=int, default=30)
    args = parser.parse_args()

    missing = [
        name
        for name, value in (
            ("api-url", args.api_url),
            ("dccs-key", args.dccs_key),
            ("gateway-id", args.gateway_id),
            ("device-id", args.device_id),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"missing required args/env: {', '.join(missing)}")

    cred = fetch_mqtt_credential(args.api_url, args.dccs_key)
    client = mqtt.Client(client_id=f"{args.gateway_id}-native-reporter")
    client.username_pw_set(cred["username"], cred["password"])
    client.connect(cred["host"], cred["port"], 60)
    client.loop_start()
    time.sleep(2)

    heartbeat_topic = f"/device/{args.gateway_id}/up/heartbeat"
    report_topic = f"/device/{args.gateway_id}/up/report"

    try:
        step = 0
        while True:
            publish_json(
                client,
                report_topic,
                make_payload(args.device_id, online=True, offset_seconds=step),
            )
            time.sleep(1)
            publish_json(
                client,
                heartbeat_topic,
                make_payload(args.device_id, offset_seconds=step + 1),
            )
            time.sleep(1)
            temp = args.base_temperature + (step % 5)
            publish_json(
                client,
                report_topic,
                make_payload(
                    args.device_id,
                    online=True,
                    temperature=temp,
                    offset_seconds=step + 2,
                ),
            )
            step += 3
            if args.count and step // 3 >= args.count:
                break
            time.sleep(max(1, args.interval - 2))
    finally:
        client.loop_stop()
        client.disconnect()
        print("[INFO] disconnected")


if __name__ == "__main__":
    main()
