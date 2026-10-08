# WoW combat system fundamentals

- **GCD (global cooldown).** Most offensive abilities share a lock (~1.5s, reduced by
  haste) — casting one prevents casting *any other GCD ability* until it expires. This is
  the base tempo of a rotation; APL priority order is fundamentally "what fills the next
  GCD."
- **Off-GCD abilities.** Some actions don't trigger or respect the GCD lock — trinkets,
  potions, and specific utility spells. In simc profiles these are tagged
  `use_off_gcd=1`. They can be used *in addition to* a GCD spell on the same moment, which
  is why APLs often fire them alongside a spender rather than instead of one.
- **Casts vs. channels.** A cast (e.g. Arcane Blast, Prismatic Bolt) commits for a fixed
  cast time and resolves once at the end. A channel (e.g. Arcane Missiles, Evocation) ticks
  repeatedly over a duration and can be **clipped** — cut short to move on to something
  else, trading later ticks for GCD efficiency. APL lines like `interrupt_if=...` or
  `chain=1` are explicitly about channel-clipping behavior, and whether a given hero-talent
  variant clips or full-channels the same channel can itself be a deliberate, documented
  difference (Spellslinger clips Missiles; Sunfury full-channels it, per community notes).
- **Fight configuration changes which APL branches are even reachable.** `desired_targets`
  / `active_enemies` gate entire AoE-only conditions in the APL — reading a priority line
  that mentions AoE without checking the fight's target count can make you think a
  condition is "dead" logic when it's just inactive for *this specific sim*, or vice versa.

Reading the priority list itself: [reading-an-apl.md](../method/reading-an-apl.md).
