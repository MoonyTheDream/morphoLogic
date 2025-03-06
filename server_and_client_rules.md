# Communication between Server and Clinet
Type: *JSON*
## Client -> Server
{
  "auth": {
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
  "auth": {
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