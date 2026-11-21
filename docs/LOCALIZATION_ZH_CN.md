# Local Chinese names and rates

Generate display names from an installed Simplified Chinese client:

```powershell
.\.venv\Scripts\python.exe tools/build_zh_cn_catalog.py --client 'D:\天使之恋Online'
$env:AO_LOCALE = 'zh_CN'
```

The generator reads the effective `setting/gb/` tables in PAK priority order and
writes `data/localization/zh_CN.json`, which is ignored by Git. Client files and
the server's gameplay database are not replaced. `AO_LOCALE_FILE` optionally
selects another generated catalog. Unset `AO_LOCALE` to restore English output.

World NPC and monster spawn packets translate by NPC/monster ID immediately
before serialization, including the captured tutorial and Lyceum spawns. Only
the fixed name field changes. GBK encoding retains the 16-byte native name limit
without splitting a Chinese character. Missing IDs keep their original names;
summoned pets with personalized names are excluded. Internal English names stay
unchanged because quests, drops and special NPC logic still use them.

Item acquisition notices, skill notices and known dialogue substitution names
also use the catalog. Achievement, title, quest, map and activity names now come
from `achievement.xml`, `crown.xml`, `quest.xml`, `stage.xml` and `string.xml`.
Ambiguous English aliases are excluded. Achievement notices use numeric IDs at
all three award paths (manual/NPC, automatic and competition), without changing
achievement rules, points, saved IDs or the canonical English tables.

Server-authored notices use `MENSAJES_ZH_CN` and `PLANTILLAS_ZH_CN` in
`server/mensajes_zh_cn.py`, routed through `server/localizacion.py`. The current
set has 471 exact strings and 129 full-sentence patterns. These cover permanent
stat items, achievements, quests, level-ups, inventory, pets, shops, production,
fusion, housing, guilds, farming, collection, mail-store delivery, star blessing,
teleports and competition/activity notices. Dynamic names and quantities retain
their original values; only known display names are translated. Player names,
guild names and pet nicknames in the designated placeholders remain untouched.

Notices use GBK. Activity banners retain their 900-byte limit, and server title
broadcasts retain their portrait selector and 999-byte text limit, without
splitting GBK characters. Title broadcasts opt into this encoding explicitly;
ordinary player-authored broadcasts are neither translated nor re-encoded.
English mode remains unchanged. Rebuilding the name catalog does not erase the
hand-written translations. Restart the server to load code/catalog changes.

This is not a complete translation of every possible UI or dialogue. Most
ordinary dialogue uses native Chinese message IDs already. Server-generated NPC,
boss and pet speech bubbles and the special Arena channel-13 result banner are
now translated. Some GM/debug output, unknown names and unlisted dynamic
sentences may still contain English. Player-authored chat is never translated or
re-encoded. No executable patches or changes to the installed Chinese client are
applied.

## 2026-11-20 system-message batch

截图里的英文来自 `app._logros_actualizar` 等成就发奖路径，模板为
`Achievement completed: [%s] (+%d points)`，名称取自英文 `plantillas/logros.json`。
本次同时修正提示句和显示名称，而不是修改成就判断或存档：

| 原文 | 当前中文输出 |
| --- | --- |
| Achievement completed: [Max MP - 5,000] (+2 points) | 成就达成：【MP界限突破 5000】（+2点成就积分） |
| Achievement completed: [Max MP - 10,000] (+2 points) | 成就达成：【MP界限突破 10000】（+2点成就积分） |
| Achievement completed: [I love change - 2] (+2 points) | 成就达成：【就是没定性 2】（+2点成就积分） |

重新生成的本机目录含 4,443 个成就、572 个称号、1,506 个任务和453个地图名称。
每日活动名也取自客户端，例如“势力歼灭战”“爆爆大战”“诈欺世界”“眼捷手快”，
不依赖对英文活动名的猜译。找不到对应ID时保留原文，不影响发奖。

可重复检查已知消息入口中直接传入的固定英文：

```powershell
.\.venv\Scripts\python.exe tools/audit_zh_cn_notices.py --check
```

当前扫描399条不同固定文本，全部有翻译。这个数字不包含所有变量拼接、异常来源、
NPC气泡、GM帮助和客户端界面，不能据此宣称全游戏零英文。

验证使用隔离的 `AO_DATOS` 和临时账号数据库，不操作正在游玩的角色：

- 汉化、实际成就发奖三条路径、属性道具、聊天、商城、NPC兼容、交易密码、地图、
  目录生成共102项测试通过；校验了名称、GBK包头/长度、英文回退及角色无关字段保留。
- 扩大回归曾得到211通过、36失败；失败集中在未提取的地图/配方/魔法/兑换/农场资源，
  例如圣域地图112缺失、生产配方19缺失、农场地块67没有坐标。
  临时数据库清理另有Windows文件占用警告。这些不是已通过的测试，本次未修改其机制。
- 在线服务端未被强制停止；正常退出游戏后重启服务端，新的提示才会生效。

The local launcher enables `AO_LOCALE=zh_CN` and the existing
`AO_CLIENT_PROTOCOL=cn-8.6.5.7` lighting fix. Restart the server and reconnect to
reload the settings and refresh existing NPCs.

## Rates

`server/configuracion.py` now selects:

| Setting | Value |
| --- | --- |
| `TASA_EXP_BASE` | 1.0 |
| `TASA_SKILL_EXP_BASE` | 100.0 |
| `TASA_DROP_BASE` | 10.0 |
| `EVENTO_FIN_DE_SEMANA_AUTOMATICO` | False |

Disabling automatic weekend events prevents an implicit change to 2x EXP,
200x skill EXP and 15x drops on Fridays through Sundays. Item and skill buffs
continue to add their documented bonuses. Quest rewards, fixed event rewards
and skill vouchers retain their existing rules.

The existing normal-monster drop algorithm applies `min(0.95, 0.90 * rate)`:
the requested 10x rate reaches the 95% cap and does not multiply item quantities.
Boss-guaranteed drops keep their existing behavior. Gold remains 7.5x. Player
critical damage remains 1.5x, with chance derived from stats and buffs (90% cap).
