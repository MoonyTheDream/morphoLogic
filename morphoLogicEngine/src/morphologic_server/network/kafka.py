"""
Initializing Kafka connection and creating context manager for
Producer, Consumer and Admin
"""
import os
import json

from time import sleep

from confluent_kafka import Producer, Consumer, KafkaException  # , KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

from ..utils.logger import logger
from ..utils.time_helpers import get_gmt_time
from ..config import settings as _SETTINGS

BOOTSTRAP_SERVER = os.getenv(
    "KAFKA_BOOTSTRAP_SERVER", _SETTINGS.get("kafka_server", "localhost:9092"))
GENERAL_TOPIC = os.getenv("KAFKA_GENERAL_TOPIC", _SETTINGS.get(
    "generalTopic", "serverGeneralTopic"))
CLIENT_HANDSHAKE_TOPIC = os.getenv("KAFKA_HANDSHAKE_TOPIC", _SETTINGS.get(
    "handshakeTopic", "clientHandshakeTopic"))
SERVER_HANDSHAKE_TOPIC = os.getenv("KAFKA_HANDSHAKE_TOPIC", _SETTINGS.get(
    "serverandshakeTopic", "serverHandshakeTopic"))

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

            self.subscribe_to_topics([GENERAL_TOPIC, SERVER_HANDSHAKE_TOPIC])

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

    def __exit__(self, exc_type, exc_value, traceback):
        """Cleanup: close consumer, flush producer"""
        if self.consumer:
            self.consumer.close()
            logger.info('Closed Kafka consumer.')

        if self.producer:
            self.producer.flush(3)  # ensure all queued messages are delivered
            logger.info("Flushed Kafka producer.")

    def create_new_topics(self, topics: list[str]) -> list[str]:
        """
        KONIECZNIE TRZEBA TO ZROBIĆ JAKO THREAD LUB ASYNC JAKIŚ
        Creating a new topic. If it already exists we just log this info and continue.
        """
        new_topics_list = []
        b_topic = ""
        # Check if topics already exists
        for topic in topics:
            if not self._topic_exists(topic):
                new_topics_list.append(NewTopic(topic))

        if new_topics_list:
            dict_future_topics = self.admin.create_topics(new_topics_list)
            # Check futures for validating
            try:
                for topic, future_topic in dict_future_topics.items():
                    b_topic = topic
                    future_topic.result()
                logger.info('Created Kafka topic "%s"', topic)
            except Exception:
                logger.exception('Failed to create topic "%s".', b_topic)
                raise  # re-raise to exit the context manager
        new_topics_list = [topic.topic if isinstance(topic, NewTopic) else topic for topic in new_topics_list]
        return new_topics_list

    def _topic_exists(self, topic: str) -> bool:
        metadata = self.admin.list_topics()
        return topic in metadata.topics

    def subscribe_to_topics(self, topics: list[str]):
        """Subscribes the class' Kafka Consumer to specific topic."""
        self.consumer.subscribe(topics)
        logger.info('Subscribed to Kafka topics "%s"', topics)

    def update_subscription(self, topics: list[str]):
        """Checks if listed topics are already subscribed and if not, subscribes"""
        current_subscription = self.consumer.assignment()
        current_subscription = [
            topic_partition.topic for topic_partition in current_subscription]

        to_update = []
        for topic in topics:
            if topic not in current_subscription:
                to_update.append(topic)
        
        if len(to_update) > 0:
            to_update += current_subscription
            self.subscribe_to_topics(to_update)


    def unsubscribe_from_topics(self, topics: list[str]):
        """Unsubscribes the class' Kafka Consumer from specific topic."""
        self.consumer.unsubscribe(topics)
        logger.info('Unsubscribed from Kafka topics "%s"', topics)

    def send_data_to_user(
        self,
        topic: str,
        username: str,
        data: dict = None,
        direct_message="",
        system_message=""
    ):
        """Wrapper for sending message. Add more preferences here later if needed"""
        if data is None:
            data = {}
        data.update({
            "dicrect_message": direct_message,
            "system_message": system_message
        })
        wrapped_data = self._add_metadata(data, username)
        wrapped_data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.producer.produce(topic, value=wrapped_data)  # no key, as:
        # adding key might result in some consumers not consuming their message as each
        # consumer get's it's own partition when there's more that one consumers
        # and there might be more than one producer and consumer when multiple users will try to join
        logger.debug('Produced message to %s: "%s"', topic, wrapped_data)
        
    def _add_metadata(self, data: dict, username: str) -> dict:
        """
        Wraps metadata data to the dictionary.
        """
        data.update(
            {
                "metadata": {
                    "source": "server",
                    "to_user": username,
                    "server_version": _SETTINGS.get("server_version", "ERROR"),
                    "timestamp": get_gmt_time()
                }
            }
        )
        return data

    # def consume_message(self) -> dict:
    #     """Wrapper helper consuming one message from Kafka"""
    #     try:
    #         msg = self.consumer.consume(num_messages=1, timeout=-1)
    #         if msg:
    #             msg = msg[0]

    #             if msg.error():
    #                 logger.warning(
    #                     "Error consuming message: %s", msg.error().str())
    #                 # WIP
    #                 # FUTURE ADDITIONAL HANDLING
    #                 return None

    #             kafka_msg = msg.value().decode("utf-8")
    #             logger.debug('Consumed message from Kafka: "%s"', kafka_msg)
    #             kafka_msg = json.loads(kafka_msg)
    #             return kafka_msg
    #     except Exception:
    #         logger.exception("Error consuming message from Kafka")
