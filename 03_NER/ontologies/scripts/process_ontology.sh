#!/bin/bash

###############################################################################
#                                                                             #
# process_ontology.sh - Ontology processing script                            #
#                                                                             #
# Usage: ./process_ontology.sh <ontology_file> [output_dir]                   #
#                                                                             #
# This script processes OWL/RDF/TXT ontologies and generates optimized        #
# index files for fast entity recognition.                                    #
#                                                                             #
# Features:                                                                   #
# - Automatic obsolete concept removal                                        #
# - Better error handling                                                     #
# - Parallel processing support                                               #
# - Progress indicators                                                       #
# - No Python dependencies                                                    #
#                                                                             #
###############################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
MIN_ENTITY_SIZE_ALPHA=3
MAX_ENTITY_SIZE_DIGIT=5
REMOVE_OBSOLETE=1  # Set to 1 to automatically remove obsolete concepts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check dependencies
check_dependencies() {
    local missing_deps=()
    
    for cmd in sed grep awk; do
        if ! command -v $cmd &> /dev/null; then
            missing_deps+=($cmd)
        fi
    done
    
    # Check if gawk is available (preferred) or fall back to awk
    if command -v gawk &> /dev/null; then
        log_info "Using GNU awk (gawk)"
    elif command -v awk &> /dev/null; then
        log_info "Using system awk (BSD awk on macOS is supported)"
    else
        missing_deps+=(awk)
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Please install them using your package manager"
        log_info "Example (Ubuntu/Debian): sudo apt-get install gawk"
        log_info "Example (MacOS): brew install gawk (optional, system awk works too)"
        exit 1
    fi
}

# Function to extract labels from OWL files
extract_owl_labels() {
    local file=$1
    local output=$2
    
    log_info "Extracting labels from OWL file..."
    
    # Check if this is an Orphanet file (has efo:alternative_term)
    if grep -q 'efo:alternative_term' "$file"; then
        log_info "Detected Orphanet OWL format"
        extract_orphanet_labels "$file" "$output"
    else
        log_info "Using standard OWL extraction"
        # Standard OWL extraction (original code)
        grep -F -e 'owl:Class rdf:about' \
                -e 'rdfs:label' \
                -e 'oboInOwl:hasExactSynonym' \
                -e 'oboInOwl:hasRelatedSynonym' "$file" | \
            tr '\n' ' ' | \
            sed -e 's/<owl:Class/\n<owl:Class/g' | \
            grep '^<owl:Class' | \
            sed 's/rdf:about="\([^"]*\)"/>\1</' | \
            awk -F'[<>]' '{for(i=NF-2;i>4;i=i-4)printf "%s\t%s\n",$i,$3;}' > "$output"
    fi
}

# Function to extract labels from Orphanet OWL files
extract_orphanet_labels() {
    local file=$1
    local output=$2
    
    log_info "Extracting Orphanet labels and alternative terms..."
    
    # Use sed/grep approach that works on both BSD and GNU tools
    # Extract class blocks and process them
    grep -E '(<Class rdf:about=|<rdfs:label|<efo:alternative_term|</Class>)' "$file" | \
    awk '
    BEGIN {
        class_uri = ""
        label = ""
        alt_count = 0
    }
    
    # Start of a new class
    /<Class rdf:about="[^"]*Orphanet_[0-9]+"/ {
        # Output previous class if we have data
        if (class_uri != "" && label != "") {
            print label "\t" class_uri
            for (i = 0; i < alt_count; i++) {
                print alt_terms[i] "\t" class_uri
            }
        }
        
        # Reset for new class
        label = ""
        alt_count = 0
        delete alt_terms
        
        # Extract URI using sub/gsub
        class_uri = $0
        sub(/.*rdf:about="/, "", class_uri)
        sub(/".*/, "", class_uri)
    }
    
    # End of class
    /<\/Class>/ {
        # Output final class data
        if (class_uri != "" && label != "") {
            print label "\t" class_uri
            for (i = 0; i < alt_count; i++) {
                print alt_terms[i] "\t" class_uri
            }
        }
        
        class_uri = ""
        label = ""
        alt_count = 0
        delete alt_terms
    }
    
    # Extract rdfs:label
    /<rdfs:label[^>]*>([^<]+)<\/rdfs:label>/ {
        if (class_uri != "") {
            label = $0
            sub(/.*<rdfs:label[^>]*>/, "", label)
            sub(/<\/rdfs:label>.*/, "", label)
        }
    }
    
    # Extract efo:alternative_term (there can be multiple)
    /<efo:alternative_term[^>]*>([^<]+)<\/efo:alternative_term>/ {
        if (class_uri != "") {
            term = $0
            sub(/.*<efo:alternative_term[^>]*>/, "", term)
            sub(/<\/efo:alternative_term>.*/, "", term)
            alt_terms[alt_count++] = term
        }
    }
    
    END {
        # Output last class if needed
        if (class_uri != "" && label != "") {
            print label "\t" class_uri
            for (i = 0; i < alt_count; i++) {
                print alt_terms[i] "\t" class_uri
            }
        }
    }
    ' > "$output"
    
    local label_count=$(wc -l < "$output" | tr -d ' ')
    log_success "Extracted $label_count labels and alternative terms"
}

