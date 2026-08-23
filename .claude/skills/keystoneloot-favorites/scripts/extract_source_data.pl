#!/usr/bin/perl
# Extracts a class/spec-filtered zone -> item-pool map from the KeystoneLoot
# addon's own bundled loot databases, so a report can show "everything this
# spec can get from Altar of Fangs", not just the items already favorited.
#
# The v3 favorites export string (see parse_export.pl) does NOT carry which
# dungeon/raid/boss an item drops from - Favorites:Export() flattens across
# sourceId entirely. The addon itself resolves source per-item at runtime via
# Query:GetItemSource() (modules/query.lua): check CatalystDatabase, else scan
# every dungeon's lootTable for the itemId, else scan every raid boss's
# lootTable. This script reproduces exactly that lookup, offline, once, into
# a durable JSON file - see .claude/skills/keystoneloot-favorites/SKILL.md
# for why this has to be a separate step from parse_export.pl.
#
# Usage:
#   perl extract_source_data.pl [classId] [specId]
#   perl extract_source_data.pl 8 62      # Arcane Mage (default)
#
# Reads from the addon install (default path below, override with
# KEYSTONELOOT_ADDON_PATH env var). Writes data/keystoneloot_sources.json:
#   { classId, specId,
#     zones: [ { type: "dungeon"|"raid", key, zoneName, bossName?,
#                items: [ {itemId, slotId}, ... ] }, ... ] }
# slotId is the addon's own numeric equip-slot id (favorites.lua's
# EQUIP_LOC_SLOT: 0=Head,1=Neck,2=Shoulder,3=Back,4=Chest,5=Wrist,6=Hands,
# 7=Waist,8=Legs,9=Feet,10=Weapon,11=Off-hand,12=Finger,13=Trinket,14=Other) -
# carried through so a downstream build script can sort in canonical
# in-game slot order without re-deriving it from Wowhead's English slot text.
#
# Zone/boss display names are NOT in the addon's data files - the bundled
# dungeons.lua/raids.lua only carry a `--[[name = "..."]]` Lua *comment*,
# auto-generated in whatever locale the addon author's client was running
# (German, in the copy this was built against - e.g. "Rubinlebensbecken" for
# Ruby Life Pools). Comments are stripped before this regex parser ever sees
# them, and are not authoritative anyway. The %DUNGEON_NAME / %RAID_NAME /
# %BOSS_NAME tables below are hand-verified English names instead, matched by
# translating each German comment and cross-checking against this project's
# own prior research: the 8-dungeon Season 2 pool in
# .claude/knowledge/midnight-s2-dungeons.md (challengeModeId order matches
# the German name's plain-language translation exactly, e.g. "Altar der
# Fänge" = "Altar of Fangs") and the 8-boss Venomous Abyss roster in
# .claude/knowledge/venomous-abyss-12.1.md (bossId order + translated names
# match that report's encounter list, including the Tidebound Grotto Lair
# boss Nymrissa Wavecaller, "Gezeitengebundene Grotte" / "Wellenrufer").
# Re-verify this table by hand if KeystoneLoot ships a new season - it will
# not update itself.

use strict;
use warnings;
use JSON::PP;
use FindBin qw($RealBin);
use File::Spec;

binmode STDOUT, ':utf8';

my $classId = shift(@ARGV) // 8;
my $specId  = shift(@ARGV) // 62;

my $addon_path = $ENV{KEYSTONELOOT_ADDON_PATH}
    // 'E:\World of Warcraft\_retail_\Interface\AddOns\KeystoneLoot';

my %DUNGEON_NAME = (
    249 => "Kings' Rest",
    250 => "Temple of Sethraliss",
    399 => "Ruby Life Pools",
    584 => "The Blinding Vale",
    585 => "Voidscar Arena",
    586 => "Den of Nalorakk",
    587 => "Murder Row",
    588 => "Altar of Fangs",
);

my %RAID_ZONE_NAME = (
    1317 => "Tidebound Grotto",   # Lair (single boss)
    1320 => "The Venomous Abyss",
);

my %BOSS_NAME = (
    2849 => "Nymrissa Wavecaller",
    2888 => "Nek'zali the Soulcoiler",
    2874 => "Entombed Sentinels",
    2894 => "The Lost Explorers",
    2882 => "Vashnik the Malignant",
    2871 => "Sszorak",
    2887 => "The Twin Fangs",
    2883 => "The Coiled Altar",
    2895 => "Ula'tek",
);

