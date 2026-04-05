# Communication between Server and Clinet

Type: **JSON**

## Revamped HANDSHAKE
<!-- -> [CLIENT][serverGeneralTopic]"system_message":"YO_ANYBODY_HOME?" // at launch, to verify connection
-> [SERVER][clientsGeneralTopic]"system_message":"UP_AND_RUNNING" 
Może jednak niepotrzebne, próba loginu tym jest -->
**1. CLIENT → `serverGeneralTopic`**

```json
{ "username": "<username>", "system_message": "ITS'A_ME_MARIO" }
```

> After login. Username is attached to every subsequent message.

**2. SERVER → `clientsGeneralTopic`**

```json
{ "system_message": "SHH_LET'S_TALK_IN_PRIVATE", "SHH_LET'S_TALK_IN_PRIVATE": "<dedicated_topic>" }
```

> Server assigns the client a private topic.

**3. CLIENT → `serverGeneralTopic`**

```json
{ "system_message": "WALLS_HAVE_EARS_GOT_IT" }
```

> Client confirms it has subscribed to the private topic.

**4. SERVER → `<dedicated_client_topic>`**

```json
{ "system_message": "CAN_YOU_HEAR_ME?" }
```

> Server tests the private channel.

**5. CLIENT → `serverGeneralTopic`**

```json
{ "system_message": "LOUD_AND_CLEAR" }
```

> Handshake complete.
<!-- -> [SERVER][<dedicated_client's_topic>]"system_message":"PERFECT_LET_US_TALK_BUSINESS_THEN" -->

## Client -> Server

```json
{
  "metadata": {
    "username": "<username>",
    "client_version": "<client_version>",
    "timestamp": "<timestamp>",
  },
  "payload": {
    "type": "user_input" | "system_message",
    "message": "<the_message>",
    "content": "<optional_content_for_the_message>"
  }
}
```

## Server -> Client

```json
{
  "metadata": {
    "to_user": "<name_of_the_target_user>",
    "server_version": "<client_version>",
    "timestamp": "<timestamp>"
  },
  "payload": {
    "message": "<the_message>",
    "content": "<optional_content_for_the_message>",
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
```

## Colors

NAMES = [color=medium_turquoise]
INFO (positive) = [color=yellow_green]
WARNING = [color=gold]
ERROR = [color=tomato]
