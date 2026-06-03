import os
import sys
import csv
import shutil
import subprocess
import siemens_tia_scripting as tia
import time
from tqdm import tqdm

sys.argv[1:] = ["rik", "d"]

blocks_input_dir="blocks"
blocks_output_dir="output/blocks"





# tqdm wrapper for auto depth
tqdm2_depth = 0

def tqdm2(iterable, **kwargs):
	global tqdm2_depth

	tqdm2_depth += 1
	try:
		if "position" not in kwargs:
			kwargs["position"] = tqdm2_depth
		if "leave" not in kwargs:
			kwargs["leave"] = False
		return tqdm(iterable, **kwargs)
	finally:
		tqdm2_depth -= 1

def count_lines(file):
	pos = file.tell()
	file.seek(0, os.SEEK_END)
	size = file.tell() - pos
	pbar = tqdm2([], total=size, unit="B", unit_scale=True, unit_divisor=1024)
	numlines = 0
	for chunk in iter(lambda: bytes(file.read(1024 * 1024), "utf-8"), b""):
		pbar.update(len(chunk))
		numlines += chunk.count(b"\n")
	file.seek(pos)
	return numlines
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
		numlines = count_lines(file)
		reader = tqdm2(csv.reader(file), total=numlines, unit="lines")
		zip([0,0],reader)
		for parts in reader:
			items = [part.strip() for part in parts]
			tag = Tag.fromParts(items)
			if tag:
				result.append(tag)
	return result

def load_replacements(constants_dir="constants"):
	table = {}
	numfiles = 0
	for root, dirs, files in os.walk(constants_dir):
		numfiles += len([file for file in files if file.endswith(".csv")])
	for root, dirs, files in tqdm2(os.walk(constants_dir), total=numfiles, unit="files"):
		for file in files:
			if not file.endswith(".csv"): continue
			path = os.path.join(root, file)
			with open(path, "r", encoding="utf-8", newline='') as f:
				numlines = count_lines(f)
				reader = tqdm2(csv.reader(f), total=numlines, unit="lines")
				zip([0,0],reader)
				for parts in reader:
					if not parts: continue
					replacement_text = parts[1] if sys.argv[1]=="rik" else parts[2]
					table[parts[0]] = Replacement(parts[0], replacement_text)
	return table

def load_tags(tags_dir="tags"):
	tags = []
	length = 0
	for root, dirs, files in os.walk(tags_dir):
		for filename in files:
			length += len([file for file in files if file.endswith(".csv")])
	for root, dirs, files in os.walk(tags_dir):
		for filename in files:
			if filename.endswith(".csv"):
				tags.extend(parse_csv(os.path.join(root, filename)))
	return tags

# -----------------------------
# Generate TIA Function Blocks
# -----------------------------


