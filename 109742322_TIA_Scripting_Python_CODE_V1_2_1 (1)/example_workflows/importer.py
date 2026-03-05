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
project_file_path = "D:\\TiaScripting\\PLC_ImportAll\\PLC_ImportAll.ap17"
import_root_dir = "D:\\TiaScripting\\Export"
version = "17.0"

if portal_mode_ui == True:
    portal = ts.open_portal(ts.Enums.PortalMode.WithGraphicalUserInterface, version = version)
    print("- open/attach tia portal with ui")
else:
    portal = ts.open_portal(ts.Enums.PortalMode.WithoutGraphicalUserInterface, version = version)
    print("- open/attach tia portal without ui")
    
project = portal.open_project(project_file_path = project_file_path)
print("- open project")

plcs = project.get_plcs()
for plc in plcs:
    plc.import_data_types(import_root_directory= import_root_dir + "\\PlcDataTypes")
    plc.import_technology_objects(import_root_directory= import_root_dir + "\\TechnologyObjects")
    plc.import_blocks(import_root_directory= import_root_dir + "\\ProgramBlocks")
    plc.import_plc_tags(import_root_directory= import_root_dir + "\\PlcTags")
    plc.import_watch_tables(import_root_directory= import_root_dir + "\\WatchAndForceTables")


if keep_tia_portal == "False":
    portal.close_portal()
    print("- close tia portal")

if keep_tia_portal == "True":
    print("- keep tia portal")

sys.exit(0)