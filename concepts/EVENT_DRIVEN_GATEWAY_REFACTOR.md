# Event-Driven Gateway Refactor

Moving Kafka from "the phone line between client and server" to "the server's internal
nervous system", and putting a **Gateway** in front of it.

**Status:** planned, not started.

**Warning:** this is a sizeable rework. The client transport changes (Kafka -> WebSocket),
the whole handshake protocol goes away, and `MessageHandler` gets dismantled. Do it on a branch.

**Overview:**

- Clients stop speaking Kafka. They speak **WebSocket** to a new **Gateway**. Kafka becomes **server-internal only**.
- Everything inside is **event-driven**: a command comes in, modules react, facts go out.
- **Postgres stays the source of truth.** `events.world` is kept on Kafka with long retention as a
  replayable "db before db" history — *without* going full event-sourcing (that's a rabbit hole I'm not jumping into yet).
- One process, **modular monolith**: Gateway + each module are asyncio tasks. Splittable into separate
  services later with no logic change — the discipline that buys that is "talk only through topics, share no memory".

---

## Why

Right now Kafka does two unrelated jobs tangled into one god-object (`MessageHandler._route`): it's the
client transport *and* the would-be internal plumbing. The tell is the outbound path creating
**a Kafka topic per username** in `_handshake_init` — Kafka used as a mailbox. Fine for 3 test clients,
falls over later (thousands of topics/partitions, metadata pressure), and fights the tool's grain.

The Gateway's whole reason to exist is to be the **wall** between the messy outside ("which client gets
this?") and the clean inside ("this happened in the world"). Get the wall right and weather / chat /
combat / NPCs are all just *another module subscribing to a topic*.

A MUD is multi-observer anyway — one sword swing, eight witnesses. Event fan-out isn't just tidy,
it's the shape of the domain.

## The shape

```text
                ┌──────────────────────── one process (TaskGroup) ──────────────────────────┐
  WS clients    │                                                                           │
  ─────────────▶│  GATEWAY (edge)           commands.player           MOVEMENT module       │
  (auth+input)  │  - WS server        ─────▶ (key=player_id)   ─────▶ own consumer + group  │
                │  - conn registry                                    validates via Memory  │
                │    player_id↔socket                                 writes DB             │
  ◀─────────────│  - ingress: WS->cmd                                 emits fact ─┐         │
  (pushed facts)│  - egress:  fact->WS ◀──────  events.world  ◀───────────────────┘         │
                │    routing: direct/        (key=player_id/area, long retention) ▲         │
                │    area/(broadcast)                                             │         │
                │                            WEATHER / NPC / regen modules ───────┘         │
                │                            each owns its own asyncio timer;               │
                │                            Kafka carries the fact, not the tick           │
                └───────────────────────────────────────────────────────────────────────────┘
                              Kafka = internal bus only │ Postgres = source of truth
```

**Components:**

- **Gateway** — `network/gateway.py`. The only thing that touches client sockets. A WebSocket server
  plus an in-memory `player_id ↔ socket` registry (this is what replaces topic-per-user). Two halves:
  - *ingress*: accept connection -> authenticate via `Memory.authenticate` -> on input, publish a command
    to `commands.player`, keyed by `player_id`.
  - *egress*: consume `events.world` -> apply a **routing policy** (direct -> actor, area -> everyone in a
    location, broadcast -> all clients, for announcements) -> push over the socket.
- **Modules** — `modules/`. Each a class with **its own consumer and its own `group.id`**, running its own
  consume loop as a task. `MovementModule` first: consume `commands.player`, validate + mutate via `Memory`,
  emit `PlayerMoved` (or `MoveRejected`) on `events.world`. Anything periodic owns its own `asyncio` timer.
- **Bus** — refactor of `KafkaConnection` (`network/kafka.py`). Drop the client-addressed `send_data_to_user`
  / `health_status`. Expose `publish(topic, event, key)` and a per-module `make_consumer(group_id, topics)`.
- **Heart** — `awakening.py`. Boots the gateway + module tasks, then idles until stop. No heartbeat ping:
  the live WebSocket *is* the liveness signal.

**Topics** (start small, split by domain only when volume demands):

- `commands.player` — imperative, may be rejected. Keyed by `player_id`.
- `events.world` — past-tense facts. Keyed by `player_id` / `area_id`. **Long retention** (`retention.ms=-1`
  or large, set via `NewTopic` config) — this is the kept event log.
- `commands.system` — later, for ad-hoc / admin one-offs ("force weather now").
- Gone: `serverGeneralTopic`, `clientsGeneralTopic`, `*HandshakeTopic`, every per-username topic.
- **No tick / heartbeat topic.** Timers are in-process; Kafka never carries "it's time", only "this happened".

**Two contracts, kept separate on purpose:**

- *External (client ↔ gateway)* — the WebSocket JSON, close to today's pydantic shape in `services/messages.py`.
  Lives at the edge, free to evolve without touching internals.
- *Internal (module ↔ module)* — a new envelope: `event_id`, `type` (discriminator, e.g. `PlayerMoved`),
  `occurred_at`, `actor` (player_id or `system`), `correlation_id` (ties a fact back to the command that caused
  it), `payload`. Pydantic discriminated union, in a new `events/` package.

## The rules that keep it honest

These are the invariants. Break one and I'm rebuilding the god-object.

- **Only the Gateway touches client connections.** Modules touch topics + DB, never a socket.
- **Each module = its own consumer group.** Same group -> modules *steal* each other's messages. Different groups
  -> each sees all matching messages. This is *the* Kafka concept to not get wrong.
