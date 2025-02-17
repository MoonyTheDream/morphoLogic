import socket
# import threading
# import sys
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient

class KafkaHandler():
    BOOTSTRAP_SERVER = "localhost:9092"
    PRODUCER_TOPIC = 'serverGlobalTopic'
    producer_config = {
        'bootstrap.servers': BOOTSTRAP_SERVER,

        # Fixed properties
        'acks': 'all'
    }
    consumer_config = {
        # User-specific properties that you must set
        'bootstrap.servers': BOOTSTRAP_SERVER,

        # Fixed properties
        'group.id':          '', # MUST BE updated
        'auto.offset.reset': 'earliest'
    }
    
    def __init__(self, client_id):
        # AdminClient
        self.admin = AdminClient({'bootstrap.servers': self.BOOTSTRAP_SERVER})
        # Producer
        self.producer = Producer(self.producer_config)
        # Consumer
        self.consumer_config["group.id"] = client_id
        self.consumer = Consumer(self.consumer_config)
        # Create new topic for this client
        self.topic = self._request_topic(client_id)
        
        # ************** WIERDO
        del self.admin # There's no point to keep it at this point. <- That's a fair point.
        # ************** WEIRDO
        
        # Subscribe to the topic
        self.consumer.subscribe([self.topic])
        
    def _request_topic(self, topic_id):
        dict_future_topics = self.admin.create_topics([topic_id])
        try:
            dict_future_topics[topic_id].result() # Wait for confirmation
            print(f'Topic {topic_id} created successfully.')
        except Exception as e:
            print(f'Failed to create topic {topic_id}: {e}')
        
        return True
    
    def consume_message(self):
        """
        Consume one message (non-blocking)
        """
        # Poll with a short timeout
        msg = self.consumer.poll(0.1)
        if msg is None:
            return ""
        
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                # Reached end of partition
                return ""
            else:
                print(f"[PY SERVICE] Error while consuming: {msg.error()}")
                return ""
        else:
            # We have a valid message
            msg_val = msg.value().decode("utf-8")
            print(f"[PY SERVICE] Consumed message from {msg.topic()}: {msg_val}")
            return msg_val
        
    def produce_message(self, message):
        """
        Send a message to Kafka
        """
        try:
            # Asynchronous produce; if needed, handle delivery reports with callbacks
            # key is a name of topic, as Server then will send optional naswer to this topic.
            self.producer.produce (self.PRODUCER_TOPIC, key=self.topic, value=message)
            # producer.poll(0)
            print(f"[PY SERVICE] Produced message to {TOPIC}: {message}")
        except KafkaException as e:
            print(f"[PY SERVICE] KafkaException while producing: {e}")

class TCPMicroserver():
    
    HOST = "127.0.0.1"
    PORT = 6164
    
    def __init__(self):
        """
        Start a TCP server that listens for connections from Godot
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((self.HOST, self.PORT))
        s.listen()
        print(f"[PY SERVICE] Kafka service listening on {HOST}:{PORT}")
        while True:
            self.conn, addr = s.accept()
            print(f"[PY SERVICE] Connection from {addr}")

    def handle_client_connection(conn):
        """
        Handle incoming commands from Godot over TCP
        Commands might be:
        - "PRODUCE <message>"
        - "CONSUME"
        - "EXIT"
        """
        try:
            while True:
                data = conn.recv(1024)
                # print(data)
                if not data:
                    break # Clinet disconnected
                
                message = data.decode("utf-8").strip()
                print(message)
                if not message:
                    pass
                
                seperated_message = message.split(" ", 1) # Split into at most 2 parts
                cmd = seperated_message[0].upper()
                
                if cmd == "PRODUCE" and len (seperated_message) == 2:
                    conn.sendall(b"RECEIVED")
                    message = seperated_message[1]
                    produce_message(message)
                elif cmd == "CONSUME" and len(seperated_message) == 1:
                    conn.sendall(b"RECEIVED")
                    msg = consume_message()
                    response = msg if msg else ""
                    conn.sendall(response.encode("utf-8") + b"\n")
                elif cmd == "EXIT":
                    conn.sendall(b"RECEIVED")
                    break
                else:
                    # Unknown command
                    conn.sendall(b"RECEIVED")
                    conn.sendall(b"ERR UNKNOWN COMMAND\n")
                    
        except Exception as e:
            print(f"Error in client connection: {e}")
            
        finally:
            conn.close()
            

def main():
    try:
        tcp_server()
    except KeyboardInterrupt:
        print("[PY SERVICE] Shutting down service.")
    finally:
        # The Cleanup
        consumer.close()
        producer.flush(3)
        
if __name__ == "__main__":
    main()
            