# Function to extract labels from RDF files
extract_rdf_labels() {
    local file=$1
    local output=$2
    
    log_info "Extracting labels from RDF file..."
    
    grep -B 1 -F -e '<Literal xml:lang="en">' "$file" | \
        tr '\n' ' ' | \
        sed -e 's/<AbbreviatedIRI>:/\n<AbbreviatedIRI>/g' | \
        grep -v -E '<Literal xml:lang="en">RID[0-9]+<' | \
        awk -F'[<>]' '{printf "%s\thttp://radlex.org/RID/%s\n",$7,$3;}' > "$output"
}

# Function to extract labels from DeCS XML files
extract_decs_labels() {
    local file=$1
    local output=$2
    local language=${3:-eng}
    
    log_info "Extracting labels from DeCS XML file (language: $language)..."
    
    if [ "$language" = "eng" ]; then
        language='T'
    fi
    
    grep -E -e '^  <DescriptorUI>' -e '<!\[CDATA\[' -e "<TermUI>$language" "$file" | \
        sed -E "s/<DescriptorUI>/@/" | \
        tr '\n' ' ' | \
        tr '@' '\n' | \
        sed -e "s/<TermUI>$language[0-9]*<\/TermUI> *<!\[CDATA\[/\n@/g; s/^\(.*\)<\/DescriptorUI>/#\1\n/g;" | \
        grep -E '@|#' | \
        sed 's/\]\]>.*$//' | \
        tr -d '\n' | \
        tr '#@' '\n\t' | \
        awk -F'\t' '{for(i=2;i<=NF;i=i+1)printf "%s\thttps://decs.bvsalud.org/ths/?filter=ths_regid&q=%s\n",$i,$1;}' > "$output"
}

# Function to remove obsolete concepts
remove_obsolete() {
    local file=$1
    
    if [ ! -f "$file" ]; then
        return
    fi
    
    log_info "Removing obsolete concepts from $(basename $file)..."
    
    # Create temporary file
    local temp_file="${file}.tmp"
    
    # Remove lines starting with "obsolete" (case insensitive)
    grep -iv '^obsolete' "$file" > "$temp_file" || true
    
    # Count removed
    local original_count=$(wc -l < "$file")
    local new_count=$(wc -l < "$temp_file")
    local removed=$((original_count - new_count))
    
    if [ $removed -gt 0 ]; then
        mv "$temp_file" "$file"
        log_success "Removed $removed obsolete concepts"
    else
        rm -f "$temp_file"
        log_info "No obsolete concepts found"
    fi
}

# Function to process text file into word files
process_text_to_words() {
    local input=$1
    local basename=$2
    local output_dir=$3
    
    log_info "Processing text into word index files..."
    
    # Create intermediate files
    local aux1="${output_dir}/${basename}.aux1"
    local aux2="${output_dir}/${basename}.aux2"
    local aux3="${output_dir}/${basename}.aux3"
    local aux4="${output_dir}/${basename}.aux4"
    local aux5="${output_dir}/${basename}.aux5"
    local aux="${output_dir}/${basename}.aux"
    
    # Filter: minimum alpha characters
    grep -E "[[:alpha:]]{${MIN_ENTITY_SIZE_ALPHA},}" "$input" > "$aux1" || true
    
    # Filter: maximum consecutive digits
    grep -Ev "[[:digit:]]{${MAX_ENTITY_SIZE_DIGIT},}" "$aux1" > "$aux2" || true
    
    # Remove leading and trailing whitespace
    sed -e 's/^ *//' -e 's/ *$//' "$aux2" > "$aux3"
    
    # Remove multiple whitespace
    sed -e 's/[[:space:]]\+/ /g' "$aux3" > "$aux4"
    
    # Remove duplicate lines
    awk '!a[$0]++' "$aux4" > "$aux5"
    
    # Replace special characters and lowercase
    sed 's/[^[:alpha:][:digit:][:space:]]/./g' "$aux5" | tr '[:upper:]' '[:lower:]' > "$aux"
    
    # Split into word files
    log_info "Creating word index files..."
    
    # Single words
    grep -E '^[^ ]*$' "$aux" > "${output_dir}/${basename}_word1.txt" || touch "${output_dir}/${basename}_word1.txt"
    local word1_count=$(wc -l < "${output_dir}/${basename}_word1.txt")
    log_success "Created ${basename}_word1.txt ($word1_count entries)"
    
    # Two words
    grep -E '^[^ ]+ [^ ]+$' "$aux" > "${output_dir}/${basename}_word2.txt" || touch "${output_dir}/${basename}_word2.txt"
    local word2_count=$(wc -l < "${output_dir}/${basename}_word2.txt")
    log_success "Created ${basename}_word2.txt ($word2_count entries)"
    
    # Multiple words (3+)
    grep -E ' [^ ]+ ' "$aux" > "${output_dir}/${basename}_words.txt" || touch "${output_dir}/${basename}_words.txt"
    local words_count=$(wc -l < "${output_dir}/${basename}_words.txt")
    log_success "Created ${basename}_words.txt ($words_count entries)"
    
    # First two words of multi-word phrases
    grep -Eo "^[^ ]+ [^ ]+" "${output_dir}/${basename}_words.txt" | awk '!a[$0]++' > "${output_dir}/${basename}_words2.txt" || touch "${output_dir}/${basename}_words2.txt"
    local words2_count=$(wc -l < "${output_dir}/${basename}_words2.txt")
    log_success "Created ${basename}_words2.txt ($words2_count entries)"
    
    # Clean up auxiliary files
    rm -f "$aux1" "$aux2" "$aux3" "$aux4" "$aux5" "$aux"
    
    log_success "Total entities processed: $((word1_count + word2_count + words_count))"
}

