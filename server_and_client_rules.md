# Communication between Server and Clinet
Type: *JSON*

## HANDSHAKE (type:content of payload)
client in *serverHandshakeTopic* -> "system_message": "REQUEST_SERVER_CONNECTION"
server in *clientHandshakeTopic* -> {"client_topic_handoff": "<dedicated_topic>"}
client in *serverGeneralTopic* -> "system_message": "HANDSHAKE_GLOBAL_TOPIC"
server in <dedicated_topic> -> "server_message": "ACK"

In case of not receiving "ACK" message after a timeout Godot will send an error message back to *serverHandshakeTopic*



## Client -> Server
{
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
}
  <!-- "client_input": "<string sent by an user>",
  "system_message": "optional system message like 'HANSHAKE'" // created only by microserver -->
## Server -> Client
{
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
}
## Colors
NAMES = [color=medium_turquoise]
INFO (positive) = [color=yellow_green]
WARNING = [color=gold]
ERROR = [color=tomato]


## Godot -> Microserver requests

Subscribing to new topic by client
"system_message": "MICROSERVER_SUBSCRIBE"
"microserver_subscribe_to": "<topic>"

Setting topic to produce to:
"system_message": "MICROSERVER_PRODUCE_TO"
"produce_topic": "<the topic>"



                                          morphoLogicClient
morphoLogicEngine(server) <-> Kafka <-> (microserver <-> Godot)