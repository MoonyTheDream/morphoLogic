# Communication between Server and Client examples

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
