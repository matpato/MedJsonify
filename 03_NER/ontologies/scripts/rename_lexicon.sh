#!/bin/bash
# rename_lexicon.sh - Rename all lexicon files to a simpler name
#
# Usage: ./rename_lexicon.sh <old_name> <new_name> <data_dir>
# Example: ./rename_lexicon.sh ORDO_en_4.8 ordo data/

OLD_NAME="$1"
NEW_NAME="$2"
DATA_DIR="${3:-.}"

if [ -z "$OLD_NAME" ] || [ -z "$NEW_NAME" ]; then
    echo "Usage: $0 <old_name> <new_name> [data_dir]"
    echo "Example: $0 ORDO_en_4.8 ordo data/"
    exit 1
fi

cd "$DATA_DIR" || exit 1

echo "Renaming lexicon from '$OLD_NAME' to '$NEW_NAME'..."

# Count files to rename
file_count=$(ls ${OLD_NAME}* 2>/dev/null | wc -l)

if [ "$file_count" -eq 0 ]; then
    echo "ERROR: No files found with prefix '$OLD_NAME' in $DATA_DIR"
    exit 1
fi

echo "Found $file_count files to rename:"
ls -1 ${OLD_NAME}*

# Rename all files
for file in ${OLD_NAME}*; do
    new_file=$(echo "$file" | sed "s/^${OLD_NAME}/${NEW_NAME}/")
    echo "  $file -> $new_file"
    mv "$file" "$new_file"
done

echo ""
echo "Renaming complete!"
echo ""
echo "You can now use the lexicon as:"
echo "  ./extract_entities.sh \"your text\" $NEW_NAME $DATA_DIR"
echo ""
echo "Files created:"
ls -1 ${NEW_NAME}*