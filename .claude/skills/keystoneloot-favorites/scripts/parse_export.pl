#!/usr/bin/perl
# Decodes a KeystoneLoot addon "favorites" export string (v3 format) into
# structured JSON.
#
# Format (see the addon's own modules/favorites.lua, function Export):
#   KeystoneLoot:v3,<base64( zlib( json ) )>
#   json = { "<specId>": [ {itemId, tier, bonusIds?, gems?, enchant?}, ... ], ... }
# tier is an integer 1-5: 1=Nice to have, 2=Must have, 3=Best in Slot,
# 4=Transmog, 5=Catalyst (Favorites.TIER_NAME in the addon source).
#
# Usage:
#   perl parse_export.pl "KeystoneLoot:v3,eJx9kj..."
#   perl parse_export.pl < export.txt
#
# Prints JSON to stdout:
#   { "62": { "specName": "Arcane Mage", "items": [
#       { "itemId": 251190, "tier": 3, "tierName": "Best in Slot", ... }, ... ] }, ... }

use strict;
use warnings;
use MIME::Base64 qw(decode_base64);
use Compress::Zlib qw(uncompress);
use JSON::PP;

binmode STDOUT, ':utf8';

my $input = shift @ARGV;
if (!defined $input) {
    local $/;
    $input = <STDIN>;
}
die "Usage: perl parse_export.pl \"KeystoneLoot:v3,<data>\"  (or pipe it via stdin)\n"
    unless defined $input && length $input;

$input =~ s/^\s+|\s+$//g;

my ($prefix, $payload) = $input =~ /^(KeystoneLoot:v\d+),(.+)$/s;
die "Not a recognizable KeystoneLoot export string (expected 'KeystoneLoot:vN,<data>').\n"
    unless defined $payload;
die "Only the v3 export format is supported by this script, got '$prefix'.\n"
    unless $prefix eq 'KeystoneLoot:v3';

my $compressed = decode_base64($payload);
die "Base64 decode produced no data — string may be truncated.\n"
    unless length $compressed;

my $json_text = uncompress($compressed);
die "Zlib decompression failed — string may be truncated or corrupted.\n"
    unless defined $json_text;

my $data = decode_json($json_text);

# WoW spec IDs -> display names, for readability only (not used for decoding).
my %SPEC_NAME = (
    62 => 'Arcane Mage', 63 => 'Fire Mage', 64 => 'Frost Mage',
    65 => 'Holy Paladin', 66 => 'Protection Paladin', 70 => 'Retribution Paladin',
    71 => 'Arms Warrior', 72 => 'Fury Warrior', 73 => 'Protection Warrior',
    102 => 'Balance Druid', 103 => 'Feral Druid', 104 => 'Guardian Druid', 105 => 'Restoration Druid',
    250 => 'Blood Death Knight', 251 => 'Frost Death Knight', 252 => 'Unholy Death Knight',
    253 => 'Beast Mastery Hunter', 254 => 'Marksmanship Hunter', 255 => 'Survival Hunter',
    256 => 'Discipline Priest', 257 => 'Holy Priest', 258 => 'Shadow Priest',
    259 => 'Assassination Rogue', 260 => 'Outlaw Rogue', 261 => 'Subtlety Rogue',
    262 => 'Elemental Shaman', 263 => 'Enhancement Shaman', 264 => 'Restoration Shaman',
    265 => 'Affliction Warlock', 266 => 'Demonology Warlock', 267 => 'Destruction Warlock',
    268 => 'Brewmaster Monk', 269 => 'Windwalker Monk', 270 => 'Mistweaver Monk',
    577 => 'Havoc Demon Hunter', 581 => 'Vengeance Demon Hunter',
    1467 => 'Devastation Evoker', 1468 => 'Preservation Evoker', 1473 => 'Augmentation Evoker',
);

# Favorites.TIER_NAME from modules/favorites.lua
my %TIER_NAME = (1 => 'Nice to have', 2 => 'Must have', 3 => 'Best in Slot',
                  4 => 'Transmog', 5 => 'Catalyst');

my %out;
for my $specKey (keys %$data) {
    my $specId = $specKey + 0;
    my @items;
    for my $entry (@{ $data->{$specKey} }) {
        push @items, {
            itemId   => $entry->{itemId} + 0,
            tier     => $entry->{tier},
            tierName => $TIER_NAME{ $entry->{tier} } // 'Unknown',
            bonusIds => $entry->{bonusIds},
            gems     => $entry->{gems},
            enchant  => $entry->{enchant},
        };
    }
    @items = sort { $a->{tier} <=> $b->{tier} || $a->{itemId} <=> $b->{itemId} } @items;
    $out{$specKey} = {
        specId   => $specId,
        specName => $SPEC_NAME{$specId} // "Unknown spec $specId",
        items    => \@items,
    };
}

print JSON::PP->new->canonical->pretty->encode(\%out);