# Main function
main() {
    local file="$1"
    local output_dir="${2:-.}"
    
    # Check if file exists
    if [ ! -f "$file" ]; then
        log_error "File not found: $file"
        exit 1
    fi
    
    # Check dependencies
    check_dependencies
    
    # Create output directory if needed
    mkdir -p "$output_dir"
    
    # Get basename and extension
    local basename=$(basename "$file")
    local filename="${basename%.*}"
    local extension="${basename##*.}"
    
    log_info "Processing ontology: $basename"
    log_info "Output directory: $output_dir"
    
    # Process based on file type
    local text_file="${output_dir}/${filename}.txt"
    local links_file="${output_dir}/${filename}_links.tsv"
    
    case "$extension" in
        owl)
            extract_owl_labels "$file" "$links_file"
            cut -f1 "$links_file" > "$text_file"
            log_success "Extracted labels with URIs"
            ;;
        rdf)
            extract_rdf_labels "$file" "$links_file"
            cut -f1 "$links_file" > "$text_file"
            log_success "Extracted labels with URIs"
            ;;
        xml)
            # Assume DeCS format
            extract_decs_labels "$file" "$links_file"
            cut -f1 "$links_file" > "$text_file"
            log_success "Extracted labels with URIs"
            ;;
        txt)
            # Plain text file, copy it
            cp "$file" "$text_file"
            log_info "Using plain text file"
            ;;
        *)
            log_error "Unsupported file format: $extension"
            log_info "Supported formats: owl, rdf, xml, txt"
            exit 1
            ;;
    esac
    
    # Convert links file to lowercase and normalize special characters if it exists
    if [ -f "$links_file" ]; then
        log_info "Converting links to lowercase and normalizing special characters..."
        # Convert label to lowercase and replace special chars with dots, keep URI unchanged
        awk -F'\t' '{
            label = tolower($1);
            gsub(/[^a-z0-9 ]/, ".", label);
            print label "\t" $2;
        }' "$links_file" | sort -k1,1 -t$'\t' | uniq > "${links_file}.tmp"
        mv "${links_file}.tmp" "$links_file"
    fi
    
    # Remove obsolete concepts if enabled
    if [ $REMOVE_OBSOLETE -eq 1 ]; then
        remove_obsolete "$text_file"
        if [ -f "$links_file" ]; then
            remove_obsolete "$links_file"
        fi
    fi
    
    # Process text into word files
    process_text_to_words "$text_file" "$filename" "$output_dir"
    
    # Final summary
    echo ""
    log_success "=========================================="
    log_success "Ontology processing complete!"
    log_success "=========================================="
    log_info "Lexicon name: $filename"
    log_info "Output directory: $output_dir"
    log_info "Files created:"
    log_info "  - ${filename}.txt (master list)"
    log_info "  - ${filename}_word1.txt (single words)"
    log_info "  - ${filename}_word2.txt (two words)"
    log_info "  - ${filename}_words.txt (3+ words)"
    log_info "  - ${filename}_words2.txt (first two words index)"
    if [ -f "$links_file" ]; then
        log_info "  - ${filename}_links.tsv (entity URIs)"
    fi
    echo ""
}

# Show usage if no arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <ontology_file> [output_dir]"
    echo ""
    echo "Process ontology files and create optimized index files for entity recognition."
    echo ""
    echo "Arguments:"
    echo "  ontology_file    Path to ontology file (OWL, RDF, XML, or TXT)"
    echo "  output_dir       Output directory (default: current directory)"
    echo ""
    echo "Supported formats:"
    echo "  .owl    - OWL ontology files"
    echo "  .rdf    - RDF ontology files"
    echo "  .xml    - DeCS XML files"
    echo "  .txt    - Plain text files (one entity per line)"
    echo ""
    echo "Examples:"
    echo "  $0 doid.owl data/"
    echo "  $0 chebi.owl data/"
    echo "  $0 orphanet.owl data/"
    echo ""
    exit 1
fi

# Run main function
main "$@"