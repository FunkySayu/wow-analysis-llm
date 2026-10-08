# WoW combat system — what a spell does, and why a log line reads the way it does

The reference for two recurring questions: **what does this talent / spell / item actually
do in combat**, and **why does this damage event have these numbers**. It is spec-agnostic;
spec files under [classes/](../classes/) carry the worked examples.

How to read this file:

- A rule with a link or a measurement behind it was checked in this repo. A rule without
  one is how the game has worked through Midnight (12.x). Numbers change by patch, so
  re-read them from spell data (§1) before building on one.
- Spell data quoted here comes from the vendored simc, `SimulationCraft 1210-01`, WoW
  **12.1.0.69299** (hotfix 2026-08-15), queried 2026-10-08.
- WCL field behaviour was measured on ~600k damage events in the local `.wclcache/`
  (2026-10-08). WCL does not document these fields, so trust the measurement over the
  field name.

## 1. The ground truth: spell data

Names lie: talents get redesigned under the same name, and tooltips round or omit values.
The spell record does not. Query it from the vendored simc:

```sh
vendor/simc/build/Release/simc.exe spell_query=spell.id=164812
vendor/simc/build/Release/simc.exe "spell_query=spell.name=Starsurge"
```

What each field of the output answers:

| field | answers |
|---|---|
| `School` | which damage modifiers, immunities and lockouts apply (§7) |
| `Cast Time`, `GCD`, `Cooldown`, `Charges`, `Duration` | the timing (§2); `Duration` on an aura is its base length |
| `Mechanic` | e.g. `Bleed` (Rip), `Shield` (Power Word: Shield) — bleeds bypass armor (§6) |
| `Attributes` | behaviour flags. See the table below |
| `Effects` `#n` | what the spell does, one line each: `School Damage` + `SP/AP Coefficient`, `Apply Aura` + an aura type (`Periodic Damage … every 2 seconds`, `Modify Damage Taken%`, `Absorb Damage`, `Proc Trigger Spell`, `Modify Versatility%` …), with base values |
| `Affecting Spells` / `Modified By` | **every talent, aura and set bonus that changes this spell**, by spell id and effect. The fastest way to find what modifies something |
| `Proc Chance`, `Proc Flags` | for passives and procs: what event can trigger it (`White Melee`, `Cast Successful` …) |

Attributes worth knowing on sight:

| attribute | meaning | example |
|---|---|---|
| `Passive` | never cast; always-on aura | Omen of Clarity 16864 |
| `Is Channelled` | a channel (§2) | Arcane Missiles 5143 |
| `Haste Affects Duration` | cast time scales with haste | Starfire 194153 |
| `Spell Haste Affects Periodic` | tick interval scales with haste | Moonfire 164812, Rip 1079 |
| `Periodic Refresh Extends Duration` | pandemic refresh (§3) | Moonfire 164812 |
| `Compute Points Only At Cast Time` (on an effect) | snapshots its value when applied (§3) | Ignite 12654 |
| `Periodic Can Crit` / `Can't Crit` | whether ticks can crit | Moonfire / Ignite |
| `No Aura Icon` | the aura exists but is not shown to the player | Arcane Missiles 5143 |

To turn a talent node into a spell id, use the `wow-talent-data` skill. For the PTR tooltip
text, use Wowhead with the `/ptr/` segment (see the `wow-ptr-research` skill). Then confirm
the effect in a log (§10).

## 2. Time: GCD, cast types, haste and movement

**The GCD.** Most abilities trigger a 1.5s global cooldown, reduced by haste to a 0.75s
floor. Some abilities use a fixed 1.0s GCD that haste does not touch; spell data shows it
directly (Rip: `GCD : 1 seconds`). The GCD is the base tempo of a rotation: an APL is
fundamentally "what fills the next GCD." The client lets you queue the next ability
slightly before the GCD ends (the spell queue window), so gaps under ~0.1s between casts are
normal play, not hesitation.

**Off-GCD actions** neither trigger nor wait on the GCD: potions, on-use trinkets, many
defensives and some spec cooldowns. simc tags them `use_off_gcd=1`. They fire *alongside* a
GCD spell, which is why APLs pair them with a spender rather than spending a GCD on them.

