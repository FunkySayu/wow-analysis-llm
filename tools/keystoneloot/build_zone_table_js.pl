#!/usr/bin/perl
# Combines data/classes/<class>/<spec>/12_1_loot_sources.json (zone -> item pool, from
# extract_source_data.pl), data/items/12_1/items.json (item info, from
# fetch_item_info.pl) and a parsed favorites list (from parse_export.pl)
# into one self-contained JS module for a "loot table" style Artifact: one
# row per dungeon/raid boss, every item that spec can use there, favorited
# ones flagged with their tier.
#
# Usage:
#   perl build_zone_table_js.pl scratch/keystoneloot_favorites.json > data/classes/<class>/<spec>/12_1_keystoneloot_zones.js
#   perl parse_export.pl "KeystoneLoot:v3,..." | perl build_zone_table_js.pl > data/classes/<class>/<spec>/12_1_keystoneloot_zones.js
#
# Output: `const KEYSTONE_LOOT_ZONES = {classId, specId, zones: [...]};`
# Each zone's `items` is pre-sorted **importance first** (Best in Slot > Must
# have > Nice to have > unfavorited), **then slot** (canonical WoW equip
# order) - the exact order a "which items matter here" table wants to read
# in. `importance` is a short code (`bis`|`must`|`nice`|`none`) rather than
# the raw tier number, since the ordering isn't the raw number's ordering
# (tier 3 outranks tier 2 - see SKILL.md) and a rendering script for a table
# like this shouldn't have to know that.

use strict;
use warnings;
use JSON::PP;
use FindBin qw($RealBin);
use File::Spec;

binmode STDOUT, ':utf8';

my $favorites_arg = shift @ARGV;
my $favorites_text;
if (defined $favorites_arg) {
    open my $fh, '<:raw', $favorites_arg or die "Can't read $favorites_arg: $!\n";
    local $/;
    $favorites_text = <$fh>;
    close $fh;
} else {
    local $/;
    $favorites_text = <STDIN>;
}
die "No favorites JSON given (arg path or stdin) - see script header for usage.\n"
    unless defined $favorites_text && length $favorites_text;

my $json = JSON::PP->new->utf8;
my $favoritesBySpec = $json->decode($favorites_text);

my $repo_root     = $ENV{REPO_ROOT} // File::Spec->catdir($RealBin, '..', '..');
my $items_path    = File::Spec->catfile($repo_root, 'data', 'items', '12_1', 'items.json');

# The favorites export is keyed by spec id; the loot pool to read is that spec's. Override
# with LOOT_SOURCES=<path> when the export carries more than one spec.
my @favSpecs = keys %$favoritesBySpec;
die "Favorites carry " . scalar(@favSpecs) . " specs (@favSpecs) - set LOOT_SOURCES to pick one.
"
    unless $ENV{LOOT_SOURCES} || @favSpecs == 1;
my $sources_path = $ENV{LOOT_SOURCES}
    // File::Spec->catfile(spec_dir_for($repo_root, $favSpecs[0]), '12_1_loot_sources.json');

# data/classes/<class>/<spec>/ for a spec id, via data/classes/specs.json (spec ids are unique
# across classes). Mirrors tools/datalayout.py's spec_dir_for_ids.
sub spec_dir_for {
    my ($repo_root, $specId) = @_;
    my $map_path = File::Spec->catfile($repo_root, 'data', 'classes', 'specs.json');
    open my $mfh, '<:raw', $map_path or die "Can't read $map_path: $!\n";
    my $map = JSON::PP->new->utf8->decode(do { local $/; <$mfh> });
    close $mfh;
    for my $class (@{ $map->{classes} }) {
        for my $spec (@{ $class->{specs} }) {
            return File::Spec->catdir($repo_root, 'data', 'classes', $class->{dir}, $spec->{dir})
                if $spec->{id} == $specId;
        }
    }
    die "spec id $specId is not in $map_path\n";
}

open my $sfh, '<:raw', $sources_path or die "Can't read $sources_path (run extract_source_data.pl first): $!\n";
my $sources = $json->decode(do { local $/; <$sfh> });
close $sfh;

open my $ifh, '<:raw', $items_path or die "Can't read $items_path (run fetch_item_info.pl first): $!\n";
my %items = %{ $json->decode(do { local $/; <$ifh> }) };
close $ifh;

my $specKey = $sources->{specId};
my $favSpec = $favoritesBySpec->{$specKey};
my %tierByItem;
if ($favSpec) {
    for my $entry (@{ $favSpec->{items} }) {
        $tierByItem{ $entry->{itemId} } = $entry->{tier};
    }
}

# TIER_NAME/IMPORTANCE: tier is NOT priority-ordered (3=BiS outranks 2=Must
# have - see modules/favorites.lua Favorites.TIER_ORDER, and this skill's
# SKILL.md). Map straight to an importance code + explicit rank instead of
# letting a renderer sort on the raw integer.
my %IMPORTANCE = (
    3 => { code => 'bis',  label => 'Best in Slot', rank => 0 },
    2 => { code => 'must', label => 'Must have',    rank => 1 },
    1 => { code => 'nice', label => 'Nice to have', rank => 2 },
);
my $NONE = { code => 'none', label => '', rank => 3 };

my $unresolved = 0;
my @zones;
for my $zone (@{ $sources->{zones} }) {
    my @outItems;
    for my $slotRef (@{ $zone->{items} }) {
        my $itemId = $slotRef->{itemId};
        my $info = $items{$itemId};
        if (!$info) {
            $unresolved++;
            next;
        }
        my $tier = $tierByItem{$itemId};
        my $imp  = defined $tier ? ($IMPORTANCE{$tier} // $NONE) : $NONE;

        push @outItems, {
            %$info,
            slotId         => $slotRef->{slotId},
            tier           => $tier,
            importance     => $imp->{code},
            importanceRank => $imp->{rank},
        };
    }

    @outItems = sort {
        $a->{importanceRank} <=> $b->{importanceRank}
            || ($a->{slotId} // 99) <=> ($b->{slotId} // 99)
            || $a->{name} cmp $b->{name}
    } @outItems;

    push @zones, {
        type     => $zone->{type},
        key      => $zone->{key},
        zoneName => $zone->{zoneName},
        bossName => $zone->{bossName},
        items    => \@outItems,
    };
}

if ($unresolved) {
    warn "$unresolved item(s) in the zone pool have no entry in data/items/12_1/items.json - run fetch_item_info.pl for them first.\n";
}

print "// Generated by tools/keystoneloot/build_zone_table_js.pl\n";
print "// Do not hand-edit - re-run the script chain in that skill's SKILL.md instead.\n";
print "const KEYSTONE_LOOT_ZONES = ";
print JSON::PP->new->canonical->encode({
    classId  => $sources->{classId},
    specId   => $sources->{specId},
    specName => $favSpec ? $favSpec->{specName} : undef,
    zones    => \@zones,
});
print ";\n";