def generate_tia_function_blocks(replacementTable):


	def handle_header(file_iter, outfile, name):
		header_lines = []
		for i, line in file_iter:
			if line.strip():
				stripped = line.strip()
				if stripped.lower().startswith("return"):
					header_lines.append(line)
					break
				elif stripped:
					header_lines.append(line)
		else: # no break
			# end is not found:
			raise Exception(f"return line not found in {name}")
		
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
		
		outfile.write(f'FUNCTION "{file_name}" : {file_returns}\n')
		outfile.write("{ S7_Optimized_Access := 'TRUE' }\n")
		outfile.write("VERSION : 0.1\n")

		if len(vars["input"]):
			outfile.write("VAR_INPUT\n")
			for line in vars["input"]:
				outfile.write(f"    {line}\n")
			outfile.write("END_VAR\n")

		if len(vars["output"]):
			outfile.write("VAR_OUTPUT\n")
			for line in vars["output"]:
				outfile.write(f"    {line}\n")
			outfile.write("END_VAR\n")

		if len(vars["inout"]):
			outfile.write("VAR_INOUT\n")
			for line in vars["inout"]:
				outfile.write(f"    {line}\n")
			outfile.write("END_VAR\n")

		if len(vars["temp"]):
			outfile.write("VAR_TEMP\n")
			for line in vars["temp"]:
				outfile.write(f"    {line}\n")
			outfile.write("END_VAR\n")

		outfile.write("BEGIN\n")

	def handle_body(file_iter, outfile):
		for i, line in file_iter:
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
							f"{rep.replacement} -> {rep.name} at {root}/{item} line {i} col {idx+1}"
						)
						idx += len(rep.name)

			# Comment original line if anything changed
			if modified_line != original_line:
				final_line = f"// {original_line}\n{modified_line}" # + "\n"
			else:
				final_line = modified_line

			outfile.write(final_line)
		

	if replacementTable is None:
		replacementTable = {}

	num_files = 0
	num_lines = 0
	for root, dirs, files in os.walk(blocks_input_dir):
		num_files += len([file for file in files if file.endswith(".SCL")])

	def all_files(inf):
		for root, dirs, files in inf:
			for file in files:
				if not file.endswith(".SCL"): continue
				yield root,file

	for root, item in tqdm2(all_files(os.walk(blocks_input_dir)), total=num_files, unit="files"):
		localreplacementTable = {k: v for k, v in replacementTable.items()}
		localreplacementTable["%%FILE%%"] = Replacement("%%FILE%%", os.path.splitext(item)[0])
		localreplacementTable["%RETURN"] = Replacement("%RETURN", "#\""+ os.path.splitext(item)[0] + "\" :=")
		file_name = os.path.splitext(item)[0]
		file_path = os.path.join(root, item)

		with open(file_path, "rb") as f:
			for chunk in iter(lambda: f.read(1024 * 1024), b""):
				num = chunk.count(b"\n")
				num_lines += num
				if len(chunk) != 1024 * 1024:
					if chunk[-1] != ord("\n"):
						num_lines += 1

		with open(file_path, "r", encoding="utf-8-sig") as source_file:

		# Prepare output
			rel_dir = os.path.relpath(root, blocks_input_dir)
			out_dir = os.path.join(blocks_output_dir, rel_dir)
			os.makedirs(out_dir, exist_ok=True)
			vars = {
				"input":[],
				"output":[],
				"inout": [],
				"temp":[]
			}

			out_path = list(os.path.splitext(os.path.join(out_dir, item)))
			out_path[1] = out_path[1].lower()
			out_path = out_path[0] + out_path[1]

			file_iterator = enumerate(tqdm2(source_file, total=num_lines, unit="lines"))
			with open(out_path, "w", encoding="utf-8") as f:
				try:
					handle_header(file_iterator, f, file_path)
					handle_body(file_iterator, f)
					f.write("\nEND_FUNCTION\n")
				except Exception as e:
					print(f"Error processing {file_path}: {e}")
					raise

# -----------------------------
# Generate TIA Data Blocks
# -----------------------------
def generate_tia_data_blocks():
	input_dir="blocks"
	output_dir="output/blocks"

	for root, dirs, files in os.walk(input_dir):
		for item in files:
			fullpath = os.path.join(root, item)
			if not item.endswith(".DB"): continue
			name = item.split(".")[0]
			with open(fullpath, "r", encoding="utf-8", newline='') as f:
				iterator = tqdm2(enumerate(f), total=count_lines(f), unit="lines")
				result = []
				for i, line in iterator:
					if not line.strip(): continue
					name, type = line.split(";")[0].split(":")[:2]
					modifiers = line.split(";")[0].split(":")[2:]
					if len(modifiers):
						modifiers = modifiers[0].split()
					else:
						modifiers = []
					comment = line.split(";")[1]
					if " " in type.strip():
						result.append({"name": name, "type":type, "modifiers":modifiers, "comment":comment.strip()})


					out_path = list(os.path.splitext(os.path.join(blocks_output_dir, item)))
					out_path[1] = out_path[1].lower()
					out_path = out_path[0] + out_path[1]
					with open(out_path, "w", encoding="utf-8") as f:
						f.write(f"DATA_BLOCK : {name}\n")
						f.write("{ S7_Optimized_Access := 'TRUE' }")
						f.write("VERSION : 0.1\n")
						f.write("NON_RETAIN")
						is_retain = False
						f.write("\tVAR")
						for [name, type, modifiers, comment] in result:
							if ("RETAIN" in modifiers) != is_retain:
								f.write("\tEND_VAR\n")
								f.write("\tVAR")
								if "RETAIN" in modifiers:
									f.write(" RETAIN")
								f.write("\n")
								is_retain = "RETAIN" in modifiers
							f.write("\t\t{name} {{ExternalAccessible := '{accessible}'; ExternalVisible := '{visible}'; ExternalWritable := '{writable}'}} : {type}; {comment}\n".format(
								name=name,
								type=type,
								accessible="TRUE" if "ACCESSIBLE" in modifiers else "FALSE",
								visible="TRUE" if "VISIBLE" in modifiers else "FALSE",
								writable="TRUE" if "WRITABLE" in modifiers else "FALSE",
								comment=comment
							))
						f.write("\tEND_VAR")
						f.write("BEGIN\n")
						f.write("\nEND_DATA_BLOCK\n")




