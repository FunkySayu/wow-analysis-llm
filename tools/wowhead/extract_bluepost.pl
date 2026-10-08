#!/usr/bin/perl
# Extracts the embedded blue-post JSON from a saved Wowhead
# /blue-tracker/topic/<region>/<id> page and prints it as plain text.
#
# Usage: perl extract_bluepost.pl <path-to-saved-html>
#
# Wowhead server-renders each blue post's raw HTML body into a
# <script type="application/json" id="data.blueTracker.topic"> tag
# (entries[].body). This avoids needing a JS-executing browser: the
# page's visible DOM is populated client-side from this same JSON, so
# reading the tag directly is both simpler and more reliable than
# scraping rendered markup.

use strict;
use warnings;
use JSON::PP;
use HTML::Entities qw(decode_entities);

binmode STDOUT, ':utf8';

local $/;
my $html = <>;

my ($json_str) = $html =~ m{<script type="application/json" id="data\.blueTracker\.topic">(.*?)</script>}s;
if (!defined $json_str) {
    print STDERR "No data.blueTracker.topic JSON found in input — page structure may have changed.\n";
    exit 1;
}

my $data = decode_json($json_str);
my @entries = @{ $data->{entries} || [] };
if (!@entries) {
    print STDERR "No blue post entries found in JSON.\n";
    exit 1;
}

for my $entry (@entries) {
    my $author = $entry->{author} // 'Unknown';
    my $date   = $entry->{date}   // $entry->{posted} // '';
    print "=" x 70, "\n";
    print "$author — $date\n";
    print "=" x 70, "\n\n";

    my $body = $entry->{body} // '';
    # Block-level tags become paragraph/line breaks before stripping.
    $body =~ s{</(p|li|h[1-6]|div)>}{\n\n}gi;
    $body =~ s{<br\s*/?>}{\n}gi;
    $body =~ s{<hr\s*/?>}{\n----------------------------------------\n}gi;
    $body =~ s{<li>}{ - }gi;
    $body =~ s{<[^>]+>}{}g;          # strip all remaining tags
    $body = decode_entities($body);
    $body =~ s{\n{3,}}{\n\n}g;       # collapse excess blank lines
    $body =~ s{^\s+|\s+$}{}g;

    print "$body\n\n";
}
