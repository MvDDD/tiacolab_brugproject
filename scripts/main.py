import os
import sys
import csv
import shutil
import subprocess
import siemens_tia_scripting as tia
import time

# -----------------------------
# Logging
# -----------------------------
def init_logging(log_path="./tia.log"):
    open(log_path, "w").close() # clear logfile
    tia.set_logging(log_path, False)

# -----------------------------
# Replacement / Tag Classes
# -----------------------------
class Replacement:
    def __init__(self, name, replacement):
        self.name = name
        self.replacement = replacement
        self.addresses = []

class Tag:
    alltags = []

    def __init__(self, parts):
        self.specialname = parts[0] or None
        self.tagname = parts[1]
        self.type = parts[2]
        self.address = parts[3]
        self.comment = parts[4] or ""
        self.byteSize = Tag.getByteSize(self.type)
        Tag.alltags.append(self)

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
        except IndexError:
            print(f"malformed tag: {parts}")
        return None

    @staticmethod
    def getByteSize(type):
        match type:
            case "Bool": return 1/8
            case "Char" | "Byte": return 1
            case "Word" | "Int": return 2
            case "DWord" | "UDInt" | "Real": return 4
            case "LReal": return 8
            case "USInt": return 1
            case "Time": return 4
            case "Date": return 2
            case "TOD": return 4
            case "DTL": return 12
            case "String": return 254

# -----------------------------
# CSV Parsing
# -----------------------------
def parse_csv(path):
    result = []
    with open(path, "r", encoding="utf-8", newline='') as file:
        reader = csv.reader(file)
        next(reader, None)
        next(reader, None)
        for parts in reader:
            items = [part.strip() for part in parts]
            tag = Tag.fromParts(items)
            if tag:
                result.append(tag)
    return result

def load_replacements(constants_dir="constants"):
    table = {}
    for root, dirs, files in os.walk(constants_dir):
        for file in files:
            if not file.endswith(".csv"): continue
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8", newline='') as f:
                reader = csv.reader(f)
                next(reader, None)
                next(reader, None)
                for parts in reader:
                    if not parts: continue
                    print(path, parts)
                    replacement_text = parts[1] if sys.argv[1]=="rik" else parts[2]
                    table[parts[0]] = Replacement(parts[0], replacement_text)
    return table

def load_tags(tags_dir="tags"):
    tags = []
    for root, dirs, files in os.walk(tags_dir):
        for filename in files:
            if filename.endswith(".csv"):
                tags.extend(parse_csv(os.path.join(root, filename)))
    return tags

# -----------------------------
# Generate TIA Function Blocks
# -----------------------------
def generate_tia_function_blocks(replacementTable):
    input_dir="blocks"
    output_dir="output/blocks"

    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir)

    if replacementTable is None:
        replacementTable = {}
    createdBlocks = set()
    for root, dirs, files in os.walk(input_dir):
        for item in files:
            localreplacementTable = {k: v for k, v in replacementTable.items()}
            localreplacementTable["%%FILE%%"] = Replacement("%%FILE%%", os.path.splitext(item)[0])
            localreplacementTable["%RETURN"] = Replacement("%RETURN", "#\""+ os.path.splitext(item)[0] + "\" :=")
            file_name = os.path.splitext(item)[0]
            file_path = os.path.join(root, item)
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()

            # Split header/body
            header_lines = []
            return_found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.lower().startswith("return "):
                    header_lines.append(line)
                    return_index = i
                    return_found = True
                    break
                elif stripped != "":
                    header_lines.append(line)
            if not return_found:
                raise ValueError(f"No RETURN line found in {item}")
            body_lines = lines[return_index + 1:]

            # Apply replacements safely
            # Apply replacements safely (works for %RETURN and all tokens)
            for i, line in enumerate(body_lines):
                original_line = line
                modified_line = line

                # Replace all tokens in the local replacement table
                for rep in localreplacementTable.values():
                    if not rep.name:
                        continue
                    if rep.name in modified_line:
                        # Replace all occurrences
                        modified_line = modified_line.replace(rep.name, rep.replacement)

                        # Track all occurrences for logging
                        idx = 0
                        while True:
                            idx = line.find(rep.name, idx)
                            if idx == -1:
                                break
                            rep.addresses.append(
                                f"{rep.replacement} -> {rep.name} at {root}/{item} line {i + return_index + 2} col {idx+1}"
                            )
                            idx += len(rep.name)

                # Comment original line if anything changed
                if modified_line != original_line:
                    body_lines[i] = f"// {original_line}\n{modified_line}"

            # Prepare output
            rel_dir = os.path.relpath(root, input_dir)
            out_dir = os.path.join(output_dir, rel_dir)
            os.makedirs(out_dir, exist_ok=True)
            createdBlocks.add(os.path.join(rel_dir, item))

            vars = {
                "input":[],
                "output":[],
                "inout": [],
                "temp":[]
            }
            var_lines = header_lines[:-1]
            for line in var_lines:
                name, type = line.split(";")[0].split(":")
                comment = line.split(";")[1]
                if " " in type.strip():
                    specifier, type = type.strip().split()
                    vars[specifier].append(f"{name} : {type};{" "+comment.strip() if comment.strip() else ""}")
            return_parts = header_lines[-1].strip().rstrip(";").split()
            file_returns = return_parts[1]

            out_path = list(os.path.splitext(os.path.join(out_dir, item)))
            out_path[1] = out_path[1].lower()
            out_path = out_path[0] + out_path[1]

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f'FUNCTION "{file_name}" : {file_returns}\n')
                # f.write("{ S7_Optimized_Access := 'TRUE' }\n")
                f.write("VERSION : 0.1\n")

                if len(vars["input"]):
                    f.write("VAR_INPUT\n")
                    for line in vars["input"]:
                        f.write(f"    {line}\n")
                    f.write("END_VAR\n")

                if len(vars["output"]):
                    f.write("VAR_OUTPUT\n")
                    for line in vars["output"]:
                        f.write(f"    {line}\n")
                    f.write("END_VAR\n")

                if len(vars["inout"]):
                    f.write("VAR_INOUT\n")
                    for line in vars["inout"]:
                        f.write(f"    {line}\n")
                    f.write("END_VAR\n")

                if len(vars["temp"]):
                    f.write("VAR_TEMP\n")
                    for line in vars["temp"]:
                        f.write(f"    {line}\n")
                    f.write("END_VAR\n")

                f.write("BEGIN\n")
                f.write("\n".join(body_lines).replace('"""', '"'))
                f.write("\nEND_FUNCTION\n")
    return createdBlocks

