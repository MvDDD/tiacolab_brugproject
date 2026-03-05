import os
import sys
import csv
import siemens_tia_scripting as tia
portal = tia.attach_portal()
print(portal.get_process_id())

blocknames = {
  "system": {
    "1": {
      "ARGUMENTS": {},
      "DESCR": "system.Main",
      "LONGNAME": "OB1 - Main program executed every PLC scan"
    },
    "10": {
      "ARGUMENTS": {},
      "DESCR": "system.StartupCold",
      "LONGNAME": "OB10 - Executed once after PLC cold restart"
    },
    "11": {
      "ARGUMENTS": {},
      "DESCR": "system.StartupWarm",
      "LONGNAME": "OB11 - Executed once after PLC warm restart"
    },
    "30": {
      "ARGUMENTS": {},
      "DESCR": "system.HighCyclic",
      "LONGNAME": "OB30 - Executed cyclically with high priority"
    },
    "31": {
      "ARGUMENTS": {},
      "DESCR": "system.MediumCyclic",
      "LONGNAME": "OB31 - Executed cyclically with medium priority"
    },
    "32": {
      "ARGUMENTS": {},
      "DESCR": "system.LowCyclic",
      "LONGNAME": "OB32 - Executed cyclically with low priority"
    },
    "35": {
      "ARGUMENTS": {"HW": "Input/Output"},
      "DESCR": "system.HWInterrupt",
      "LONGNAME": "OB35 - Triggered by hardware input change"
    },
    "40": {
      "ARGUMENTS": {"FaultCode": "INT"},
      "DESCR": "system.HWFault",
      "LONGNAME": "OB40 - Executed on hardware fault"
    },
    "82": {
      "ARGUMENTS": {"FaultCode": "INT"},
      "DESCR": "system.CPUFault",
      "LONGNAME": "OB82 - Executed on CPU fault"
    },
    "100": {
      "ARGUMENTS": {},
      "DESCR": "system.StartupInit",
      "LONGNAME": "OB100 - Executed once on PLC startup"
    }
  }
}

replacementTable = {}


class Replacement:
    def __init__(self, name, replacement):
        self.name = name # original name
        self.replacement = replacement # text to replace with
        self.addresses = [] # list of places where replacement is used (for checking)


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
    result = []
    with open(path, "r", encoding="utf-8", newline='') as file:
        reader = csv.reader(file)
        # Skip header lines
        next(reader, None)
        next(reader, None)
        for parts in reader:
            tag = Tag.fromParts(parts)
            if tag:
                result.append(tag)
    return result

# Load replacement table from constants
for root, dirs, files in os.walk("constants"):
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

# Load tags from CSV files
tags = []
for root, dirs, files in os.walk("tags"):
    for filename in files:
        if filename.endswith(".csv"):
            tags.extend(parse_csv(os.path.join(root, filename)))

# Create output directory and write tags CSV
os.makedirs("output", exist_ok=True)

with open("output/tags.csv", "w", encoding="utf-8") as file:
    for tag in tags:
        file.write(
            f"\"{tag.tagname.replace('\"', '\\"')}\", Default Tagtable, {tag.type}, "
            f"%{tag.address}, false, false, false, \"{tag.comment}\"\n"
        )

# Add tags to replacement table
for tag in reversed(sorted(tags, key=lambda t: len(t.specialname) if t.specialname else 0)):
    if tag.specialname:
        replacementTable[tag.specialname] = Replacement(tag.specialname, tag.tagname)

def getObName(basename):
    return "main." + blocknames["system"][basename[2:]]["DESCR"].split(".")[1].title()

def getObArgs(basename):
    return basename

def getFcName(basename):
    return basename

# Find replacements in blocks
createdBlocks = set()
available = [item for item in os.listdir("blocks") if os.path.isdir(os.path.join("blocks", item))]
for blocktype in available:
    for root, dirs, files in os.walk(os.path.join("..", "blocks", blocktype)):
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
                                replacement_obj.addresses.append(
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
            os.makedirs(os.path.join("../output/blocks", os.path.relpath(root, "blocks")), exist_ok=True)
            createdBlocks.add(os.path.relpath(os.path.join(root, "blocks"), item))
            with open(os.path.join("../output/blocks", os.path.relpath(root, "blocks"), item), "w", encoding="utf-8") as file:
                basename = os.path.splitext(os.path.basename(item))[0]
                if blocktype == "OB":
                    name = getObName(basename)
                    args = getObArgs(basename)
                    file.write(f'FUNCTION "{name}"\nTITLE = "{name}"\n{{ S7_Optimized_Access := \'TRUE\' }}\nVERSION : 0.1\n\nBEGIN\n')
                if blocktype == "FC":
                    name = getFcName(basename)
                    file.write(f'FUNCTION "{name}"\nTITLE = "{name}"\nVERSION : 0.1\n\nBEGIN\n')
                
                file.write(content)
                if blocktype == "OB":
                    file.write('END_FUNCTION\n')
                if blocktype == "FC":
                    file.write('END_FUNCTION\n')
                

# Write patches CSV
with open("../output/patches.csv", "w", encoding="utf-8", newline='') as file:
    writer = csv.writer(file)
    for key, value in replacementTable.items():
        if len(value.addresses) == 0:
            writer.writerow([key, value.name, "No patches"])
        else:
            writer.writerow([key, value.name])
            for address in value.addresses:
                writer.writerow(["", "", address])


print(list(createdBlocks))
import sys;sys.exit(0)
try:
    portal = tia.attach_portal()
except Exception as e:
    # async open proccess (detached from this script)
    os.startfile(os.path.join(os.getcwd(), "template", "template.ap20"))
    import time
    connected = False
    portal = None
    while connected == False:
        try:
            print("Trying to connect to TIA Portal...")
            portal = tia.attach_portal()
            connected = True
        except Exception as e:
            time.sleep(5)

project = portal.get_project()
if project is not None:
    project.save()
    project.close()
print("step 1 done")
import shutil
shutil.rmtree(os.path.join(os.getcwd(), "output", "project"), ignore_errors=True)
shutil.copytree(os.path.join(os.getcwd(), "template"), os.path.join(os.getcwd(), "output", "project"))
project = portal.open_project(os.path.join(os.getcwd(), "output", "project", "template.ap20"))

plcs = project.get_plcs()
plc = plcs[0]
plc.open_device_editor()