# -----------------------------
# Generate Tag Table XML
# -----------------------------
def generate_tagtable_xml(tags, file):
	id = 1
	file.write(
		
		'<?xml version="1.0" encoding="utf-8"?>\n'
		'    <Document>\n'
		'        <Engineering version="V20" />\n'
		'            <SW.Tags.PlcTagTable ID="0">\n'
		'                <AttributeList>\n'
		'                    <Name>Default tag table</Name>\n'
		'                </AttributeList>\n'
		'                <ObjectList>\n'
	)
	for tag in tqdm2(tags, total=len(tags), unit="tags", desc="writing tags"):
		file.write(
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
	file.write (
		'            </ObjectList>\n'
		'        </SW.Tags.PlcTagTable>\n'
		'    </Document>\n'
		'</xml>\n'
	)

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
		for tag in tqdm2(tags, unit="tags", desc="writing tags"):
			writer.writerow([tag.tagname.strip('"'), "Default Tagtable", tag.type, "false", "false", "false", tag.address, tag.comment])

	# Add tags to replacement table

	for tag in tqdm2(list(reversed(sorted(tags, key=lambda t: len(t.specialname) if t.specialname else 0))), unit="tags", desc="building table"):
		if tag.specialname:
			replacementTable[tag.specialname] = Replacement(tag.specialname, tag.tagname)


	shutil.rmtree(blocks_output_dir, ignore_errors=True)
	os.makedirs(blocks_output_dir)
	# Generate blocks
	generate_tia_function_blocks(replacementTable)
	generate_tia_data_blocks()
	# Write patches CSV
	with open("output/patches.csv", "w", encoding="utf-8", newline='') as f:
		writer = csv.writer(f)
		for key, value in tqdm2(replacementTable.items(), total=len(replacementTable), unit="patches", desc="writing patches"):
			if len(value.addresses) == 0:
				writer.writerow([key, value.name, "No patches"])
			else:
				writer.writerow([key, value.name])
				for address in value.addresses:
					writer.writerow(["", "", address])

	# Generate tagtable XML
	os.makedirs("output/tags", exist_ok=True)
	with open(os.path.join("output", "tags", "tagtable.xml"), "w", encoding="utf-8") as f:
		generate_tagtable_xml(tags, f)

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


	plc.import_blocks(
		import_root_directory = os.path.join(os.getcwd(), "output/blocks"),
		target_folder_path = ""
	)
	root_target = os.path.abspath("output/blocks")
	p=[]
	for root, dirs, files in os.walk(root_target):
		for dir in dirs:
			base = os.path.join(root, dir)
			trg = os.path.relpath(base, root_target)
			p.append(plc.import_blocks(base, trg))
	print(p)

	project.save()
	sys.exit(0)

# -----------------------------
# Entry Point
# -----------------------------
if __name__ == "__main__":
	main()