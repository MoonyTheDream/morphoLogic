# Communication between Server and Clinet
Type: *JSON*

## HANDSHAKE (type:content of payload)
client in *serverHandshakeTopic* -> "system_message": "REQUEST_SERVER_CONNECTION"
server in *clientHandshakeTopic* -> {"CLIENT_TOPIC_HANDOFF": "<dedicated_topic>"}
client in *serverGeneralTopic* -> "system_message": "HANDSHAKE_GLOBAL_TOPIC"
server in <dedicated_topic> -> "server_message": "ACK"

In case of not receiving "ACK" message after a timeout Godot will send an error message back to *serverHandshakeTopic*



## Client -> Server
<!-- {
  "metadata": {
    "source": "client",
    "username": "<username>",
    "client_version": "<client_version>",
    "timestamp": "<timestamp>",
    "client_ip": "<client.ip>"
  },
  "payload": {
    "type": "<client_input|system_message>",
    "content": "<the actual payload>"
  }
} -->

{
  "metadata": {
    "source": "client",
    "username": "<username>",
    "client_version": "<client_version>",
    "timestamp": "<timestamp>",
    "client_ip": "<client.ip>"
  },
  "payload": {
    "user_input": "<the_message>",
    "system_message": "<the_message>",
    "content": "<optional_content_for_the_message>"
  }
}
  <!-- "client_input": "<string sent by an user>",
  "system_message": "optional system message like 'HANSHAKE'" // created only by microserver -->
## Server -> Client
<!-- {
  "metadata": {
    "source": "<server/microserver>",
    "to_user": "<name_of_the_target_user>",
    "server_version": "<client_version>",
    "timestamp": "<timestamp>"
  },
  "payload": {
    "type": "<system_message|direct_message|objects>"
    "content": { 
      "id_of_object_01": {
        "value_01": "value",
        "value_02": 5
      },
      "id_od_object_02" :{
        "value_01": "some_value",
        "value_02": 0
      }
    }
  }
} -->
{
  "metadata": {
    "source": "<server/microserver>",
    "to_user": "<name_of_the_target_user>",
    "server_version": "<client_version>",
    "timestamp": "<timestamp>"
  },
  "payload": {
    "server_message": "<the_message>",
    "direct_message": "<the message wo show on client directly>",
    "content": "<optional_content_for_the_message>"
    "objects": { 
      "id_of_object_01": {
        "value_01": "value",
        "value_02": 5
      },
      "id_od_object_02" :{
        "value_01": "some_value",
        "value_02": 0
      }
    }
  }
}
## Colors
NAMES = [color=medium_turquoise]
INFO (positive) = [color=yellow_green]
WARNING = [color=gold]
ERROR = [color=tomato]


## Godot -> Microserver requests

Subscribing to new topic by client
"system_message": "MICROSERVER_SUBSCRIBE"
"MICROSERVER_SUBSCRIBE_TO": "<topic>"

Setting topic to produce to:
"system_message": "MICROSERVER_PRODUCE_TO"
"produce_topic": "<the topic>"



                                          morphoLogicClient
morphoLogicEngine(server) <-> Kafka <-> (microserver <-> Godot)