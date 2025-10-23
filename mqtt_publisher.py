import json
import time
import threading
from awscrt import mqtt
from awsiot import mqtt_connection_builder

class AWSIoTMQTTTestClient:
    def __init__(self, endpoint, client_id, cert_path, key_path, root_ca_path):
        self.endpoint = endpoint
        self.client_id = client_id
        self.cert_path = cert_path
        self.key_path = key_path
        self.root_ca_path = root_ca_path
        self.mqtt_connection = None
        self.is_connected = False
        
    def on_connection_interrupted(self, connection, error, **kwargs):
        print(f"Connection interrupted. error: {error}")
        self.is_connected = False

    def on_connection_resumed(self, connection, return_code, session_present, **kwargs):
        print(f"Connection resumed. return_code: {return_code} session_present: {session_present}")
        self.is_connected = True

    def on_message_received(self, topic, payload, dup, qos, retain, **kwargs):
        try:
            message = json.loads(payload.decode('utf-8'))
            print(f"📨 Received message on topic '{topic}':")
            print(json.dumps(message, indent=2))
        except:
            print(f"📨 Received message on topic '{topic}': {payload.decode('utf-8')}")

    def connect(self):
        try:
            # Create MQTT connection
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.endpoint,
                cert_filepath=self.cert_path,
                pri_key_filepath=self.key_path,
                client_id=self.client_id,
                clean_session=True,
                keep_alive_secs=30,
                on_connection_interrupted=self.on_connection_interrupted,
                on_connection_resumed=self.on_connection_resumed)
            
            print(f"Connecting to {self.endpoint} with client ID {self.client_id}...")
            
            # Connect to AWS IoT
            connect_future = self.mqtt_connection.connect()
            connect_future.result()  # Wait for connection
            self.is_connected = True
            
            print("✅ Successfully connected to AWS IoT!")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def subscribe(self, topic):
        if not self.is_connected:
            print("Not connected to AWS IoT")
            return False
            
        try:
            print(f"Subscribing to topic: {topic}")
            subscribe_future, packet_id = self.mqtt_connection.subscribe(
                topic=topic,
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=self.on_message_received)
            
            subscribe_result = subscribe_future.result()
            print(f"✅ Subscribed to {topic} with QoS: {subscribe_result['qos']}")
            return True
            
        except Exception as e:
            print(f"❌ Subscription failed: {e}")
            return False

    def publish(self, topic, message):
        if not self.is_connected:
            print("Not connected to AWS IoT")
            return False
            
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            
            print(f"Publishing to {topic}: {message}")
            self.mqtt_connection.publish(
                topic=topic,
                payload=message,
                qos=mqtt.QoS.AT_LEAST_ONCE)
            
            print("✅ Message published successfully")
            return True
            
        except Exception as e:
            print(f"❌ Publish failed: {e}")
            return False

    def disconnect(self):
        if self.mqtt_connection and self.is_connected:
            print("Disconnecting from AWS IoT...")
            disconnect_future = self.mqtt_connection.disconnect()
            disconnect_future.result()
            self.is_connected = False
            print("✅ Disconnected")

# Usage example
if __name__ == "__main__":
    # Configuration - Update these paths with your actual certificate files
    config = {
        "endpoint": "a2kymckba2gab5-ats.iot.ap-northeast-1.amazonaws.com",
        "client_id": "Raspberry_AWS_IoT092025",  # Or use your test client ID
        "cert_path": "/home/nippoh/mqtt_publisher/14aa5e7756dbca4a909370cb57ad581e1bd334d390c0b17b96f6efa6bba834ac-certificate.pem.crt",
        "key_path": "/home/nippoh/mqtt_publisher/14aa5e7756dbca4a909370cb57ad581e1bd334d390c0b17b96f6efa6bba834ac-private.pem.key",
        "root_ca_path": "/home/nippoh/mqtt_publisher/AmazonRootCA1.pem"
    }
    
    # Create client instance
    client = AWSIoTMQTTTestClient(**config)
    
    try:
        # Connect to AWS IoT
        if client.connect():
            # Subscribe to topics based on your policy
            client.subscribe("test/dc/#")  # Wildcard subscription
            
            # Publish test messages
            test_message = {
                "timestamp": int(time.time()),
                "message": "Hello from MQTT Test Client",
                "client_id": config["client_id"]
            }
            
            client.publish("test/dc/pubtopic", test_message)
            
            # Keep the client running to receive messages
            print("Listening for messages... Press Ctrl+C to exit")
            while True:
                time.sleep(1)
                client.publish("test/dc/pubtopic", test_message)
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        client.disconnect()