| cast type | commits you for | resolves | movement | in the log |
|---|---|---|---|---|
| instant | the GCD only | immediately | castable while moving | one `cast` |
| hard cast | the cast time (haste-scaled) | once, at the end | movement cancels it | `begincast` then `cast`. `begincast` carries `targetID: -1`, so pair by order, not by target ([balance-druid](../classes/druid/balance-druid-12.1.md)) |
| channel | the channel duration | ticks during the channel | movement cancels it, losing the remaining ticks | one `cast`; damage comes as a **different** spell id per tick (Missiles cast 5143 returns zero damage events, [arcane-mage](../classes/mage/arcane-mage-12.1-ptr.md)) |
| charges | one charge; charges recharge on their own timer | — | — | — |

- **Haste on a channel** shortens the duration and keeps the tick count. Haste on a DoT
  shortens the tick interval and keeps the duration, so more ticks fit. The final tick is a
  partial one. Measured: Moonfire's data says a tick every 2s, while a top Balance's median
  tick interval was 1.148s ([balance-druid](../classes/druid/balance-druid-12.1.md)).
- **Clipping a channel** trades its last ticks for an earlier next action. APL keywords:
  `interrupt_if=`, `chain=1`, `cancel_action`. Whether a spec clips or full-channels can
  differ by hero tree: Spellslinger clips Missiles, Sunfury full-channels it (per community
  notes; the APL lines are in [arcane-mage](../classes/mage/arcane-mage-12.1-ptr.md)).
- **Movement.** A hard cast or channel stops when you move, unless an aura allows casting
  while moving. Such auras show in spell data as `Cast while Moving` / `Allow Casting while
  Moving` effects, often on *another* spell than the one cast (check `Affecting Spells`).
  Instants and those allowances are what a spec has left on a movement-heavy fight. Fire
  keeps 0.96× of its damage with 20% of the fight spent moving, because Scorch is castable
  while moving and Hot Streak Pyroblasts are instant
  ([fire-mage](../classes/mage/fire-mage-12.1.md)). The `cancels` check in
  `tools/warcraftlogs/` counts hard casts started but not completed.
- **Travel time.** Projectiles land after the `cast`. A cast at 9.8s into a 10s window can
  damage outside it; attribute windows by the damage timestamp, not the cast.

## 3. Auras: buffs, debuffs and the rotation

An aura is any spell effect of the form `Apply Aura | <type>`: a buff on a friendly unit or a
debuff on a hostile one. Nearly everything a rotation "builds toward" is an aura: Eclipse,
Combustion, Hot Streak, a stacking proc, a DoT, a boss's vulnerability.

**In the log:**
- **Lifecycle events.** `applybuff` / `applydebuff`, `refreshbuff` / `refreshdebuff`,
  `applybuffstack` / `removebuffstack` (with `stack`), then `removebuff` / `removedebuff`.
- **What was up on a hit.** Each damage event carries a `buffs` string: the aura ids on the
  *source* at that moment (`"1217242.1295057.…"`). It needs `includeResources` (see
  `warcraftlogs-reports`).
- **Debuff events are keyed on the aura on the target**, not on who cast it. Rebuild one
  player's DoT uptime from its damage ticks instead
  ([balance-druid](../classes/druid/balance-druid-12.1.md)).
- **Some auras never log.** Passives (§4) and `No Aura Icon` auras never appear;
  raid-wide debuffs like Chaos Brand carry `No Cast Log` / `Do Not Log Aura Refresh`.

**Rules that change damage:**

| rule | what it means | evidence |
|---|---|---|
| **Pandemic** | refreshing a DoT carries its remaining time over, up to 30% of base duration. Earlier is waste, later risks a gap | spell attribute `Periodic Refresh Extends Duration`. Moonfire: 5.4s of 18s, [balance-druid](../classes/druid/balance-druid-12.1.md) |
| **Snapshot** | the DoT keeps the modifiers it was applied with | Feral bleeds keep Tiger's Fury's +15% ([feral-druid](../classes/druid/feral-druid-12.1.md)). Ignite's effects are `Compute Points Only At Cast Time` |
| **Dynamic** | the DoT reads modifiers live, each tick | Starfall ticks read Eclipse live, measured at fixed stacks ([balance-druid](../classes/druid/balance-druid-12.1.md)) |
| **Stacks** | magnitude scales with stack count. One event can carry all stacks | a Starfall tick carries every active Starfall; compare per tick only at a fixed stack count |
| **Caster-scoped vs shared** | `Modify Damage Taken% from Caster's Spells` amplifies only the caster's own damage. `Modify Damage Taken%` amplifies everyone's | Moonfire and Rip carry the caster-scoped kind; Chaos Brand (1490: +3%, magic schools) and Mystic Touch (113746: +5%, physical) are the shared kind |