sub slurp {
    my ($path) = @_;
    open my $fh, '<:raw', $path or die "Can't read $path: $!\n";
    local $/;
    return <$fh>;
}

# --- items.lua: itemId -> { usable(bool), slotId } for the given class/spec ---
my $items_lua = slurp(File::Spec->catfile($addon_path, 'data', 'items.lua'));
my %usable; # itemId -> slotId, only for items this class/spec can equip

while ($items_lua =~ /\[(\d+)\]\s*=\s*\{(.*?)\},\s*$/mg) {
    my ($itemId, $body) = ($1, $2);
    next unless $body =~ /\[$classId\]\s*=\s*\{([^}]*)\}/;
    my @specs = split /\s*,\s*/, $1;
    @specs = grep { length } @specs;
    next unless grep { $_ == $specId } @specs;
    my ($slotId) = $body =~ /slotId\s*=\s*(-?\d+)/;
    $usable{$itemId} = defined $slotId ? $slotId + 0 : undef;
}

print "items.lua: ", scalar(keys %usable), " items usable by classId=$classId specId=$specId\n";

# --- dungeons.lua: challengeModeId -> lootTable itemIds ---
my $dungeons_lua = slurp(File::Spec->catfile($addon_path, 'data', 'dungeons.lua'));
my @zones;

while ($dungeons_lua =~ /challengeModeId\s*=\s*(\d+),.*?lootTable\s*=\s*\{([^}]*)\}/gs) {
    my ($challengeModeId, $lootStr) = ($1, $2);
    my @itemIds = grep { exists $usable{$_} } ($lootStr =~ /(\d+)/g);
    next unless @itemIds;
    push @zones, {
        type     => 'dungeon',
        key      => "dungeon:$challengeModeId",
        zoneName => $DUNGEON_NAME{$challengeModeId} // "Unknown dungeon $challengeModeId",
        items    => [ map { { itemId => $_ + 0, slotId => $usable{$_} } } @itemIds ],
    };
}

# --- raids.lua: per raid block -> per boss -> union of lootTable[14..17] ---
my $raids_lua = slurp(File::Spec->catfile($addon_path, 'data', 'raids.lua'));
# Split into top-level raid blocks only. Both a raid entry and each boss
# inside its bossList start with the same "{ --[[name = " comment shape, so
# splitting on that alone shreds every boss out of its raid too - the
# indentation is the only thing that tells them apart (4 spaces for a raid,
# 12 for a boss within it), so anchor the split to exactly 4.
for my $raidBlock (split /(?=\n {4}\{\s*--\[\[name = )/, $raids_lua) {
    next unless $raidBlock =~ /journalInstanceId\s*=\s*(\d+)/;
    my $journalInstanceId = $1;
    my $zoneName = $RAID_ZONE_NAME{$journalInstanceId} // "Unknown raid $journalInstanceId";

    while ($raidBlock =~ /bossId\s*=\s*(\d+),\s*lootTable\s*=\s*\{(.*?)\n\s*\}\s*\}/gs) {
        my ($bossId, $lootBlock) = ($1, $2);
        my %seen;
        my @itemIds = grep { exists $usable{$_} && !$seen{$_}++ } ($lootBlock =~ /(\d+)/g);
        next unless @itemIds;
        push @zones, {
            type     => 'raid',
            key      => "raid:$bossId",
            zoneName => $zoneName,
            bossName => $BOSS_NAME{$bossId} // "Unknown boss $bossId",
            items    => [ map { { itemId => $_ + 0, slotId => $usable{$_} } } @itemIds ],
        };
    }
}

for my $zone (@zones) {
    my $label = $zone->{bossName} ? "$zone->{zoneName} - $zone->{bossName}" : $zone->{zoneName};
    print "  $label: ", scalar(@{$zone->{items}}), " items\n";
}

my $repo_root = $ENV{REPO_ROOT} // File::Spec->catdir($RealBin, '..', '..', '..', '..');
my $out_path  = File::Spec->catfile($repo_root, 'data', 'keystoneloot_sources.json');

open my $out, '>:raw', $out_path or die "Can't write $out_path: $!\n";
print $out JSON::PP->new->canonical->pretty->encode({
    classId => $classId + 0,
    specId  => $specId + 0,
    zones   => \@zones,
});
close $out;

print "\n$out_path written - ", scalar(@zones), " zones.\n";
