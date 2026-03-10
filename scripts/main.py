import os
import sys
import csv
import subprocess
import siemens_tia_scripting as tia

open("./tia.log", "w").close()
tia.set_logging("./tia.log", False)

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
    alltags = []
    memoryCounter = 0
    @staticmethod
    def fromParts(parts):
        try:
            type_val = None
            address = None
            if sys.argv[1] == "rik":
                type_val = parts[2]
                address = parts[3]
            elif sys.argv[1] == "mark":
                type_val = parts[4]
                address = parts[5]
            if address and type_val and parts[1]:
                return Tag([
                    parts[0],
                    parts[1],
                    type_val,
                    address,
                    parts[6] if len(parts) > 6 else ""
                ])
        except IndexError as e:
            print(f"malformed tag: {parts}")
        return None
    @staticmethod
    def getByteSize(type):
        match type:
            case "Bool": return 1/8
            case "Char": return 1
            case "Byte": return 1
            case "Word": return 2
            case "DWord": return 4
            case "Real": return 4
            case "LReal": return 8
            case "USInt": return 1
            case "Int": return 2
            case "UDInt": return 4
            case "Time": return 4
            case "Date": return 2
            case "TOD": return 4
            case "DTL": return 12
            case "String": return 254


    def __init__(self, parts):
        self.specialname = parts[0] or None
        self.tagname = parts[1]
        self.type = parts[2]
        self.address = parts[3]
        self.comment = parts[4] or ""
        self.byteSize = Tag.getByteSize(self.type)
        # check if the tag fits in the current memory config

        Tag.alltags.append(self)

        


def parse_csv(path):
    """Parse a CSV file and return list of Tag objects."""
    result = []
    with open(path, "r", encoding="utf-8", newline='') as file:
        reader = csv.reader(file)
        # Skip header lines
        next(reader, None)
        next(reader, None)
        for parts in reader:
            items = [part.strip() for part in parts]
            tag = Tag.fromParts(items)
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
    writer = csv.writer(file)
    for tag in tags:
        writer.writerow([tag.tagname.strip('"'), "Default Tagtable", tag.type, "false", "false", "false", tag.address, tag.comment])

# Add tags to replacement table
for tag in reversed(sorted(tags, key=lambda t: len(t.specialname) if t.specialname else 0)):
    if tag.specialname:
        replacementTable[tag.specialname] = Replacement(tag.specialname, tag.tagname)

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
            os.makedirs(os.path.join("output/blocks", os.path.relpath(root, "blocks")), exist_ok=True)
            createdBlocks.add(os.path.relpath(os.path.join(root, "blocks"), item))
            with open(os.path.join("output/blocks", os.path.relpath(root, "blocks"), item), "w", encoding="utf-8") as file:
                basename = os.path.splitext(os.path.basename(item))[0]
                file.write(content)
                

# Write patches CSV
with open("output/patches.csv", "w", encoding="utf-8", newline='') as file:
    writer = csv.writer(file)
    for key, value in replacementTable.items():
        if len(value.addresses) == 0:
            writer.writerow([key, value.name, "No patches"])
        else:
            writer.writerow([key, value.name])
            for address in value.addresses:
                writer.writerow(["", "", address])


try:
    portal = tia.attach_portal()
except Exception as e:
    # async open proccess (detached from this script)
    subprocess.Popen(
        ["C:/Program Files/siemens/automation/Portal V20/bin/Siemens.Automation.Portal.exe"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True
    )
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


def generate_tagtable_xml(tags):
    id = 1
    xml ="""<?xml version="1.0" encoding="utf-8"?>
                <Document>
                    <Engineering version="V20" />
                        <SW.Tags.PlcTagTable ID="0">
                            <AttributeList>
                                <Name>Default tag table</Name>
                            </AttributeList>
                            <ObjectList>"""
    for tag in tags:
        xml += f"""
            <SW.Tags.PlcTag ID="{(id:=id+1)}" CompositionName="Tags">
                <AttributeList>
                    <DataTypeName>{tag.type}</DataTypeName>
                    <ExternalAccessible>true</ExternalAccessible>
                    <ExternalVisible>true</ExternalVisible>
                    <ExternalWritable>true</ExternalWritable>
                    <LogicalAddress>{tag.address}</LogicalAddress>
                    <Name>{tag.tagname.strip('\"')}</Name>
                </AttributeList>
                <ObjectList>
                    <MultilingualText ID="{(id:=id+1)}" CompositionName="Comment">
                        <ObjectList>
                            <MultilingualTextItem ID="{(id:=id+1)}" CompositionName="Items">
                                <AttributeList>
                                  <Culture>en-US</Culture>
                                  <Text {tag.comment}/>
                                </AttributeList>
                            </MultilingualTextItem>
                        </ObjectList>
                    </MultilingualText>
                </ObjectList>
            </SW.Tags.PlcTag>
            """
    xml += """</ObjectList>
            </SW.Tags.PlcTagTable>
        </Document>
    """
    return xml

os.makedirs(os.path.join(os.getcwd(), "output", "tags"), exist_ok=True)
with open(os.path.join(os.getcwd(), "output", "tags", "tagtable.xml"), "w", encoding="utf-8") as file:
    file.write(generate_tagtable_xml(tags))
    

project = portal.get_project()
if project is not None:
    project.save()
    project.close()

import shutil
shutil.rmtree(os.path.join(os.getcwd(), "output", "project"), ignore_errors=True)
shutil.copytree(os.path.join(os.getcwd(), "template"), os.path.join(os.getcwd(), "output", "project"))
project = portal.open_project(os.path.join(os.getcwd(), "output", "project", "template.ap20"))

plcs = project.get_plcs()
plc = plcs[0]
plc.open_device_editor()
plc.import_blocks(os.path.join(os.getcwd(), "output", "blocks"))
plc.import_plc_tags(os.path.join(os.getcwd(), "output", "tags"))
project.save()