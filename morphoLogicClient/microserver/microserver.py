import socket
import threading
# import sys
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError

HOST = "127.0.0.1"
PORT = 6164

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
PRODUCER_CONFIG = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,

    # Fixed properties
    'acks': 'all'
}
CONSUMER_CONFIG = {
    # User-specific properties that you must set
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,

    # Fixed properties
    'group.id':          'kafka-python-getting-started',
    'auto.offset.reset': 'earliest'
}

# 1) Create Producer and Consumer
producer = Producer(PRODUCER_CONFIG)
consumer = Consumer(CONSUMER_CONFIG)

# Subscribe to topic
TOPIC = "quickstart-events"
consumer.subscribe([TOPIC])

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
        

def produce_message(message):
    """
    Send a message to Kafka
    """
    try:
        # Asynchronous produce; if needed, handle delivery reports with callbacks
        producer.produce (TOPIC, value=message)
        producer.poll(0)
        print(f"[PY SERVICE] Produced message to {TOPIC}: {message}")
    except KafkaException as e:
        print(f"[PY SERVICE] KafkaException while producing: {e}")
        
def consume_message():
    """
    Consume one message (non-blocking)
    """
    # Poll with a short timeout
    msg = consumer.poll(0.1)
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
    
    
def tcp_server():
    """
    Start a TCP server that listens for connections from Godot
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"[PY SERVICE] Kafka service listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            print(f"[PY SERVICE] Connection from {addr}")
            # Handle connection in a seperate thread
            client_thread = threading.Thread(target=handle_client_connection, args=(conn,))
            client_thread.start()

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
            