import siemens_tia_scripting as tia
import os
tia.Enums.ExportFormats.ExternalSource
tia.Enums.ExportFormats.SimaticSD
tia.Enums.ExportFormats.SimaticML
tia.Enums.ExportOptions.WithReadOnly
tia.Enums.ExportOptions.WithDefaults
portal = tia.attach_portal()
print(dir(portal))
project = portal.get_project()
print(dir(project))
plcs = project.get_plcs()
print(dir(plcs))
plc = plcs[0]
print(plc.get_name())
blocks = plc.get_program_blocks()
block = blocks[0]

for block in blocks:
    if block.get_property(name="ProgrammingLanguage") == "SCL":
        print(block.get_name())
        print(block.get_supported_export_format())
        print(block.export(os.path.join(os.getcwd(), "blosks_source"), tia.Enums.ExportOptions.WithDefaults, tia.Enums.ExportFormats.ExternalSource, True)) 