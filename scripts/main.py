import os
import sys
import csv

replacementTable = {}


class Replacement:
    def __init__(self, name, replacement):
        self.name = name # original name
        self.replacement = replacement # text to replace with
        self.adresses = [] # list of places where replacement is used (for checking)


def load_replacement_table():
    """Load replacement table from constants CSV files."""
    for root, dirs, files in os.walk("../constants"):
        for file in files:
            if file.endswith(".csv"):
                with open(os.path.join(root, file), "r", encoding="utf-8", newline='') as f:
                    reader = csv.reader(f)
                    next(reader, None) # Skip header 1
                    next(reader, None) # Skip header 2
                    for parts in reader:
                        if not parts: continue
                        replacement_text = (
                            parts[1] if sys.argv[1] == "rik"
                            else parts[2]
                        )
                        replacementTable[parts[0]] = Replacement(
                            parts[0],
                            replacement_text + f" /*{parts[0]}*/"
                        )


class Tag:
    @staticmethod
    def fromParts(parts):
        type_val = None
        address = None
        if sys.argv[1] == "rik":
            type_val = parts[2]
            address = parts[3]
        elif sys.argv[1] == "mark":
            type_val = parts[4]
            address = parts[5]
        if address or type_val:
            return Tag([
                parts[0],
                parts[1],
                type_val,
                address,
                parts[6] if len(parts) > 6 else ""
            ])
        return None

    def __init__(self, parts):
        self.specialname = parts[0] or None
        self.tagname = parts[1]
        self.type = parts[2]
        self.address = parts[3]
        self.comment = parts[4] or ""


def parse_csv(path):
    """Parse a CSV file and return list of Tag objects."""
    with open(path, "r", encoding="utf-8") as file:
        lines = file.read().splitlines()
    lines = lines[2:]

    result = []
    for line in lines:
        tag = Tag.fromParts(line.split(","))
        if tag:
            result.append(tag)
    return result

# Load replacement table from constants
load_replacement_table()

# Load tags from CSV files
tags = []
for root, dirs, files in os.walk(os.path.join("..", "tags")):
    for filename in files:
        if filename.endswith(".csv"):
            tags.extend(parse_csv(os.path.join(root, filename)))

# Create output directory and write tags CSV
os.makedirs("../output", exist_ok=True)

with open("../output/tags.csv", "w", encoding="utf-8") as file:
    for tag in tags:
        file.write(
            f"\"{tag.tagname.replace('\"', '\\"')}\", Default Tagtable, {tag.type}, "
            f"%{tag.address}, false, false, false, \"{tag.comment}\"\n"
        )

# Add tags to replacement table
for tag in tags:
    if tag.specialname:
        replacementTable[tag.specialname] = Replacement(tag.specialname, tag.tagname)

# Find replacements in blocks
for root, dirs, files in os.walk(os.path.join("..", "blocks")):
    for item in files:
        with open(os.path.join(root, item), "r", encoding="utf-8") as file:
            content = file.read()
            for replacement_obj in replacementTable.values():
                if replacement_obj.name in content:
                    lines = content.splitlines()
                    line_number = 0
                    while line_number < len(lines):
                        oldline = lines[line_number]
                        col = lines[line_number].find(replacement_obj.name)
                         while col != -1:
                            replacement_obj.adresses.append(
                                f"{replacement_obj.replacement} -> {replacement_obj.name} "
                                f"at {root}/{item} line {line_number + 1} col {col + 1}"
                            )

                            lines[line_number] = lines[line_number].replace(replacement_obj.name, replacement_obj.replacement, 1)
                            col = lines[line_number].find(replacement_obj.name, col + 1)
                        if oldline != lines[line_number]:
                            lines.insert(line_number, f"// {oldline}")
                            line_number += 1
                        line_number += 1
                    content = "\n".join(lines)
        os.makedirs(os.path.join("../output", os.path.relpath(root, "../blocks")), exist_ok=True)
        with open(os.path.join("../output", os.path.relpath(root, "../blocks"), item), "w", encoding="utf-8") as file:
            file.write(content)

# Write patches CSV
with open("../output/patches.csv", "w", encoding="utf-8") as file:

    for key, value in replacementTable.items():
        if len(value.adresses) == 0:
            file.write(f"{key}, {value.name}, No patches\n")
        else:
            file.write(f"{key}, {value.name}\n")
            for address in value.adresses:
                file.write(f",,{address}\n")
