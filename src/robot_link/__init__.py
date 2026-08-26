"""The voice → robot command link.

The demo runs on three machines and this package owns the leg between two of them:

    Jetson (mic/VAD/STT/TTS)  ──HTTP over VPN──►  PC server ở nhà (LLM brain + orchestrator)
            │
            └────────────── UDP on the venue LAN ──────────────►  Laptop (Gazebo + V-JEPA)

The LLM leg is HTTP because it crosses a VPN and carries a whole conversation turn; losing one
would lose the answer. The robot leg is UDP because it crosses one LAN switch and carries a single
short command whose value is entirely in arriving *now* — a stop that waits on a TCP retransmit is
not a stop. `protocol` makes that trade safe (repeat sends + de-duplication), `sender` is the
Jetson half, and `bridge` is the laptop half that turns a datagram into robot motion.
"""
