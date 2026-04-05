from morphologic_server.services.messages import ClientMessage

def test_valid_client_message():
    good = {
        "metadata": {
            "username": "testuser",
            "client_version": "0.1",
            "timestamp": "1991-03-19 15:04:00"
        },
        "payload": {
            "type": "user_input",
            "message": "rozejrzyj się",
        }
    }
    msg = ClientMessage.model_validate(good)
    assert msg.metadata.username == "testuser"
    assert msg.metadata.client_version == "0.1"
    assert msg.metadata.timestamp == "1991-03-19 15:04:00"
    assert msg.payload.type == "user_input"
    assert msg.payload.message == "rozejrzyj się"
    assert msg.payload.content is None  # optional field, wasn't provided