- **Key player-scoped messages by `player_id`.** Same key -> same partition -> ordered per player, parallel across
  players. (Today's code deliberately omits keys — right for a broadcast topic, wrong for these.)
- **Edge feedback is eventual.** No blocking "ok" — the client is pushed the resulting fact. `correlation_id`
  lets the gateway *also* send a direct confirm/reject to the one who asked.
- **Kafka carries commands + facts that need reacting to — not triggers, not reads.** Timers are local
  `asyncio`. Current state (weather, etc.) is read straight from DB/memory. The bus carries the *result*,
  never the *trigger*. Not everything is an event.
- **Routing is a property of the event, not the module.** A module marks (or the gateway infers) the audience —
  direct / area / broadcast — but a module never names a client.
- **The domain module owns its DB write** (validate -> write -> emit). No separate after-the-fact persistence
  projection yet — modules need current state to validate.

## Steps

Each step ships and is testable on its own.

### Step 1 — Stand up the WebSocket Gateway

Build `network/gateway.py`: a `websockets` server task inside the existing TaskGroup in `cli.py`. A client
connects, sends credentials, gateway authenticates via `Memory.authenticate`, stores `player_id -> socket`.
On input it runs the **existing** logic (reuse `commands.handle_command` + `Memory`) and pushes the result
back. **No internal bus yet** — the only goal is proving the transport swap: same behaviour as today, over WS,
with an in-memory registry instead of per-user topics. WebSocket (not raw TCP) gives message framing for free,
so the manual `+ "\n"` framing in `Kafka.gd` goes away.

This collapses the whole handshake (`ITS'A_ME_MARIO` … `CAN_YOU_HEAR_ME?`), `_is_it_for_me_really`, and
topic-per-user.

### Step 2 — Slide the event bus in behind it

Add the internal event envelope (`events/`), create `commands.player` + `events.world`, extract
`MovementModule` (`modules/movement.py`) as its own task + consumer + group, moving the move logic out of the
gateway. Rewire the gateway: input -> publish to `commands.player`; consume `events.world` -> push to clients.
Prove the full loop for "go to X": **WS -> commands.player -> MovementModule -> events.world -> WS -> client.**
Once this one path works, every later feature is "another module + another event type".

### Step 3 — Self-spawned weather module

Add `modules/weather.py` with its **own `asyncio` timer** — no Kafka clock. On its own cadence it recomputes
weather and, *only when it meaningfully changes*, emits `WeatherChanged` on `events.world` keyed by area.
The gateway's **area** fan-out delivers it to clients in that area only. Current weather is just readable
state (in-memory on the module, or DB) that a player's `look` queries directly — a read, not an event.
(Area fan-out perf is untested — revisit if rooms get crowded.)

Proves: work no user triggered still reaches the right clients, with no shared clock.

## File map

- **New** `network/gateway.py` — WS server, connection registry, ingress/egress, auth. The edge.
- **New** `events/__init__.py` — internal command/event pydantic models (envelope + discriminated union).
- **New** `modules/movement.py`, later `modules/weather.py` — each a consumer-owning module class.
- **Refactor** `network/kafka.py` — `KafkaConnection` becomes the internal bus: drop `send_data_to_user` /
  `health_status`; add `publish(topic, event, key)` and `make_consumer(group_id, topics)`; keep producer /
  admin / `create_new_topics` (extend it to pass per-topic config for retention).
- **Rewrite** `awakening.py` — `awake()` boots bus + gateway + module tasks, then idles; new topic list.
- **Dissolve** `services/message_handler.py` — routing -> gateway (edge) + modules. Surroundings logic moves
  to a module / egress helper.
- **Split** `services/messages.py` — external WS protocol stays; internal protocol lives in `events/`.
- **Move** `game_logic/commands.py` — the parser stays reusable; the mutate-and-save body moves into `MovementModule`.
- **Edit** `config.py` — topic settings -> `COMMANDS_PLAYER_TOPIC` / `EVENTS_WORLD_TOPIC` / `COMMANDS_SYSTEM_TOPIC`;
  add `WS_HOST` / `WS_PORT`; drop the client / handshake / general topic settings.
- **Edit** `pyproject.toml` — add `websockets`.
- **Edit** `tests/test_messages.py` — update for the two contracts.
- **Client (Godot, separate repo)** — swap the Kafka GDExtension for a WebSocket client; drop
  `_is_it_for_me_really` and the handshake dance. Out of scope here but a hard dependency for end-to-end testing.

## Verification

1. **Step 1** — `morphologic start -l`; connect a throwaway `websockets` / `websocat` client, authenticate,
   send `go to <name>`, confirm the same feedback + surroundings as today arrive over WS. `kafka-topics --list`
   no longer shows per-user topics.
2. **Step 2** — run `kafka-console-consumer` (via the kafka container) on `commands.player` and `events.world`;
   send a move -> a command appears, then a `PlayerMoved` fact, then the client gets pushed surroundings.
   Send a bad move -> a `MoveRejected` correlated back to the client.
3. **Step 3** — weather changes with no user input; two clients in one area get the push, a third elsewhere
   doesn't.
4. **Tests** — `pytest` (updated `tests/test_messages.py`). Add a unit test per module: feed a command event,
   assert the emitted fact + the DB mutation.

## Not now (on purpose)

- **Full event sourcing** — `events.world` is retained, so the door stays open; not walking through it yet.
- **Gateway horizontal scaling** — the gateway is stateful (the connection registry), so it's the one piece
  that's awkward to run as N instances (needs sticky routing / shared registry). One instance is fine for now.
- **`aiokafka`** — confluent-kafka is sync; each module's loop runs via `asyncio.to_thread` (N parked threads).
  Fine at small module counts; revisit if it grows.