Never assume snapshot or dynamic from the name. Measure it: hit size against an aura that
turned on or off mid-DoT, at a fixed stack count.

**Raid buffs, from 12.1 spell data:** Arcane Intellect +3% Intellect, Mark of the Wild +3%
Versatility, Bloodlust +30% haste for 40s. Lust has **eight** spell ids, not four: check
the buff received, not the cast
([balance-druid](../classes/druid/balance-druid-12.1.md)).

**How auras connect to the rotation:**
- **A proc is a resource.** Clearcasting, Hot Streak and Shooting Stars charges are spent
  like any other resource, and a capped proc is wasted
  ([resource-economy](../method/resource-economy.md)).
- **APL conditions read auras:** `buff.x.up`, `debuff.y.remains`. The direction of a
  condition is the trap ([reading-an-apl](../method/reading-an-apl.md)).
- **Burst windows multiply aura with aura.** A spender inside Eclipse inside a boss's
  vulnerability takes all three. A cooldown's value depends on what it overlaps, which is
  why cooldowns are scored per instance
  ([analysing-a-pull](../method/analysing-a-pull.md)).

## 4. Passive effects and procs

A passive (`Passive` in spell data) is never cast. It is one of two kinds, and they look
completely different in a log:

| kind | spell data | in the log |
|---|---|---|
| **modifier** | `Apply Aura` + `Add Percent Modifier`, `Modify Damage Done%` … | **invisible.** Another spell's hits are just bigger. It shows up in that spell's `Affecting Spells` |
| **trigger** | `Proc Trigger Spell` / `Periodic Trigger Spell` + `Proc Flags` | a **new spell id** doing damage or applying a buff. Shooting Stars passive 202342 deals damage as 202497; Shatter logs as 1246949 ([frost-mage](../classes/mage/frost-mage-12.1.md)); Omen of Clarity (`Proc Flags: White Melee`) triggers Clearcasting |

**How a proc fires:**
- **Flat chance per trigger event.** `Proc Chance` × the events matching `Proc Flags`, so
  more casts or more ticks means more procs. Haste scales a tick-driven proc: Shooting
  Stars procs off DoT ticks, and two thirds of Balance's Astral Power is haste-scaled for
  that reason ([balance-druid](../classes/druid/balance-druid-12.1.md)).
- **RPPM (real procs per minute).** Most item and many talent procs fire at a rate per
  minute, sometimes scaled by haste, with bad-luck protection. The rate does not depend on
  how many buttons you press.
- **Internal cooldown.** A `Cooldown` on the proc aura itself (Red Moon: 30s).
- **Deterministic counters** that look like procs. Arcane Soul is a clock, not a chance
  ([arcane-mage](../classes/mage/arcane-mage-12.1-ptr.md)).

**Seeing an invisible modifier.** Take a ratio of two of the player's own hits that share
every modifier except the one under test. Balance's Shooting Stars ÷ Moonfire tick isolates
the mastery double-dip (ρ +0.45 with mastery rating), while Starfall ÷ Moonfire does not
(ρ −0.10): too many Starfall-only modifiers ride on it
([balance-druid](../classes/druid/balance-druid-12.1.md)). WCL can also **fold** a passive
into its parent: Intensifying Flame is reported inside Ignite
([fire-mage](../classes/mage/fire-mage-12.1.md)).

## 5. Stats: from rating to damage

| tier | stats | what they do in combat |
|---|---|---|
| primary | Intellect / Agility / Strength, Stamina | the main stat becomes spell power / attack power. Every damage effect's `SP/AP Coefficient` multiplies it (Starsurge 3.676 SP, Moonfire tick 0.184 SP, Rip tick 0.3113 AP). Stamina is health |
| secondary | critical strike, haste, mastery, versatility | see below |
| tertiary | leech, avoidance, speed | survival and movement only: leech heals for a share of damage done, avoidance cuts AoE damage taken, speed is run speed. No damage |

The secondaries:
- **Crit:** chance for a hit to deal double damage. Talents raise the chance or the crit
  multiplier, and some abilities always crit.
