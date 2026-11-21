# Simplified Chinese 8.6.5.7 map lighting

The local Simplified Chinese client entered Angel Lyceum successfully but rendered
the scene dark around a small light surrounding the player. Its current
`setting/gb/stage.xml` in `update29.pak` declares stage 41 with brightness 255 and
no weather. The original executable was only unpacked into a diagnostic copy;
the installed executable and its PAKs were not changed.

Client SHA-256: `133949b83a57fbbd0322afa50e321d9e2db83291a01a82c2d9fd81d12c580e6f`.

## Measured receive layout

The world `0x0014` handler at `0x005EF0E0` reads these offsets, including the
two-byte opcode:

| Offset | Type | Use |
| --- | --- | --- |
| 2 | u32 | Map flags; bit 0x20 disables the minimap |
| 6 | u8 | Hour passed to `0x005B54B0`, reduced modulo 24 |
| 7 | u8 | Weather type passed to `0x00687AF0`; zero disables weather |
| 8 | u8 | Weather intensity |
| 9 | i32 | Lighting preset; -1 explicitly disables the preset |

The previous packet contained seven body bytes (`05020000ff0000`), or nine
bytes including the opcode. The handler nevertheless reads a dword at offset 9.
This reads beyond the packet. The old hour byte 255 also becomes hour 15; it is
not a full-brightness byte in this client.

Read-only inspection of the running process found scene brightness 32/255, a
map brightness override of 255, hour 15, and an enabled lighting-preset flag.
The preset path can override normal map brightness. These observations explain
why the map's normal full-brightness setting was not sufficient.

## Opt-in correction

Set `AO_CLIENT_PROTOCOL=cn-8.6.5.7` for the local server. `flags_de_mapa` then emits
the complete eleven-byte body, explicitly selecting hour 12, no weather, and
preset -1. The client uses its existing map brightness override, including
intentionally dark maps. The original IGG packet remains unchanged by default.
Both initial scene construction and the subsequent scene-ready refresh use the
same constructor. This does not implement a day/night clock or claim general
compatibility with other client versions.

Regression coverage in `tools/test_scene_map.py` checks the native dword read,
map flags, template/refresh consistency, and unchanged legacy bytes. A running
server must be restarted to load the correction; source changes alone do not
update existing connections.
