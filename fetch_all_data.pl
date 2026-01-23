#!/usr/bin/perl
use strict;
use warnings;
use utf8;
use File::Path qw(make_path);
use POSIX qw(strftime);

binmode(STDOUT, ":utf8");

# Configuration
my %LANGUAGES = (
    'uz-Cyrl' => 3,
    'uz' => 4,
    'ru' => 2,
    'en' => 1,
);

my %BASE_URLS = (
    'uz-Cyrl' => 'https://lex.uz',
    'uz' => 'https://lex.uz/uz',
    'ru' => 'https://lex.uz/ru',
    'en' => 'https://lex.uz/en',
);

my %DOC_TYPES = (
    'constitution' => 1,
    'codes' => 21,
    'laws' => 22,
    'president' => 3,
    'government' => 4,
    'ministries' => 5,
    'international' => 6,
);

sub fetch_url {
    my ($url) = @_;
    for my $attempt (1..3) {
        my $content = `curl -s -A "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36" --max-time 60 "$url" 2>/dev/null`;
        return $content if $content && length($content) > 100;
        print "  Attempt $attempt failed for $url\n";
        sleep(5) if $attempt < 3;
    }
    return undef;
}

sub parse_html {
    my ($html) = @_;
    return [] unless $html;
    
    my @docs;
    my %seen;
    
    while ($html =~ /href="(\/(?:uz\/|ru\/|en\/)?docs\/(-?\d+))"[^>]*>([^<]+)/gi) {
        my ($path, $id, $title) = ($1, $2, $3);
        $title =~ s/^\s+|\s+$//g;
        
        next if $seen{$id} || !$title;
        $seen{$id} = 1;
        
        $title =~ s/\$/USD /g;
        
        push @docs, {
            id => $id,
            title => $title,
            url => "https://lex.uz$path",
        };
    }
    
    return \@docs;
}

sub escape_json {
    my ($str) = @_;
    $str =~ s/\\/\\\\/g;
    $str =~ s/"/\\"/g;
    $str =~ s/\n/\\n/g;
    $str =~ s/\r/\\r/g;
    $str =~ s/\t/\\t/g;
    return $str;
}

sub docs_to_json {
    my ($docs) = @_;
    my @items;
    for my $doc (@$docs) {
        my $id = escape_json($doc->{id});
        my $title = escape_json($doc->{title});
        my $url = escape_json($doc->{url});
        push @items, qq(  {"id": "$id", "title": "$title", "url": "$url"});
    }
    return "[\n" . join(",\n", @items) . "\n]";
}

sub fetch_documents {
    my ($doc_type, $act_type) = @_;
    print "\nFetching $doc_type...\n";
    my %results;
    
    for my $lang (keys %LANGUAGES) {
        my $lang_param = $LANGUAGES{$lang};
        my $base_url = $BASE_URLS{$lang};
        my $url = "$base_url/search/all?act_type=$act_type&lang=$lang_param";
        
        print "  $lang: $url\n";
        my $html = fetch_url($url);
        my $docs = parse_html($html);
        $results{$lang} = $docs;
        print "    Found " . scalar(@$docs) . " documents\n";
        
        sleep(2);
    }
    
    return \%results;
}

sub fetch_news {
    print "\nFetching news...\n";
    my %results;
    my $today = strftime("%d.%m.%Y", localtime);
    
    for my $lang (keys %LANGUAGES) {
        my $lang_param = $LANGUAGES{$lang};
        my $base_url = $BASE_URLS{$lang};
        my $url = "$base_url/search/all?from=01.01.2020&to=$today&lang=$lang_param";
        
        print "  $lang: $url\n";
        my $html = fetch_url($url);
        my $docs = parse_html($html);
        $results{$lang} = $docs;
        print "    Found " . scalar(@$docs) . " documents\n";
        
        sleep(2);
    }
    
    return \%results;
}

sub save_json {
    my ($json_str, $filename) = @_;
    open(my $fh, '>:encoding(UTF-8)', $filename) or die "Cannot open $filename: $!";
    print $fh $json_str;
    close($fh);
    print "Saved $filename\n";
}

# Main
print "=" x 50 . "\n";
print "Lex.uz Data Fetcher\n";
print "Started at: " . strftime("%Y-%m-%dT%H:%M:%SZ", gmtime) . "\n";
print "=" x 50 . "\n";

my %all_data;

# Fetch all document types
for my $doc_type (keys %DOC_TYPES) {
    $all_data{$doc_type} = fetch_documents($doc_type, $DOC_TYPES{$doc_type});
}

# Fetch news
$all_data{'news'} = fetch_news();

# Create data directory
make_path('data');

# Build metadata
my @meta_types;
my $last_updated = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime);

for my $doc_type (sort keys %all_data) {
    my @lang_entries;
    
    for my $lang (sort keys %{$all_data{$doc_type}}) {
        my $lang_safe = $lang;
        $lang_safe =~ s/-/_/g;
        my $filename = "data/${doc_type}_${lang_safe}.json";
        my $docs = $all_data{$doc_type}{$lang};
        my $count = scalar(@$docs);
        
        # Save document file
        save_json(docs_to_json($docs), $filename);
        
        push @lang_entries, qq(    "$lang": {"file": "$filename", "count": $count});
    }
    
    push @meta_types, qq(  "$doc_type": {\n) . join(",\n", @lang_entries) . "\n  }";
}

# Save metadata
my $metadata_json = qq({
  "last_updated": "$last_updated",
  "document_types": {
) . join(",\n", @meta_types) . qq(
  }
});

save_json($metadata_json, 'metadata.json');

print "\n" . "=" x 50 . "\n";
print "Fetch complete!\n";
print "Finished at: " . strftime("%Y-%m-%dT%H:%M:%SZ", gmtime) . "\n";
print "=" x 50 . "\n";