- **Haste:** shorter cast times and GCD, faster DoT ticks, more channel ticks per second,
  faster resource regen, and more RPPM procs. Some cooldowns scale with it too; check
  attributes.
- **Mastery:** a different effect per spec, read from the spec's mastery spell. Astral
  Invocation (393014) amplifies Nature and Arcane damage, Razor Claws (77493) amplifies
  bleeds, Fire's mastery scales Ignite.
- **Versatility:** a flat % damage and healing done, and half that % off damage taken.

**Rating to percentage** has diminishing returns. At level 90, 1% costs 44 haste rating,
46 crit or mastery, and 54 versatility, before the curve bends
([itemization-fundamentals](itemization-fundamentals.md), "Diminishing returns").

**Rating is not effective stat.** Raid buffs, procs and temporary buffs move the real
number, so measure haste from the log, not the armory: cast times, GCD gaps and tick
intervals ([balance-druid](../classes/druid/balance-druid-12.1.md)).

**A stat's value is spec-shaped.** The same stat can be best for one spec and worst for
its sibling. Fire values crit least (plausibly because Combustion and Fire Blast already buy its
crits; not isolated by experiment); Frost values it most, because its Shatter talents
convert crit chance into crit damage
([dps-specs-boss-profile](../classes/dps-specs-boss-profile-12.1.md)). Get weights from a
sim on the right fight, never from the stat's description.

## 6. Damage calculation

Roughly, a hit goes through these stages, in order:

```
base       = coefficient × spell power / attack power   (or weapon damage)
caster     × versatility × mastery × talents × buffs × set bonuses
crit       × crit multiplier (2.0 base), if it crits
target     × damage-taken modifiers: vulnerability, Chaos Brand / Mystic Touch, caster-scoped debuffs, boss damage reduction
armor      − physical non-bleed only
absorbs    − shield on the target eats part or all
health     − anything past the target's remaining HP is overkill
```

**How modifiers combine.**
- **Across categories, they mostly multiply.** That is why a stacked window is worth so
  much: a +100% amplify alone gives everyone 2.00× for pressing nothing
  ([arcane-mage](../classes/mage/arcane-mage-12.1-ptr.md)).
- **Within one category, some add instead.** Spell data does not say which. Read the
  spec's simc module before assuming either.
- **simc's own options have conventions too.** `vulnerable,multiplier=` is the
  *increase*, not the factor ([modelling-a-fight-in-simc](../method/modelling-a-fight-in-simc.md)).

**AoE scaling.** An AoE hits every target in its radius as a separate damage event
(`isAoE: true`). Many AoE spells reduce damage per target beyond a cap; the tooltip says
"reduced beyond N targets."

**Armor** cuts only physical damage that is not a bleed. Measured on player-sourced
non-crit hits, Shred lost 12–24% to `mitigated`, while 3,874 of 3,933 Rip ticks
carried none. Mystic Touch's +5% physical-damage-taken partly offsets armor, and it is part
of why a physical spec's damage depends on raid composition.

**Untargetable, immune, evading.**
- **Untargetable stops direct damage but not DoTs already ticking.** Find it by splitting
  damage on the `tick` flag ([modelling-a-fight-in-simc](../method/modelling-a-fight-in-simc.md)).
- **Immune hits log** with `amount: 0` and `hitType: 10`.
- **An invulnerable target still counts toward target-count scaling.**

**Boss damage reduction** looks like a vulnerability in reverse. Malacrass sat at 99%
([arcane-mage](../classes/mage/arcane-mage-12.1-ptr.md)).

### Reading WCL's damage fields

| field | holds | measured behaviour |
|---|---|---|
| `amount` | health actually removed | excludes `absorbed` and `overkill` |
| `absorbed` | eaten by a shield on the target | WCL and this repo's checks count `amount + absorbed` as damage done |
| `mitigated` | removed by armor or damage reduction | **mostly absent on crits.** Shred: 659 of 778 non-crits carry it, 1 of 720 crits. A missing `mitigated` is not zero armor |
| `unmitigatedAmount` | depends on the event, see below | — |
| `overkill` | past the target's remaining HP | present only when the hit killed. Deaths tables show it only on the killing blow ([boss-death-timelines](../method/boss-death-timelines.md)) |
| `blocked` | removed by a block | appears with `hitType: 4`; included in `mitigated` |
| `tick` | `true` on periodic damage | the direct-vs-tick split |
| `hitType` | outcome enum | 0 miss, 1 hit, 2 crit, 4 block, 7 dodge, 8 parry, 9 deflect, 10 immune, 13 evade. WCL's enum. The cached samples of every outcome except 1, 2 and 4 carry `amount: 0` |
| `buffs` | aura ids on the source | §3 |
| `sourceInstance` / `targetInstance` | which copy of a repeated NPC | needed to tell adds apart |

