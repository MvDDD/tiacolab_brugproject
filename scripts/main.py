import os
import sys

replacementTable = {}

class Replacement():
    def __init__(self, name, replacement):
        self.name = name
        self.replacement = replacement
        self.adresses = []

for root, dirs, files in os.walk("../constants"):
    for file in files:
        if file.endswith(".csv"):
            with open(os.path.join(root, file), "r") as f:
                lines = f.read().splitlines()
                for line in lines[2:]:
                    parts = line.split(",")
                    replacementTable[parts[0]] = \
                        Replacement(parts[0],
                            (
                                parts[1] if sys.argv[1] == "rik" 
                                else parts[2]
                            ) + f" /*{parts[0]}*/")


class Tag():
    @staticmethod
    def fromParts(parts):
        type = None
        address = None
        if sys.argv[1] == "rik":
            type = parts[2]
            address = parts[3]
        elif sys.argv[1] == "mark":
            type = parts[4]
            address = parts[5]
        if address or type:
            return Tag([parts[0], parts[1], type, address, parts[6] if len(parts) > 6 else ""])
        return None
    def __init__(self, parts):
        self.specialname = parts[0] or None
        self.tagname = f"\"{parts[1]}\""
        self.type = parts[2]
        self.address = parts[3]
        self.comment = parts[4] or ""



def parse_csv(path):
    with open(path, "r") as file:
        lines = file.read().splitlines()
    lines = lines[2:]
    
    result = []
    for line in lines:
        tag = Tag.fromParts(line.split(","))
        if tag:
            result.append(tag)
    return result


tags = []
for root, dirs, files in os.walk(os.path.join("..", "tags")):
    for item in files:
        if item.endswith(".csv"):
            tags.extend(parse_csv(os.path.join(root, item)))

os.makedirs("../output", exist_ok=True)
with open("../output/tags.csv", "w") as file:
    for tag in tags:
        file.write(f"{tag.tagname}, Default Tagtable, {tag.type}, %{tag.address}, false, false, false, \"{tag.comment}\"\n")


for tag in tags:
    if tag.specialname:
        replacementTable[tag.specialname] = Replacement(f"\"{tag.tagname}\"", tag.specialname)

for root, dirs, files in os.walk(os.path.join("..", "blocks")):
    for item in files:
        with open(os.path.join(root, item), "r") as file:
            content = file.read()
            for item in replacementTable.values():
                if item.replacement in content:
                    index = content.find(item.replacement)
                    while index != -1:
                        lines = content.split("\n")
                        for line_number, line in enumerate(lines):
                            col = line.find(item.replacement)
                            while col != -1:
                                item.adresses.append(f"{item.replacement} in {item.name} at {root}/{item.name} line {line_number + 1} col {col + 1}")
                                line = line.replace(item.replacement, item.name, 1)
                                col = line.find(item.replacement)
                                replacementTable[item.name].adresses.append(f"{item.replacement} in {item.name} at {root}/{item.name} line {line_number + 1} col {col + 1}")


# patches are are file/line/offset where replacements have been made.
# save them in a csv so they can be used to check the output of the patcher.
with open("../output/patches.csv", "w") as file:
    for key, value in replacementTable.items():
        if len(value.adresses) == 0:
            file.write(f"{key}, {value.name}, No patches\n")
        else:
            file.write(f"{key}, {value.name}\n,,{",,\n".join(value.adresses)}\n")


