# morphoLogic

## morphoLogicEngine

### CMD

The package name is `morphologic-server`, but the name of the program is `morphoLogic`.

- `morphologic start` — starts the server
  - `-l` or `--log` — enable logging
- `morphologic shell` — drop into async-aware interactive shell without running the server
- `morphologic seed` — populatea the database with test objects and areas

### CLI

The CLI has some basic functions. When the morphoLogic Server is run by `morphologic start` the CLI will start altogether.

- `stop` — a command to stop the server
- `detach` — detaches (turns off) the CLI, the server keeps running
- `debug` — runs **debugpy** at port `5678`
- `shell` — drop into async-aware interactive shell. Logging is paused
  - `quit()` to turn off the shell (logging will resume if was enabled)

## morphoLogicClient

Built on Godot