What `unmitigatedAmount` holds depends on whether the event carries `mitigated`:
- **With `mitigated`** (most damage players take, physical non-crit hits):
  `unmitigatedAmount = amount + absorbed + mitigated + overkill`. This held on all but 30 of
  ~111k such events.
- **Without it** (most damage players deal): `unmitigatedAmount` is *smaller* than what
  landed. Total ÷ unmitigated runs 1.03 median (p90 1.16) on non-crits and **2.21** median
  (p10 2.08) on crits. So it reads as the hit before the crit multiplier and before
  target-side amps.
- **So on a non-crit, `(amount + absorbed + overkill) ÷ unmitigatedAmount − 1` estimates
  the damage-taken amp at that moment.** This is an inference from these numbers, not
  WCL's documentation; check it against a known amp before relying on it.

## 7. Spell schools

Seven base schools, each a bit in the school mask:

| school | mask |
|---|---|
| Physical | 0x01 |
| Holy | 0x02 |
| Fire | 0x04 |
| Nature | 0x08 |
| Frost | 0x10 |
| Shadow | 0x20 |
| Arcane | 0x40 |

A multi-school spell is the OR of its schools:
- **Astral** = Arcane + Nature = 0x48 = 72
- **Frostfire** = Fire + Frost = 20
- **Spellfire** = Fire + Arcane = 68
- **Shadowflame** = Fire + Shadow = 36

WCL exposes the mask as the ability's `type`; a Nature boss ability logs `"type": 8`. simc's
spell data prints the school by name.

**One spec can mix schools,** so check per spell, never per spec. On Balance, Starsurge,
Starfall and Shooting Stars are **Astral**, while Starfire and Moonfire are plain **Arcane**.

What a multi-school spell gets:
- **Every modifier keyed on any of its schools.** That is the mastery double-dip: Astral
  Invocation boosts Nature and Arcane separately, so an Astral spell takes it twice
  ([balance-druid](../classes/druid/balance-druid-12.1.md)).
- **Raid-wide amps by mask.** Chaos Brand's effect mask is 0x7e: all six magic schools,
  not Physical.
- **Lockouts and immunities by school.** An interrupt locks out the school of the
  interrupted spell, and an immunity applies per school.

To learn a debuff's school from logs alone, use its dispel type; the method is in
[midnight-s2-dungeons](../dungeons/12_1/midnight-s2-dungeons.md).

## 8. Absorbs

| kind | what it does | in the log |
|---|---|---|
| **damage absorb on a player** (Power Word: Shield: `Absorb Damage`, mask 0x7f = all schools) | eats incoming damage before health | the damage event's `absorbed`. WCL credits the shield's caster with an absorb, counted as healing |
| **damage absorb on an enemy** (boss shields, add shields) | eats the raid's damage | the raid's hits read `amount: 0, absorbed: N`. Count `amount + absorbed` as damage done, or shield phases look like dead time |
| **healing absorb on a player** | eats incoming healing before health | heal events with `absorbed`; that healing restored nothing |
| `overheal` | healing past full health | wasted, not absorbed |

For death analysis, absorbed damage is **excluded** from a blow's size: a shield that ate
half the hit means the player was not one-shot
([boss-death-timelines](../method/boss-death-timelines.md)).

## 9. Items and consumables in combat

**On-use trinkets** are off-GCD, with their own cooldown.
- APLs fire them inside the spec's main cooldown (Balance: `use_items` only while
  Incarnation is up). A trinket ranking is therefore only as good as the cooldown schedule
  simmed ([twin-fangs-sim-profile](../raid/12_1/venomous_abyss/twin-fangs-sim-profile.md)).
- In a log, score each use against the fight's windows. Of 25 sampled Arcane pulls that
  log an on-use, 23 fire it inside the boss's vulnerability window
  ([arcane-mage](../classes/mage/arcane-mage-12.1-ptr.md)).

