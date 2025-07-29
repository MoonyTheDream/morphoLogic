# Communication between Server and Clinet
Type: *JSON*

## Revamped HANDSHAKE
<!-- -> [CLIENT][serverGeneralTopic]"system_message":"YO_ANYBODY_HOME?" // at launch, to verify connection
-> [SERVER][clientsGeneralTopic]"system_message":"UP_AND_RUNNING" 
Może jednak niepotrzebne, próba loginu tym jest -->
-> [CLIENT][serverGeneralTopic]"username":<username>; "system_message":"ITS'A_ME_MARIO" // after user log in. Username attached to each message from now on
-> [SERVER][clientsGeneralTopic]"sytem_message":"SHH_LET'S_TALK_IN_PRIVATE"; "SHH_LET'S_TALK_IN_PRIVATE": <dedicated_client's_topic>
-> [CLIENT][serverGeneralTopic]"system_message":"WALLS_HAVE_EARS_GOT_IT" // after succsessful subscribing to new topic
-> [SERVER][<dedicated_client's_topic>]"system_message":"CAN_YOU_HEAR_ME?"
-> [CLIENT][serverGeneralTopic]"system_message":"LOUD_AND_CLEAR"
<!-- -> [SERVER][<dedicated_client's_topic>]"system_message":"PERFECT_LET_US_TALK_BUSINESS_THEN" -->


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
    "user_input": "<the_message>",
    "system_message": "<the_message>",
    "content": "<optional_content_for_the_message>"
  }
}
## Server -> Client
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
