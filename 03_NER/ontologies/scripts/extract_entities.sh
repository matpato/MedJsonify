#!/bin/bash

###############################################################################
#                                                                             #
# extract_entities.sh - Entity extraction with all matches                   #
#                                                                             #
# Usage: ./extract_entities.sh <text> <lexicon_name> [data_dir]              #
#                                                                             #
# Extracts ALL matching entities, including overlapping ones                 #
# Output format: START\tEND\tENTITY\tURI (tab-separated)                     #
#                                                                             #
###############################################################################

set -u  # Exit on undefined variable

# Configuration
USE_STOPWORDS=1
MIN_WORD_LENGTH=3
STOPWORDS_FILE="stopwords.txt"
DEBUG=${DEBUG:-0}

# Debug function
debug() {
    if [ $DEBUG -eq 1 ]; then
        echo "[DEBUG] $1" >&2
    fi
}

# Create stopwords file if missing
create_stopwords() {
    if [ ! -f "$STOPWORDS_FILE" ]; then
        cat > "$STOPWORDS_FILE" << 'EOF'
the
a
an
and
or
but
in
on
at
to
for
of
with
by
from
up
about
into
through
during
before
after
above
below
between
under
is
are
was
were
be
been
being
have
has
had
do
does
did
will
would
should
could
may
might
must
can
all
some
any
each
every
this
that
these
those
EOF
        debug "Created default stopwords file"
    fi
}

# Parse arguments
SHOW_URI=true
POSITIONAL_ARGS=()

# First pass: extract flags and collect positional arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-uri|-u|-U)
            SHOW_URI=false
            shift
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Set positional arguments
set -- "${POSITIONAL_ARGS[@]}"

TEXT="${1:-}"
LEXICON="${2:-}"
DATA_DIR="${3:-.}"

debug "Text: '$TEXT'"
debug "Lexicon: '$LEXICON'"
debug "Data directory: '$DATA_DIR'"
debug "Show URI: $SHOW_URI"

# Validate
if [ -z "$TEXT" ] || [ -z "$LEXICON" ]; then
    echo "Usage: $0 [--no-uri|-u] <text> <lexicon_name> [data_dir]" >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  --no-uri, -u, -U    Output only START, END, and ENTITY (no URI column)" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0 'text with asthma' doid data/" >&2
    echo "  $0 --no-uri 'text with asthma' doid data/" >&2
    echo "  $0 -u 'text with asthma' doid data/" >&2
    exit 1
fi

# Check data directory
if [ ! -d "$DATA_DIR" ]; then
    echo "ERROR: Data directory not found: $DATA_DIR" >&2
    exit 1
fi

# Check lexicon files
WORD1_FILE="${DATA_DIR}/${LEXICON}_word1.txt"
WORD2_FILE="${DATA_DIR}/${LEXICON}_word2.txt"
WORDS_FILE="${DATA_DIR}/${LEXICON}_words.txt"
WORDS2_FILE="${DATA_DIR}/${LEXICON}_words2.txt"
LINKS_FILE="${DATA_DIR}/${LEXICON}_links.tsv"

debug "Checking lexicon files..."
for file in "$WORD1_FILE" "$WORD2_FILE" "$WORDS_FILE" "$WORDS2_FILE"; do
    if [ ! -f "$file" ]; then
        echo "ERROR: Missing $(basename $file)" >&2
        exit 1
    fi
done
debug "All lexicon files found!"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not found" >&2
    exit 1
fi

# Create stopwords if needed
if [ $USE_STOPWORDS -eq 1 ]; then
    create_stopwords
fi

# Save original text
ORIGINAL_TEXT="$TEXT"
ORIGINAL_LOWER=$(echo "$TEXT" | tr '[:upper:]' '[:lower:]')
debug "Original text length: ${#ORIGINAL_TEXT}"

# Preprocess text for matching
debug "Preprocessing text..."

# 1. Lowercase
PROCESSED_TEXT=$(echo "$TEXT" | tr '[:upper:]' '[:lower:]')

# 2. Replace punctuation with spaces
PROCESSED_TEXT=$(echo "$PROCESSED_TEXT" | sed 's/[,.;:!?()-]/ /g')

# 3. Replace non-alphanumeric (except spaces) with dots
PROCESSED_TEXT=$(echo "$PROCESSED_TEXT" | sed 's/[^a-z0-9 ]/./g')

# 4. Normalize whitespace
PROCESSED_TEXT=$(echo "$PROCESSED_TEXT" | tr -s ' ')