# -----------------------------
# Generate Tag Table XML
# -----------------------------
def generate_tagtable_xml(tags):
    id = 1
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '    <Document>\n'
        '        <Engineering version="V20" />\n'
        '            <SW.Tags.PlcTagTable ID="0">\n'
        '                <AttributeList>\n'
        '                    <Name>Default tag table</Name>\n'
        '                </AttributeList>\n'
        '                <ObjectList>\n'
    )
    for tag in tags:
        xml += (
            f'                <SW.Tags.PlcTag ID="{(id:=id+1)}" CompositionName="Tags">\n'
            f'                    <AttributeList>\n'
            f'                        <DataTypeName>{tag.type}</DataTypeName>\n'
            f'                        <ExternalAccessible>true</ExternalAccessible>\n'
            f'                        <ExternalVisible>true</ExternalVisible>\n'
            f'                        <ExternalWritable>true</ExternalWritable>\n'
            f'                        <LogicalAddress>{tag.address}</LogicalAddress>\n'
            f'                        <Name>{tag.tagname.strip('"')}</Name>\n'
            f'                    </AttributeList>\n'
            f'                    <ObjectList>\n'
            f'                        <MultilingualText ID="{(id:=id+1)}" CompositionName="Comment">\n'
            f'                            <ObjectList>\n'
            f'                                <MultilingualTextItem ID="{(id:=id+1)}" CompositionName="Items">\n'
            f'                                    <AttributeList>\n'
            f'                                      <Culture>en-US</Culture>\n'
            f'                                      <Text>{tag.comment}</Text>\n'
            f'                                    </AttributeList>\n'
            f'                                </MultilingualTextItem>\n'
            f'                            </ObjectList>\n'
            f'                        </MultilingualText>\n'
            f'                    </ObjectList>\n'
            f'                </SW.Tags.PlcTag>\n'
        )
    xml += (
        '            </ObjectList>\n'
        '        </SW.Tags.PlcTagTable>\n'
        '    </Document>\n'
        '</xml>\n'
    )
    return xml

# -----------------------------
# Main Workflow
# -----------------------------
def main():
    init_logging()
    replacementTable = load_replacements()
    tags = load_tags()

    # Write tags CSV
    os.makedirs("output", exist_ok=True)
    with open("output/tags.csv", "w", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        for tag in tags:
            writer.writerow([tag.tagname.strip('"'), "Default Tagtable", tag.type, "false", "false", "false", tag.address, tag.comment])

    # Add tags to replacement table
    for tag in reversed(sorted(tags, key=lambda t: len(t.specialname) if t.specialname else 0)):
        if tag.specialname:
            replacementTable[tag.specialname] = Replacement(tag.specialname, tag.tagname)

    # Generate blocks
    generate_tia_function_blocks(replacementTable)

    # Write patches CSV
    with open("output/patches.csv", "w", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        for key, value in replacementTable.items():
            if len(value.addresses) == 0:
                writer.writerow([key, value.name, "No patches"])
            else:
                writer.writerow([key, value.name])
                for address in value.addresses:
                    writer.writerow(["", "", address])

    # Generate tagtable XML
    os.makedirs("output/tags", exist_ok=True)
    with open(os.path.join("output", "tags", "tagtable.xml"), "w", encoding="utf-8") as f:
        f.write(generate_tagtable_xml(tags))

    if "d" in sys.argv:
        print("Skipping TIA Portal")
        return
    # Attach TIA Portal
    try:
        portal = tia.attach_portal()
    except Exception:
        subprocess.Popen(
            ["C:/Program Files/siemens/automation/Portal V20/bin/Siemens.Automation.Portal.exe"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True
        )
        portal = None
        while portal is None:
            try:
                print("Trying to connect to TIA Portal...")
                portal = tia.attach_portal()
            except Exception:
                time.sleep(5)

    # Get and close project if open
    project = portal.get_project()
    if project:
        project.save()
        project.close()

    # Copy project template
    # This must happen after closing the project because tiaportal locks the projectfiles
    shutil.rmtree("output/project", ignore_errors=True)
    shutil.copytree("template", "output/project", dirs_exist_ok=True)
    print("Copied project template")
    project = portal.open_project(os.path.join(os.getcwd(), "output/project/template.ap20"))
    print("opened project")
    plcs = project.get_plcs()
    plc = plcs[0]
    plc.open_device_editor()
    plc.import_plc_tags(os.path.join(os.getcwd(), "output/tags"))
    plc.import_blocks(os.path.join(os.getcwd(), "output/blocks"))
    project.save()
    sys.exit(0)

# -----------------------------
# Entry Point
# -----------------------------
if __name__ == "__main__":
    main()