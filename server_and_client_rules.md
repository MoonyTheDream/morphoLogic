# Communication between Server and Clinet
Type: *JSON*

## HANDSHAKE
*In handshake topic:*
client -> "system_message": "REQUEST_SERVER_CONNECTION"
server -> {"system_message": "TOPIC_CREATED_SEND_HANDSHAKE_THERE", "client_topic_handoff": <topic>}
*In handled topic:*
client -> "system_message": "HANDSHAKE_DEDICATED_TOPIC"
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