# 5. Remove stopwords (improved method)
if [ $USE_STOPWORDS -eq 1 ] && [ -f "$STOPWORDS_FILE" ]; then
    debug "Removing stopwords..."
    # Build a temporary file with each word on a line
    echo "$PROCESSED_TEXT" | tr ' ' '\n' > /tmp/words_temp.txt
    # Filter out stopwords using grep
    PROCESSED_TEXT=$(grep -vxFf "$STOPWORDS_FILE" /tmp/words_temp.txt 2>/dev/null | tr '\n' ' ')
    rm -f /tmp/words_temp.txt
fi

# 6. Normalize whitespace again after stopword removal
PROCESSED_TEXT=$(echo "$PROCESSED_TEXT" | tr -s ' ')

# 7. Trim
PROCESSED_TEXT=$(echo "$PROCESSED_TEXT" | sed 's/^ *//;s/ *$//')
debug "Final processed text: '$PROCESSED_TEXT'"

# Exit if empty
if [ -z "$PROCESSED_TEXT" ]; then
    debug "No text remaining after preprocessing"
    exit 0
fi

# Function to find ALL positions of entity in original text (case-insensitive)
find_all_positions() {
    local entity="$1"
    local pattern="$entity"
    
    # Escape special regex characters for pattern matching
    pattern=$(echo "$pattern" | sed 's/\./[^ ]/g')
    
    # Use Python for more reliable position finding
    python3 << EOF
import re
import sys

text = " ${ORIGINAL_LOWER} "
entity = "${entity}"
pattern = r'\b' + re.escape(entity).replace(r'\.', r'\w') + r'\b'

for match in re.finditer(pattern, text, re.IGNORECASE):
    # Adjust for the space we added at the beginning
    start = match.start() - 1
    end = match.end() - 1
    matched_text = text[match.start():match.end()].strip()
    # Get the actual case from original text
    actual_match = "${ORIGINAL_TEXT}"[start:end]
    print(f"{start}\t{end}\t{actual_match}")
EOF
}

# Function to format output line (with or without URI based on SHOW_URI flag)
format_output() {
    local start="$1"
    local end="$2"
    local matched="$3"
    local uri="$4"
    
    if [ "$SHOW_URI" = true ]; then
        echo -e "${start}\t${end}\t${matched}\t${uri}"
    else
        echo -e "${start}\t${end}\t${matched}"
    fi
}

# Function to lookup URI (portable version without awk dependency)
lookup_uri() {
    local entity="$1"
    
    if [ ! -f "$LINKS_FILE" ]; then
        debug "    Links file not found: $LINKS_FILE"
        echo ""
        return
    fi
    
    # Clean entity for lookup (remove dots, normalize spaces, lowercase)
    local clean=$(echo "$entity" | sed 's/\./ /g' | tr -s ' ' | sed 's/^ *//;s/ *$//' | tr '[:upper:]' '[:lower:]')
    
    debug "    Looking up URI for: '$clean' in $LINKS_FILE"
    
    # Method 1: Try exact match with optional L prefix using grep and cut
    # This works with both GNU and BSD grep
    local uri=""
    local tab=$(printf '\t')
    
    # First try: exact match with L prefix (e.g., "Lasthma")
    uri=$(grep -i "^l${clean}${tab}" "$LINKS_FILE" 2>/dev/null | head -1 | cut -f2)
    
    # Second try: exact match without L prefix (in case file doesn't have L)
    if [ -z "$uri" ]; then
        uri=$(grep -i "^${clean}${tab}" "$LINKS_FILE" 2>/dev/null | head -1 | cut -f2)
    fi
    
    if [ -n "$uri" ]; then
        debug "    Found URI: $uri"
        echo "$uri"
    else
        debug "    No URI found for '$clean'"
        # Debug: show what's actually in the file for this term
        if [ $DEBUG -eq 1 ]; then
            debug "    Checking links file for similar entries..."
            local count=$(wc -l < "$LINKS_FILE" 2>/dev/null || echo "0")
            debug "    Total entries in links file: $count"
            
            # Show first few lines to understand format
            debug "    First 3 lines of links file:"
            head -3 "$LINKS_FILE" 2>/dev/null | while IFS= read -r line; do
                debug "      |$line|"
            done
            
            # Show what asthma/copd look like in file
            debug "    Looking for similar entries to '$clean':"
            grep -iE "^l?${clean}" "$LINKS_FILE" 2>/dev/null | head -3 | while IFS= read -r line; do
                debug "      Entry: |$line|"
            done
        fi
        echo ""
    fi
}

