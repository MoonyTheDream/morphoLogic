"""
Initializing Kafka connection and creating context manager for
Producer, Consumer and Admin
"""

from __future__ import annotations

import asyncio
import os
import json

from time import sleep
from typing import TYPE_CHECKING

from confluent_kafka import Producer, Consumer, KafkaException
from confluent_kafka.admin import AdminClient
from confluent_kafka.cimpl import NewTopic


if TYPE_CHECKING:
    from morphologic_server.awakening import MorphoLogicHeart

from morphologic_server.utils.time_helpers import get_gmt_time


# 888    d8P            .d888 888
# 888   d8P            d88P"  888
# 888  d8P             888    888
# 888d88K      8888b.  888888 888  888  8888b.
# 8888888b        "88b 888    888 .88P     "88b
# 888  Y88b   .d888888 888    888888K  .d888888
# 888   Y88b  888  888 888    888 "88b 888  888
# 888    Y88b "Y888888 888    888  888 "Y888888
#                   w                w
# .d8b .d8b. 8d8b. w8ww .d88b Yb dP w8ww    8d8b.d8b. .d88 8d8b. .d88 .d88 .d88b 8d8b
# 8    8' .8 8P Y8  8   8.dP'  `8.   8      8P Y8P Y8 8  8 8P Y8 8  8 8  8 8.dP' 8P
# `Y8P `Y8P' 8   8  Y8P `Y88P dP Yb  Y8P    8   8   8 `Y88 8   8 `Y88 `Y88 `Y88P 8
#                                                                     wwdP
class KafkaConnection:
    """
    Context manager that set up a Kafka Connection, give acces to Admin, Producer and Consumer
    and exposing some methods like create new topic etc.
    """

    def __init__(self, heart: MorphoLogicHeart):
        self.heart = heart
        self.log = self.heart.log.getChild("kafka") 
        self.admin: AdminClient
        self.producer: Producer
        self.consumer: Consumer
        # self.general_topic = SERVER_GENERAL_TOPIC

    def _establish_kafka_connection(
        self, max_retries=3, wait_time=0.5
    ):
        """
        Verifies the connection to Kafka by requesting cluster metadata.
        Retries a few times before giving up.
        """
        for attempt in range(max_retries):
            try:
                cluster_metadata = self.admin.list_topics(timeout=5)
                if cluster_metadata.brokers:
                    self.log.debug("Kafka connected: %d broker(s).", len(cluster_metadata.brokers))
                    return
                else:
                    raise KafkaException("No brokers found in cluster metadata.")
            except KafkaException:
                if attempt < max_retries - 1:
                    self.log.exception("Kafka connection failed. Attempt %d/%d.", attempt+1, max_retries)
                    sleep(wait_time)
                else:
                    self.log.exception(
                        "Kafka connection failed after %d retries.", max_retries
                    )
                    raise RuntimeError(
                        "Kafka cluster is unreachable. Check if the broker is running."
                    )
                    
    def _delivery_report(self, err, msg):
        """Called once for each message produced to indicate delivery result.
           Triggered by poll() or flush()."""
        if err is not None:
            self.log.error('Delivery FAILED to %s: %s', msg.topic(), err)
        else:
            self.log.debug('Delivered to %s [p%s]', msg.topic(), msg.partition())

    def __enter__(self):
        """
        Handles the creation of Kafka Admin Client, Producer, and Consmer
        """
        try:
            admin_conf = {"bootstrap.servers": self.heart.settings.KAFKA_SERVER, **self._ssl_conf()}
            self.admin = AdminClient(admin_conf)
            self._establish_kafka_connection()

            producer_conf = {"bootstrap.servers": self.heart.settings.KAFKA_SERVER, "acks": "all", **self._ssl_conf()}
            self.producer = Producer(producer_conf)

            consumer_conf = {
                "bootstrap.servers": self.heart.settings.KAFKA_SERVER,
                "group.id": self.heart.settings.KAFKA_GROUP_ID,
                "auto.offset.reset": "latest",
                "enable.partition.eof": False,  # we'll be hitting end of partition quite often
                **self._ssl_conf(),
            }
            self.consumer = Consumer(consumer_conf)

            # self.subscribe_to_topics([self.heart.settings.SERVER_GENERAL_TOPIC, self.heart.settings.SERVER_HANDSHAKE_TOPIC])

            return self

        except KafkaException:
            self.log.exception("Error setting up Kafka resources.")
            raise
        except Exception as e:
            self.log.exception("Error setting up Kafka resources: %s", e)
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        """Cleanup: close consumer, flush producer"""
        if self.consumer:
            self.consumer.close()
            self.log.info("Closed Kafka consumer.")

        if self.producer:
            self.producer.flush(3)  # ensure all queued messages are delivered
            self.log.info("Flushed Kafka producer.")
            
    def _ssl_conf(self) -> dict:
        if not self.heart.settings.KAFKA_SECURITY_PROTOCOL:
            return {}
        c = {"security.protocol": self.heart.settings.KAFKA_SECURITY_PROTOCOL}
        if self.heart.settings.KAFKA_SSL_CA_LOCATIONS:
            c["ssl.ca.location"] = self.heart.settings.KAFKA_SSL_CA_LOCATIONS
        return c

    async def create_new_topics(self, topics: list[str]) -> list[str]:
        """
        Creating a new topic. If it already exists we just log this info and continue.
        """
        new_topics_list = []
        b_topic = ""

        cluster_metadata = await asyncio.to_thread(self.admin.list_topics)
        current_topics = cluster_metadata.topics

        for topic in topics:
            if topic not in current_topics:
                new_topics_list.append(NewTopic(topic))

        if new_topics_list:
            dict_future_topics = self.admin.create_topics(new_topics_list)
            try:
                for topic, future_topic in dict_future_topics.items():
                    b_topic = topic
                    await asyncio.wrap_future(future_topic)
                    self.log.info('Created Kafka topic "%s"', topic)
            except Exception:
                self.log.exception('Failed to create topic "%s".', b_topic)
                raise  # re-raise to exit the context manager
        new_topics_list = [
            topic.topic if isinstance(topic, NewTopic) else topic
            for topic in new_topics_list
        ]
        return new_topics_list

    def subscribe_to_topics(self, topics: list[str]):
        """Subscribes the class' Kafka Consumer to specific topic."""
        self.consumer.subscribe(topics)
        self.log.info('Subscribed to Kafka topics "%s"', topics)

    def update_subscription(self, topics: list[str]):
        """Checks if listed topics are already subscribed and if not, subscribes"""
        current_subscription = self.consumer.assignment()
        current_subscription = [
            topic_partition.topic for topic_partition in current_subscription
        ]

        to_update = []
        for topic in topics:
            if topic not in current_subscription:
                to_update.append(topic)

        if len(to_update) > 0:
            to_update += current_subscription
            self.subscribe_to_topics(to_update)


    def send_data_to_user(
        self,
        topic: str,
        username: str,
        server_message: str = "",
        content: str = "",
        direct_message: str = "",
        objects: dict = {},
    ):
        """Wrapper for sending message. Add more preferences here later if needed"""
        # if data is None:
        payload_data: dict = {
            "payload": {
                "server_message": server_message,
                "content": content,
                "direct_message": direct_message,
                "objects": objects,
            }
        }
        self._add_metadata(payload_data, username)
        wrapped_data = json.dumps(payload_data, ensure_ascii=False).encode("utf-8")
        self.producer.produce(topic, value=wrapped_data, on_delivery=self._delivery_report)  # no key, as:
        # adding key might result in some consumers not consuming their message as each
        # consumer get's it's own partition when there's more that one consumers
        # and there might be more than one producer and consumer when multiple users will try to join
        self.log.debug('Produced message to %s: "%s"', topic, payload_data)
        self.producer.poll(0)  # trigger delivery report callbacks

    def health_status(self):
        """Just a quick 'UP_AND_RUNNING' message to Kafka"""
        payload_data = {
            "payload": {
                "server_message": "UP_AND_RUNNING",
                "content": "",
                "direct_message": "",
                "objects": None,
            }
        }
        self._add_metadata(payload_data, "")
        wrapped_data = json.dumps(payload_data, ensure_ascii=False).encode("utf-8")
        self.producer.produce(self.heart.settings.CLIENTS_GENERAL_TOPIC, value=wrapped_data, on_delivery=self._delivery_report)
        self.log.debug('Produced message to %s: "%s"', self.heart.settings.CLIENTS_GENERAL_TOPIC, payload_data)
        self.producer.poll(0)  # trigger delivery report callbacks

    def _add_metadata(self, data: dict, username: str) -> dict:
        """
        Wraps metadata data to the dictionary.
        """
        data.update(
            {
                "metadata": {
                    "source": "server",
                    "to_user": username,
                    "server_version": self.heart.settings.SERVER_VERSION,
                    "timestamp": get_gmt_time(),
                }
            }
        )
        return data