**Proc trinkets, "cantrip" equip effects, weapon enchants and embellishments** are passives
of the trigger kind (§4), mostly RPPM.
- The sim models them from the item's data, which can be wrong. The Aqirbane Reliquary sims
  all its secondaries as crit, unlike the log
  ([balance-druid](../classes/druid/balance-druid-12.1.md)).
- For gear facts simc mis-resolves, see the `simc-profile-syntax` skill. Embellishments are
  covered in [crafting-midnight-s2](crafting-midnight-s2.md).

**Set bonuses** are auras that modify specific spells. They appear in a spell's `Affecting
Spells` (Starsurge lists `Druid Balance 12.1 Class Set 2pc`), so that list shows exactly
what a 2pc or 4pc touches.

**Consumables:**

| kind | effect | trap |
|---|---|---|
| flask | a secondary stat for the fight | **the name does not say the stat** (Magisters = Mastery, Blood Knights = Haste; ids in [balance-druid](../classes/druid/balance-druid-12.1.md)) |
| food, augment rune, weapon oil | stat or damage buffs | present at pull in `CombatantInfo` auras |
| combat potion | a burst buff on a shared potion cooldown | pre-pull potions are invisible in a fight's cast log, and Midnight potions are not named "Potion" ([analysing-a-pull](../method/analysing-a-pull.md)). Some scale with your gear: Potion of Recklessness boosts your *highest* secondary, so whether it beats Light's Potential depends on which stat leads your gear |
| healthstone, healing potion | survival | — |

`CombatantInfo` gives gear, enchants, gems, auras at pull and the talent tree; the
`consumables` check in `tools/warcraftlogs/` audits all of this against the pool. That
audit is step one of every analysis ([analysing-a-pull](../method/analysing-a-pull.md)).

## 10. Enemies, target count, and which APL branches are reachable

- **Target count decides which APL branches are reachable.** `desired_targets` /
  `active_enemies` gate whole AoE-only branches. A priority line that mentions AoE can look
  like dead logic when it is only inactive for *this* sim, or the reverse. Check the fight's
  target count before reading a line.
- **Adds come and go without spawn events.** Spawn is first damage taken, which is an upper
  bound ([modelling-a-fight-in-simc](../method/modelling-a-fight-in-simc.md)).
- **An add wave rewards specs whose damage lands on fresh targets.** Fire scores 1.38× on
  3 adds every 60s ([fire-mage](../classes/mage/fire-mage-12.1.md)).
- **Execute phases change priorities.** Fire is the one spec stronger in the last 30% of a
  health-based fight (Scorch auto-crits below 30%).

## 11. Checklists

**Why does this damage event read this way?**

1. **Right spell id?** One ability can be several ids: the cast differs from the damage
   (Moonfire cast 8921 vs DoT 164812; Missiles 5143 vs its impact), and the journal id is
   often not the logged one. Resolve by name from `masterData.abilities`.
2. **Direct or `tick`?** **Crit (`hitType` 2)?**
3. **Who is the source?** A pet or guardian is its own actor.
4. **What was on the source?** Read its `buffs` string.
5. **What was on the target?** Look for an amp in the non-crit ratio (§6).
6. **Where did the rest of the damage go?** It is in `absorbed` (a shield), `mitigated`
   (armor), or `overkill` (the target died).
7. **Is it a stacking aura?** Hold the stack count fixed before comparing hit sizes.
8. **Was it a projectile?** Then it landed after the cast.

**What does this talent actually do?**

1. Get the node's spell id (`wow-talent-data`) and its PTR tooltip (`/ptr/`).
2. Run `spell_query` on that id and read it in order:
   - Is it `Passive`?
   - What do its effects do?
   - If it is a trigger, what spell id does it trigger?
   - Which spells does it modify? Look it up in their `Affecting Spells`.
3. Place it in the resource economy: does it generate, spend, amplify or proc?
   ([resource-economy](../method/resource-economy.md)).
4. Confirm it in a log:
   - **A trigger passive:** look for a new spell id.
   - **A buff:** look for its id in `buffs` strings.
   - **An invisible modifier:** take a ratio of two of the player's own hits (§4).

   Report the result as "confirmed via X" or "unverifiable".

Reading the priority list itself: [reading-an-apl.md](../method/reading-an-apl.md).
