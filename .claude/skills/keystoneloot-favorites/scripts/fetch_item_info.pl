#!/usr/bin/perl
# Fetches item info (name, icon, quality, item level, slot, source, tooltip
# text) from Wowhead's tooltip JSON endpoint for a list of item IDs, plus the
# item's icon image (base64-encoded as a data: URI, since an HTML Artifact's
# CSP blocks external image hosts), and upserts the results into
# data/items.json (creating it if missing).
#
# Wowhead endpoint (same family as the /tooltip/spell/<id> one documented in
# .claude/skills/wow-talent-data/SKILL.md - no auth needed):
#   https://nether.wowhead.com/tooltip/item/<itemId>          live
#   https://nether.wowhead.com/tooltip/item/<itemId>?ptr=1    PTR   (untested column;
#     the /ptr/ path segment used for spells 404s for items - pass ?ptr=1 instead if
#     you ever need PTR-only item data. Verify against a known PTR-exclusive item
#     before trusting it, per this project's "don't trust HTTP 200" rule in CLAUDE.md.)
#
# Usage:
#   perl fetch_item_info.pl 251190 251191 193763
#   perl fetch_item_info.pl < item_ids.txt          # one item ID per line
#   perl parse_export.pl "KeystoneLoot:v3,..." | perl extract_item_ids.pl | perl fetch_item_info.pl
#
# Writes/updates data/items.json (path resolved relative to the repo root —
# run this from anywhere inside the repo, or set REPO_ROOT).
#
# Already-cached items are skipped by default (cheap re-runs); pass --force
# to refetch everything.

use strict;
use warnings;
use JSON::PP;
use MIME::Base64 qw(encode_base64);
use FindBin qw($RealBin);
use File::Spec;

# Shells out to curl rather than LWP::UserAgent: the Perl bundled with Git
# for Windows (used throughout this project's tooling, see
# .claude/skills/wowhead-blueposts/SKILL.md) doesn't ship LWP::Protocol::https,
# so HTTPS GETs via LWP fail with "protocol scheme not supported". curl is
# already this project's standard fetch tool and handles TLS natively.
sub http_get {
    my ($url) = @_;
    my @cmd = ('curl', '-sL', '-A', 'Mozilla/5.0 (wow-analysis data pull)', $url);
    open my $fh, '-|', @cmd or return (undef, "failed to launch curl: $!");
    binmode $fh, ':raw';
    local $/;
    my $body = <$fh>;
    close $fh;
    return (undef, "curl exited non-zero") if $? != 0;
    return (undef, "empty response") unless defined $body && length $body;
    return ($body, undef);
}

binmode STDOUT, ':utf8';

my $force = 0;
my @ids;
for my $arg (@ARGV) {
    if ($arg eq '--force') { $force = 1; next; }
    push @ids, $arg;
}

if (!@ids) {
    while (my $line = <STDIN>) {
        $line =~ s/\D//g;
        push @ids, $line if length $line;
    }
}
@ids = grep { /^\d+$/ } @ids;
die "No item IDs given. Usage: perl fetch_item_info.pl <itemId> [itemId ...]\n" unless @ids;

# dedupe, keep order
my %seen;
@ids = grep { !$seen{$_}++ } @ids;

my $repo_root  = $ENV{REPO_ROOT} // File::Spec->catdir($RealBin, '..', '..', '..', '..');
my $items_path = File::Spec->catfile($repo_root, 'data', 'items.json');

my $json = JSON::PP->new->canonical->pretty->utf8;

my %items;
if (-f $items_path) {
    open my $fh, '<:raw', $items_path or die "Can't read $items_path: $!\n";
    local $/;
    my $text = <$fh>;
    close $fh;
    %items = %{ $json->decode($text) } if length $text;
}

my ($fetched, $skipped, $failed) = (0, 0, 0);

for my $id (@ids) {
    if (!$force && exists $items{$id}) {
        $skipped++;
        next;
    }

    my ($body, $err) = http_get("https://nether.wowhead.com/tooltip/item/$id");
    if (!defined $body) {
        warn "  item $id: $err - skipped\n";
        $failed++;
        next;
    }

    my $raw = eval { $json->decode($body) };
    if (!$raw || !$raw->{name}) {
        warn "  item $id: no usable JSON in response - skipped\n";
        $failed++;
        next;
    }

    my $tooltip = $raw->{tooltip} // '';

    my ($itemLevel) = $tooltip =~ /Item Level <!--ilvl-->(\d+)/;
    my ($slot)       = $tooltip =~ m{<table width="100%"><tr><td>([^<]*)</td>};
    my ($difficulty) = $tooltip =~ m{<span style="color: #00FF00">([^<]*)</span>};

    # Every "whtt-extra whtt-<kind>" div is a labeled fact line (Dropped by:,
    # Sold by:, Contained in:, Drop Chance:, Quest:, ...) - collect them all
    # rather than special-casing one kind, since which ones appear depends on
    # the item's source.
    my @sourceLines;
    while ($tooltip =~ m{<div class="whtt-extra whtt-([a-z]+)">(.*?)</div>}g) {
        my ($kind, $text) = ($1, $2);
        $text =~ s/<[^>]+>//g;
        push @sourceLines, { kind => $kind, text => $text };
    }

    my $plainTooltip = $tooltip;
    $plainTooltip =~ s{<br\s*/?>}{\n}gi;
    $plainTooltip =~ s{</(tr|table|div)>}{\n}gi;
    $plainTooltip =~ s{<[^>]+>}{}g;
    $plainTooltip =~ s{[ \t]+}{ }g;
    $plainTooltip =~ s{[ \t]*\n[ \t]*}{\n}g;
    $plainTooltip =~ s{\n{2,}}{\n}g;
    $plainTooltip =~ s{^\s+|\s+$}{}g;

    # Artifacts run under a CSP that blocks every external image host, so the
    # icon has to travel as a data: URI, not a URL — fetch once here and cache
    # it in items.json alongside everything else (see .claude/knowledge/
    # building-reports.md, "Icons and tooltips": ~1-2 KB per icon at `medium`).
    my $iconName = $raw->{icon} // '';
    my $iconDataUri;
    if (length $iconName) {
        my ($iconBytes, $iconErr) = http_get(
            "https://wow.zamimg.com/images/wow/icons/medium/$iconName.jpg");
        if (defined $iconBytes && length $iconBytes) {
            my $b64 = encode_base64($iconBytes, '');
            $iconDataUri = "data:image/jpeg;base64,$b64";
        } else {
            warn "  item $id: icon '$iconName' fetch failed ($iconErr) - no data URI cached\n";
        }
    }

    $items{$id} = {
        itemId       => $id + 0,
        name         => $raw->{name},
        icon         => $iconName,
        quality      => $raw->{quality},
        itemLevel    => defined $itemLevel ? $itemLevel + 0 : undef,
        slot         => $slot,
        difficulty   => $difficulty,
        sourceLines  => \@sourceLines,
        tooltipHtml  => $tooltip,
        tooltipText  => $plainTooltip,
        wowheadUrl   => "https://www.wowhead.com/item=$id",
        iconUrl      => "https://wow.zamimg.com/images/wow/icons/large/$iconName.jpg",
        iconDataUri  => $iconDataUri,
    };
    $fetched++;
    print "  fetched $id: $raw->{name}\n";
}

open my $out, '>:raw', $items_path or die "Can't write $items_path: $!\n";
print $out $json->encode(\%items);
close $out;

print "\n$items_path updated - $fetched fetched, $skipped already cached, $failed failed.\n";
