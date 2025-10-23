import json
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from awscrt import mqtt
from awsiot import mqtt_connection_builder
from datetime import datetime

class MQTTPublisherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MQTT Publisher - Send Data")
        self.root.geometry("600x700")
        self.root.resizable(True, True)
        
        # MQTT Configuration
        self.config = {
            "endpoint": "a2kymckba2gab5-ats.iot.ap-northeast-1.amazonaws.com",
            "client_id": "Raspberry_AWS_IoT092025",
            "cert_path": "/home/nippoh/mqtt_publisher/14aa5e7756dbca4a909370cb57ad581e1bd334d390c0b17b96f6efa6bba834ac-certificate.pem.crt",
            "key_path": "/home/nippoh/mqtt_publisher/14aa5e7756dbca4a909370cb57ad581e1bd334d390c0b17b96f6efa6bba834ac-private.pem.key",
            "root_ca_path": "/home/nippoh/mqtt_publisher/AmazonRootCA1.pem"
        }
        
        self.mqtt_connection = None
        self.is_connected = False
        self.auto_publish_active = False
        self.auto_publish_thread = None
        self.subscribed_topics = []
        
        self.setup_gui()
        
    def setup_gui(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="MQTT Data Publisher", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Connection status frame
        status_frame = ttk.LabelFrame(main_frame, text="Connection Status", padding="10")
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="🔄 Connecting...")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                     font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=0, padx=5)
        
        # Topic configuration frame
        topic_frame = ttk.LabelFrame(main_frame, text="Topic Configuration", padding="10")
        topic_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        topic_frame.columnconfigure(1, weight=1)
        
        ttk.Label(topic_frame, text="Topic:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.topic_var = tk.StringVar(value="test/dc/pubtopic")
        self.topic_entry = ttk.Entry(topic_frame, textvariable=self.topic_var, width=40)
        self.topic_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # Subscription frame (for receiving messages)
        subscription_frame = ttk.LabelFrame(main_frame, text="Message Reception", padding="10")
        subscription_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        subscription_frame.columnconfigure(1, weight=1)
        
        # Subscription controls
        ttk.Label(subscription_frame, text="Subscribe to:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.subscribe_topic_var = tk.StringVar(value="test/my/#")
        subscribe_entry = ttk.Entry(subscription_frame, textvariable=self.subscribe_topic_var, width=30)
        subscribe_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.subscribe_btn = ttk.Button(subscription_frame, text="📥 Subscribe", 
                                       command=self.subscribe_to_topic, state="disabled")
        self.subscribe_btn.grid(row=0, column=2)
        
        # Active subscriptions list
        ttk.Label(subscription_frame, text="Active Subscriptions:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        
        # Listbox for subscriptions with scrollbar
        list_frame = ttk.Frame(subscription_frame)
        list_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        list_frame.columnconfigure(0, weight=1)
        
        self.subscriptions_listbox = tk.Listbox(list_frame, height=2)
        self.subscriptions_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        sub_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.subscriptions_listbox.yview)
        sub_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.subscriptions_listbox.configure(yscrollcommand=sub_scrollbar.set)
        
        self.unsubscribe_btn = ttk.Button(subscription_frame, text="🗑️ Unsubscribe Selected", 
                                         command=self.unsubscribe_from_topic, state="disabled")
        self.unsubscribe_btn.grid(row=3, column=0, columnspan=3, pady=(5, 0))
        
        # Received messages display
        ttk.Label(subscription_frame, text="Received Messages:").grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        self.received_text = scrolledtext.ScrolledText(subscription_frame, height=4, width=50, font=("Consolas", 9))
        self.received_text.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Message composition frame
        msg_frame = ttk.LabelFrame(main_frame, text="Message Composition", padding="10")
        msg_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        msg_frame.columnconfigure(0, weight=1)
        msg_frame.rowconfigure(1, weight=1)
        
        # Message type selection
        type_frame = ttk.Frame(msg_frame)
        type_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(type_frame, text="Message Type:").grid(row=0, column=0, padx=(0, 10))
        self.msg_type = tk.StringVar(value="JSON")
        ttk.Radiobutton(type_frame, text="JSON", variable=self.msg_type, 
                       value="JSON", command=self.update_message_template).grid(row=0, column=1, padx=5)
        ttk.Radiobutton(type_frame, text="Plain Text", variable=self.msg_type, 
                       value="TEXT", command=self.update_message_template).grid(row=0, column=2, padx=5)
        
        # Message text area
        self.message_text = scrolledtext.ScrolledText(msg_frame, height=10, width=50)
        self.message_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.update_message_template()
        
        # Publishing controls frame
        pub_frame = ttk.LabelFrame(main_frame, text="Publishing Controls", padding="10")
        pub_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        pub_frame.columnconfigure(0, weight=1)
        
        # Single publish
        single_frame = ttk.Frame(pub_frame)
        single_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        single_frame.columnconfigure(0, weight=1)
        
        self.publish_btn = ttk.Button(single_frame, text="📤 Publish Message", 
                                     command=self.publish_single_message, state="disabled")
        self.publish_btn.grid(row=0, column=0)
        
        # Auto publish controls
        auto_frame = ttk.Frame(pub_frame)
        auto_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        ttk.Label(auto_frame, text="Auto Publish Interval (seconds):").grid(row=0, column=0, padx=(0, 10))
        self.interval_var = tk.StringVar(value="5")
        interval_spinbox = ttk.Spinbox(auto_frame, from_=1, to=60, width=10, 
                                      textvariable=self.interval_var)
        interval_spinbox.grid(row=0, column=1, padx=(0, 10))
        
        self.auto_publish_btn = ttk.Button(auto_frame, text="🔄 Start Auto Publish", 
                                          command=self.toggle_auto_publish, state="disabled")
        self.auto_publish_btn.grid(row=0, column=2)
        
        # Status log frame
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, width=50)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure main frame row weights
        main_frame.rowconfigure(4, weight=2)  # Message composition
        main_frame.rowconfigure(6, weight=1)  # Activity log
        
        self.log_message("🚀 MQTT Publisher GUI started")
        
        # Auto-connect after GUI is ready
        self.root.after(1000, self.auto_connect)
        
    def update_message_template(self):
        """Update message template based on selected type"""
        self.message_text.delete(1.0, tk.END)
        if self.msg_type.get() == "JSON":
            template = {
                "timestamp": int(time.time()),
                "message": "Hello from MQTT Publisher GUI",
                "client_id": self.config["client_id"],
                "data": {
                    "temperature": 25.5,
                    "humidity": 60.0,
                    "status": "active"
                }
            }
            self.message_text.insert(1.0, json.dumps(template, indent=2))
        else:
            self.message_text.insert(1.0, "Hello from MQTT Publisher GUI")
    
    def log_message(self, message):
        """Add message to activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def auto_connect(self):
        """Auto-connect to AWS IoT on startup"""
        threading.Thread(target=self._auto_connect_worker, daemon=True).start()
    
    def _auto_connect_worker(self):
        """Auto-connect worker that connects and subscribes"""
        if self.connect():
            # Auto-subscribe to receive messages from subscriber
            self._subscribe_to_topic("test/my/#")
    
    def on_message_received(self, topic, payload, dup, qos, retain, **kwargs):
        """Handle received MQTT messages from subscriber"""
        try:
            message_data = json.loads(payload.decode('utf-8'))
            formatted_content = json.dumps(message_data, indent=2)
        except:
            formatted_content = payload.decode('utf-8')
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        display_message = f"[{timestamp}] Topic: {topic}\n{formatted_content}\n" + "="*50 + "\n\n"
        
        # Update GUI in main thread
        self.root.after(0, self._update_received_display, display_message)
    
    def _update_received_display(self, message):
        """Update received messages display (called from main thread)"""
        self.received_text.insert(tk.END, message)
        self.received_text.see(tk.END)
    
    def _subscribe_to_topic(self, topic):
        """Internal method to subscribe to topic"""
        try:
            self.log_message(f"🔄 Subscribing to topic: {topic}")
            
            subscribe_future, packet_id = self.mqtt_connection.subscribe(
                topic=topic,
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=self.on_message_received)
            
            subscribe_result = subscribe_future.result()
            
            if topic not in self.subscribed_topics:
                self.subscribed_topics.append(topic)
                self.root.after(0, self._update_subscriptions_list)
            
            self.log_message(f"✅ Subscribed to '{topic}' with QoS: {subscribe_result['qos']}")
            
        except Exception as e:
            self.log_message(f"❌ Subscription failed for '{topic}': {e}")
    
    def subscribe_to_topic(self):
        """Subscribe to a new topic"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to AWS IoT first")
            return
        
        topic = self.subscribe_topic_var.get().strip()
        if not topic:
            messagebox.showwarning("Invalid Topic", "Please enter a topic name")
            return
        
        if topic in self.subscribed_topics:
            messagebox.showinfo("Already Subscribed", f"Already subscribed to '{topic}'")
            return
        
        threading.Thread(target=self._subscribe_to_topic, args=(topic,), daemon=True).start()
    
    def _update_subscriptions_list(self):
        """Update the subscriptions listbox"""
        self.subscriptions_listbox.delete(0, tk.END)
        for topic in self.subscribed_topics:
            self.subscriptions_listbox.insert(tk.END, topic)
        
        if self.subscribed_topics and self.is_connected:
            self.unsubscribe_btn.config(state="normal")
        else:
            self.unsubscribe_btn.config(state="disabled")
    
    def unsubscribe_from_topic(self):
        """Unsubscribe from selected topic"""
        selection = self.subscriptions_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a topic to unsubscribe from")
            return
        
        topic = self.subscriptions_listbox.get(selection[0])
        threading.Thread(target=self._unsubscribe_from_topic, args=(topic,), daemon=True).start()
    
    def _unsubscribe_from_topic(self, topic):
        """Internal method to unsubscribe from topic"""
        try:
            self.log_message(f"🔄 Unsubscribing from topic: {topic}")
            
            unsubscribe_future, packet_id = self.mqtt_connection.unsubscribe(topic=topic)
            unsubscribe_future.result()
            
            if topic in self.subscribed_topics:
                self.subscribed_topics.remove(topic)
            
            self.root.after(0, self._update_subscriptions_list)
            self.log_message(f"✅ Unsubscribed from '{topic}'")
            
        except Exception as e:
            self.log_message(f"❌ Unsubscribe failed for '{topic}': {e}")
    
    def update_connection_status(self):
        """Update connection status display"""
        if self.is_connected:
            self.status_var.set("✅ Connected")
            self.publish_btn.config(state="normal")
            self.auto_publish_btn.config(state="normal")
            self.subscribe_btn.config(state="normal")
            if self.subscribed_topics:
                self.unsubscribe_btn.config(state="normal")
        else:
            self.status_var.set("❌ Disconnected")
            self.publish_btn.config(state="disabled")
            self.auto_publish_btn.config(state="disabled")
            self.subscribe_btn.config(state="disabled")
            self.unsubscribe_btn.config(state="disabled")
    
    def connect(self):
        """Connect to AWS IoT MQTT"""
        try:
            self.log_message("🔄 Connecting to AWS IoT...")
            
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.config["endpoint"],
                cert_filepath=self.config["cert_path"],
                pri_key_filepath=self.config["key_path"],
                client_id=self.config["client_id"],
                clean_session=True,
                keep_alive_secs=30)
            
            connect_future = self.mqtt_connection.connect()
            connect_future.result()
            
            self.is_connected = True
            self.log_message("✅ Successfully connected to AWS IoT!")
            self.root.after(0, self.update_connection_status)
            
        except Exception as e:
            self.log_message(f"❌ Connection failed: {e}")
            self.root.after(0, self.update_connection_status)
    
    def disconnect(self):
        """Disconnect from AWS IoT MQTT"""
        try:
            if self.auto_publish_active:
                self.toggle_auto_publish()
            
            if self.mqtt_connection and self.is_connected:
                self.log_message("🔄 Disconnecting...")
                disconnect_future = self.mqtt_connection.disconnect()
                disconnect_future.result()
                
            self.is_connected = False
            self.subscribed_topics.clear()
            self.subscriptions_listbox.delete(0, tk.END)
            self.log_message("✅ Disconnected from AWS IoT")
            self.update_connection_status()
            
        except Exception as e:
            self.log_message(f"❌ Disconnect error: {e}")
    
    def publish_single_message(self):
        """Publish a single message"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to AWS IoT first")
            return
        
        threading.Thread(target=self._publish_message, daemon=True).start()
    
    def _publish_message(self):
        """Internal method to publish message"""
        try:
            topic = self.topic_var.get().strip()
            message_content = self.message_text.get(1.0, tk.END).strip()
            
            if not topic:
                self.log_message("❌ Topic cannot be empty")
                return
            
            if not message_content:
                self.log_message("❌ Message cannot be empty")
                return
            
            # Validate JSON if JSON type is selected
            if self.msg_type.get() == "JSON":
                try:
                    json.loads(message_content)
                except json.JSONDecodeError as e:
                    self.log_message(f"❌ Invalid JSON: {e}")
                    return
            
            self.mqtt_connection.publish(
                topic=topic,
                payload=message_content,
                qos=mqtt.QoS.AT_LEAST_ONCE)
            
            self.log_message(f"📤 Published to '{topic}': {message_content[:50]}{'...' if len(message_content) > 50 else ''}")
            
        except Exception as e:
            self.log_message(f"❌ Publish failed: {e}")
    
    def toggle_auto_publish(self):
        """Toggle auto publishing"""
        if self.auto_publish_active:
            self.auto_publish_active = False
            self.auto_publish_btn.config(text="🔄 Start Auto Publish")
            self.log_message("⏹️ Auto publish stopped")
        else:
            try:
                interval = float(self.interval_var.get())
                if interval < 0.1:
                    messagebox.showwarning("Invalid Interval", "Interval must be at least 0.1 seconds")
                    return
                
                self.auto_publish_active = True
                self.auto_publish_btn.config(text="⏹️ Stop Auto Publish")
                self.log_message(f"▶️ Auto publish started (every {interval}s)")
                
                self.auto_publish_thread = threading.Thread(
                    target=self._auto_publish_worker, args=(interval,), daemon=True)
                self.auto_publish_thread.start()
                
            except ValueError:
                messagebox.showwarning("Invalid Interval", "Please enter a valid number")
    
    def _auto_publish_worker(self, interval):
        """Worker thread for auto publishing"""
        while self.auto_publish_active and self.is_connected:
            self._publish_message()
            time.sleep(interval)
    
    def on_closing(self):
        """Handle window closing"""
        if self.auto_publish_active:
            self.auto_publish_active = False
        
        if self.is_connected:
            self.disconnect()
        
        self.root.destroy()
    
    def run(self):
        """Start the GUI application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

if __name__ == "__main__":
    app = MQTTPublisherGUI()
    app.run()
