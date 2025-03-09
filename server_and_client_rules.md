# Communication between Server and Clinet
Type: *JSON*

## HANDSHAKE
*In handshake topic:*
client -> "system_message": "REQUEST_SERVER_CONNECTION"
server -> {"system_message": "TOPIC_CREATED_SEND_HANDSHAKE_THERE", "client_topic_handoff": <topic>}
*In globalServerTopic*
client -> "system_message": "HANDSHAKE_GLOBAL_TOPIC"
*In handled topic:*
server -> "system_message": "ACK"



## Client -> Server
{
  "metadata": {
    "source": "client"
    "username": "<username>",
    "client_version": "<client_version>",
    "timestamp": "<timestamp>",
    "client_ip": "<client.ip>"
  },
  "client_input": "<string sent by an user>",
  "system_message": "optional system message like 'HANSHAKE'" // created only by microserver
}
## Server -> Client
{
  "metadata": {
    "source": "<server/microserver>",
    "to_user": "<name_of_the_target_user>",
    "server_version": "<client_version>",
    "timestamp": "<timestamp>"
  },
  "direct_messages": ["strings to show on the client", "can be more than one"],
  "system_message": "optional system message like 'connected to server'",
  "obejcts": {
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