# Split processed text into words array
IFS=' ' read -ra WORDS <<< "$PROCESSED_TEXT"
debug "Word array size before stopword filter: ${#WORDS[@]}"

# Filter out stopwords from the WORDS array (using grep, compatible with older bash)
if [ $USE_STOPWORDS -eq 1 ] && [ -f "$STOPWORDS_FILE" ]; then
    FILTERED_WORDS=()
    for word in "${WORDS[@]}"; do
        # Check if word is in stopwords file
        if grep -qxF "$word" "$STOPWORDS_FILE" 2>/dev/null; then
            debug "  Filtering stopword: $word"
        else
            FILTERED_WORDS+=("$word")
        fi
    done
    WORDS=("${FILTERED_WORDS[@]}")
fi

debug "Word array size after stopword filter: ${#WORDS[@]}"

# Temporary file for results
TEMP_RESULTS=$(mktemp)

# 1. Match multi-word phrases (3+ words)
debug "Matching multi-word phrases..."
for ((i=0; i<${#WORDS[@]}-2; i++)); do
    for ((len=5; len>=3 && i+len<=${#WORDS[@]}; len--)); do
        # Build phrase
        phrase="${WORDS[$i]}"
        for ((j=1; j<len; j++)); do
            phrase="$phrase ${WORDS[$i+$j]}"
        done
        
        # Check if phrase exists in lexicon
        if grep -qxF "$phrase" "$WORDS_FILE" 2>/dev/null; then
            debug "  Found multi-word: $phrase"
            
            # Find ALL positions of this entity
            while IFS=$'\t' read -r start end matched; do
                if [ -n "$start" ]; then
                    # Lookup URI if needed
                    if [ "$SHOW_URI" = true ]; then
                        uri=$(lookup_uri "$phrase")
                    else
                        uri=""
                    fi
                    
                    # Output with optional URI
                    format_output "$start" "$end" "$matched" "$uri" >> "$TEMP_RESULTS"
                    debug "    Added: $matched (${start}-${end}) URI: $uri"
                fi
            done < <(find_all_positions "$phrase")
        fi
    done
done

# 2. Match two-word phrases
debug "Matching two-word phrases..."
for ((i=0; i<${#WORDS[@]}-1; i++)); do
    phrase="${WORDS[$i]} ${WORDS[$i+1]}"
    
    # Check if phrase exists in lexicon
    if grep -qxF "$phrase" "$WORD2_FILE" 2>/dev/null; then
        debug "  Found two-word: $phrase"
        
        # Find ALL positions of this entity
        while IFS=$'\t' read -r start end matched; do
            if [ -n "$start" ]; then
                # Lookup URI if needed
                if [ "$SHOW_URI" = true ]; then
                    uri=$(lookup_uri "$phrase")
                else
                    uri=""
                fi
                
                # Output with optional URI
                format_output "$start" "$end" "$matched" "$uri" >> "$TEMP_RESULTS"
                debug "    Added: $matched (${start}-${end}) URI: $uri"
            fi
        done < <(find_all_positions "$phrase")
    fi
done

# 3. Match single words
debug "Matching single words..."
for word in "${WORDS[@]}"; do
    # Skip short words
    if [ ${#word} -lt $MIN_WORD_LENGTH ]; then
        continue
    fi
    
    # Check if word exists in lexicon
    if grep -qxF "$word" "$WORD1_FILE" 2>/dev/null; then
        debug "  Found single word: $word"
        
        # Find ALL positions of this word
        while IFS=$'\t' read -r start end matched; do
            if [ -n "$start" ]; then
                # Lookup URI if needed
                if [ "$SHOW_URI" = true ]; then
                    uri=$(lookup_uri "$word")
                else
                    uri=""
                fi
                
                # Output with optional URI
                format_output "$start" "$end" "$matched" "$uri" >> "$TEMP_RESULTS"
                debug "    Added: $matched (${start}-${end}) URI: $uri"
            fi
        done < <(find_all_positions "$word")
    fi
done

# Output results: sorted by position, remove duplicates, output as pure TSV
if [ -s "$TEMP_RESULTS" ]; then
    total=$(wc -l < "$TEMP_RESULTS")
    debug "Total matches before dedup: $total"
    
    # Sort by start position (column 1), then end position (column 2)
    # Remove duplicate lines, output as TAB-separated
    sort -t$'\t' -k1,1n -k2,2n "$TEMP_RESULTS" | uniq
    
    debug "Results output complete"
else
    debug "No entities found"
fi

# Cleanup
rm -f "$TEMP_RESULTS"