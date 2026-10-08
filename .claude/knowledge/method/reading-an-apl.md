# Reading a SimC Action Priority List (APL)

The APL *is* the rotation logic — reading it correctly is reading the rotation correctly.
Syntax:

```
actions.<list_name>=<action>,if=<condition>       # first action in a list
actions.<list_name>+=/<action>,if=<condition>      # appended action
```

- Lists are evaluated **top to bottom**, re-checked every time a GCD is free. The first
  action whose `if` condition is true (or has no condition) is what gets cast.
- `call_action_list,name=X,if=...` branches into another list — this is how hero-talent
  variants (e.g. Sunfury vs. Spellslinger) share one profile: a top-level condition on a
  talent picks which list actually runs. Structural gates like this are different from a
  per-action `if` — check them first to know *which list is even live* before reading its
  contents.
- Common expression vocabulary: `buff.X.up` / `.down` / `.react` (buff usable, accounting
  for a human reaction-time delay) / `.stack` / `.remains`; `cooldown.X.ready` / `.remains`
  / `.charges_fractional`; `talent.X` (boolean); `prev_gcd.N.X` (what was cast N GCDs ago —
  used to chain a burst cooldown right after a specific spender); `active_enemies`;
  user-defined `variable.X`.
- Fight configuration decides which branches are reachable at all (`desired_targets` /
  `active_enemies`) — see [combat-system.md](../game/combat-system.md).

**The one rule that actually matters: never infer a condition's direction from the ability
name or from what "seems right."** `buff.arcane_soul.down` and `buff.arcane_soul.up` read
similarly at a skim and mean opposite things. This project already shipped one real bug
from doing exactly that — read [arcane-mage-12.1-ptr.md](../classes/mage/arcane-mage-12.1-ptr.md)
for the specific case. When a raw APL line and a community/theorycrafting explanation of
"how the rotation works" are both available, treat the raw line as ground truth and use the
prose explanation to sanity-check your reading of it, not the other way around.

The SimC profile syntax itself (gear, talents, sim options, CLI overrides) is the
`simc-profile-syntax` skill; a spec's current APL lives under
`data/classes/<class>/<spec>/apl/`.
