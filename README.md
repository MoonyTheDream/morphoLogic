# morphoLogicEngine
## CMD
The package name is "morphologic-server", but the name of the program is "morphoLogic".
- start the program
    - `morphologic start` command with optional `-l` for logging in console

## CLI
The CLI has some basic functions. When the morphoLogic Server is run by "morphologic start" the CLI will start altogether.

- `stop` - a command to stop the server
- `detach` - detaches (turns off) the CLI, the server keeps running

# morphoLogicClient
Built on Godot
## microserver
The microserver (python script) is automaticly run by a Godot Client. It's main purpose is to comunicate Client with Kafka (two-way communication)      