"""
Initializing Kafka connection and creating context manager for
Producer, Consumer and Admin
"""
import os

from time import sleep

from confluent_kafka import Producer, Consumer, KafkaException  # , KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

from ..utils.logger import logger
from ..config import settings as _SETTINGS

BOOTSTRAP_SERVER = os.getenv(
    "KAFKA_BOOTSTRAP_SERVER", _SETTINGS.get("kafka_server", "localhost:9092"))
GENERAL_TOPIC = os.getenv("KAFKA_GENERAL_TOPIC", _SETTINGS.get(
    "generalTopic", "serverGlobalTopic"))
HANDSHAKE_TOPIC = os.getenv("KAFKA_HANDSHAKE_TOPIC", _SETTINGS.get(
    "handshakeTopic", "serverHandshakeTopic"))

####################################################################################################
# Kafka Context Manager
####################################################################################################

class KafkaConnection:
    """
    Context manager that set up a Kafka Connection, give acces to Admin, Producer and Consumer
    and exposing some methods like create new topic etc.
    """
    def __init__(self, bootstrap_server: str = BOOTSTRAP_SERVER):
        self.admin: AdminClient = None
        self.producer: Producer = None
        self.consumer: Consumer = None
        self.bootstrap_server = bootstrap_server
        # self.general_topic = GENERAL_TOPIC
        
    def _establish_kafka_connection(self, admin: AdminClient, max_retries=4, wait_time=1):
        """
        Verifies the connection to Kafka by requesting cluster metadata.
        Retries a few times before giving up.
        """
        for attemt in range(max_retries):
            try:
                cluster_metadata = admin.list_topics(timeout=5)
                if cluster_metadata.brokers:
                    logger.debug("Kafka connection verified.")
                    return
            except KafkaException as e:
                if attemt < max_retries - 1:
                    logger.warning("Kafka connection failed. Retrying.")
                    sleep(wait_time)
                else:
                    logger.error(
                        "Kafka connection failed after %d retries.", max_retries)
                    raise RuntimeError(
                        "Kafka cluster is unreachable. Check if the broker is running.") from e
    
    def __enter__(self):
        """
        Handles the creation of Kafka Admin Client, Producer, and Consmer
        """
        try:
            admin_conf = {
                'bootstrap.servers': BOOTSTRAP_SERVER
            }
            self.admin = AdminClient(admin_conf)
            self._establish_kafka_connection(self.admin)

            producer_conf = {
                'bootstrap.servers': BOOTSTRAP_SERVER,
                'acks': 'all'
            }
            self.producer = Producer(producer_conf)

            consumer_conf = {
                'bootstrap.servers': BOOTSTRAP_SERVER,
                'group.id': "morphoLogicServerGroup",
                'auto.offset.reset': 'earliest',
                "enable.partition.eof": False  # we'll be hitting end of partition quite often
            }
            self.consumer = Consumer(consumer_conf)

            self.subscribe_to_topics([GENERAL_TOPIC, HANDSHAKE_TOPIC])
            
            # kafka_resources = {
            #     "admin": admin,
            #     "producer": producer,
            #     "consumer": consumer,
            # }
            return self
        
        except KafkaException:
            logger.exception("Error setting up Kafka resources.")
            raise
        except Exception:
            logger.exception("Error setting up Kafka resources.")
            raise
        
    def __exit__ (self, exc_type, exc_value, traceback):
        """Cleanup: close consumer, flush producer"""
        if self.consumer:
            self.consumer.close()
            logger.info('Closed Kafka consumer.')

        if self.producer:
            self.producer.flush(3)  # ensure all queued messages are delivered
            logger.info("Flushed Kafka producer.")
                    
    def create_new_topics(self, topics: list[str]):
        """Creating a new topic. If it already exists we just log this info and continue."""
        new_topics_list = []
        for topic in topics:
            if not self._topic_exists(topic):
                new_topics_list.append = NewTopic(topic)
        dict_future_topics = self.admin.create_topics(new_topics_list)
        try:
            for topic, future_topic in dict_future_topics.items():
                future_topic.result()
            logger.info('Created Kafka topic "%s"', topic)
        except Exception:
            logger.exception('Failed to create topic %s.', topic)
            raise  # re-raise to exit the context manager
        
    def _topic_exists(self, topic: str) -> bool:
        metadata = self.admin.list_topics()
        return topic in metadata.topics

    def subscribe_to_topics(self, topics: list[str]):
        """Subscribes the class' Kafka Consumer to specific topic."""
        self.consumer.subscribe(topics)
        logger.info('Subscribed to Kafka topics "%s"', topics)
        
    def unsubscribe_from_topics(self, topics: list[str]):
        """Unsubscribes the class' Kafka Consumer from specific topic."""
        self.consumer.unsubscribe(topics)
        logger.info('Unsubscribed from Kafka topics "%s"', topics)







