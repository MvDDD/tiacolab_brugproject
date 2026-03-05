import os
import sys

# Use TIA Scripting via file import (Only if TIA Scripting is not installed as package)
# need to set a global environment variable “TIA_SCRIPTING” with path containing TIA Scripting binaries
if os.getenv('TIA_SCRIPTING')  == None:
    # if TIA_SCRIPTING global environment variable is not set
    # set local variable with the path to TIA Scripting binaries
    tia_scripting_directory = "C:\\your\\path\\to\\tia-scripting-python"
    sys.path.append(tia_scripting_directory)
else:
    # TIA_SCRIPTING global environment variable is set and will be used for import
    sys.path.append(os.getenv('TIA_SCRIPTING'))

try:
    # import TIA Scripting binaries
    # if TIA Scripting is installed as package, global environment variable will be ignored
    import siemens_tia_scripting as ts
except ImportError:
    # you will run into ImportError also if you are using Python version which is not 3.12.X
    print("siemens_tia_scripting could not be found")
    sys.exit(0)

portal_mode_ui = True
keep_tia_portal = False
# example values for directories
project_file_path = "D:\\TiaScripting\\PLC_ExportAll\\PLC_ExportAll.ap20"
export_target_dir = "D:\\TiaScripting\\Export"
keep_folder_structure = True
# need to specify target version e.g. "17.0", requires that TIA portal V17 is installed
version = "20.0"
export_options = ts.Enums.ExportOptions.WithDefaults
export_format = ts.Enums.ExportFormats.SimaticML

if portal_mode_ui == True:
    portal = ts.open_portal(ts.Enums.PortalMode.WithGraphicalUserInterface, version = version)
    print("- open/attach tia portal with ui")
else:
    portal = ts.open_portal(ts.Enums.PortalMode.WithoutGraphicalUserInterface, version = version)
    print("- open/attach tia portal without ui")
    
project = portal.open_project(project_file_path = project_file_path, server_project_view = False)
print("- open project")
plcs = project.get_plcs()

if plcs:
    plc = plcs[0]
    tag_tables = plc.get_plc_tag_tables()
    for tag_table in tag_tables:
        # Export each tag table to the target directory in SimaticML format, with defaults, keeping folder structure
        tag_table.export(
            target_directory_path= export_target_dir + "\\PLC_TagTables",
            export_options=ts.Enums.ExportOptions.WithDefaults,
            export_format=ts.Enums.ExportFormats.SimaticML,
            keep_folder_structure=True
        )
    # Export all user data types of the first PLC
    udts = plc.get_user_data_types()
    for udt in udts:
        udt.export(
            target_directory_path= export_target_dir + "\\PLC_UDTs",
            export_format=ts.Enums.ExportFormats.SimaticSD,
            keep_folder_structure=True
        )
    # Export all Software Units of the first PLC
    for software_unit in plc.get_software_units():
        target_dir_su= export_target_dir + "\\SoftwareUnits\\" + software_unit.get_name()
        # Export software unit configuration        
        software_unit.export_configuration(export_file_path = target_dir_su + "ConfigSU.xml")

        # Export Program blocks
        for program_block in software_unit.get_program_blocks():
            if program_block.is_consistent() == False:
                program_block.compile()
            if program_block.is_consistent() == True:
                program_block.export(
                    target_directory_path = target_dir_su + "\\ProgramBlocks",
                    export_options = export_options,
                    keep_folder_structure = keep_folder_structure
                )
            if program_block.get_property(name="ProgrammingLanguage") == "SCL":
                program_block.export(
                    target_directory_path = target_dir_su + "\\ProgramBlocks",
                    export_options = export_options,
                    export_format = ts.Enums.ExportFormats.ExternalSource,
                    keep_folder_structure = keep_folder_structure
                )
       

if keep_tia_portal == "False":
    portal.close_portal()
    print("- close tia portal")

if keep_tia_portal == "True":
    print("- keep tia portal")

sys.exit(0)