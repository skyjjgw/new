import datetime
import json
import time
import urllib.request

import paho.mqtt.client as mqtt


NODE_ID = "uno-cloud-gateway-01"
DCCS_KEY = "dd5dc7cde5e65a4be23982dc675c6e19"
API_URL = "https://api-dccs-ensaas.edu.advantech.com.cn"


def fetch_mqtt_credential():
    url = f"{API_URL}/v1/serviceCredentials/{DCCS_KEY}"
    payload = json.loads(urllib.request.urlopen(url).read().decode("utf-8"))
    mqtt_cred = payload["credential"]["protocols"]["mqtt"]
    return {
        "host": payload["serviceHost"],
        "port": mqtt_cred["port"],
        "username": mqtt_cred["username"],
        "password": mqtt_cred["password"],
    }


def utc_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def build_cases():
    return [
        (
            "sdk_conn_online",
            f"/wisepaas/scada/{NODE_ID}/conn",
            {"d": {"Dev": {NODE_ID: 1}}, "ts": utc_now()},
        ),
        (
            "sdk_data_plain_temp",
            f"/wisepaas/scada/{NODE_ID}/data",
            {"d": {NODE_ID: {"temperature": 41}}, "ts": utc_now()},
        ),
        (
            "sdk_data_sys_status",
            f"/wisepaas/scada/{NODE_ID}/data",
            {"d": {NODE_ID: {"#MSYS_EdgeStatus": 1, "temperature": 42}}, "ts": utc_now()},
        ),
        (
            "sdk_data_module_dot",
            f"/wisepaas/scada/{NODE_ID}/data",
            {
                "d": {
                    NODE_ID: {
                        "defaultModule.temperature": 43,
                        "#SYS.devicestatus": 1,
                    }
                },
                "ts": utc_now(),
            },
        ),
        (
            "sdk_data_module_colon",
            f"/wisepaas/scada/{NODE_ID}/data",
            {
                "d": {
                    NODE_ID: {
                        "defaultModule:temperature": 44,
                        "#SYS:devicestatus": 1,
                    }
                },
                "ts": utc_now(),
            },
        ),
        (
            "sdk_data_status_alias",
            f"/wisepaas/scada/{NODE_ID}/data",
            {
                "d": {
                    NODE_ID: {
                        "devicestatus": 1,
                        "temperature": 45,
                    }
                },
                "ts": utc_now(),
            },
        ),
    ]


def main():
    cred = fetch_mqtt_credential()
    print("[INFO] mqtt credential loaded")
    print(json.dumps({k: v for k, v in cred.items() if k != "password"}, ensure_ascii=True))

    client = mqtt.Client(client_id=f"{NODE_ID}-matrix")
    client.username_pw_set(cred["username"], cred["password"])
    client.connect(cred["host"], cred["port"], 60)
    client.loop_start()
    time.sleep(2)

    try:
        for name, topic, payload in build_cases():
            body = json.dumps(payload, ensure_ascii=True)
            print(f"[CASE] {name}")
            print(f"[TOPIC] {topic}")
            print(f"[PAYLOAD] {body}")
            info = client.publish(topic, body, qos=0, retain=False)
            info.wait_for_publish()
            print(f"[RESULT] rc={info.rc}")
            time.sleep(8)
    finally:
        client.loop_stop()
        client.disconnect()
        print("[INFO] mqtt matrix done")


if __name__ == "__main__":
    main()
