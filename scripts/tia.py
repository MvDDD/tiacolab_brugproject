import subprocess
import os
import siemens_tia_scripting as tia

portalversion = list(sorted([item.split()[1] for item in os.listdir("C:\\Program Files\\Siemens\\Automation") if item.startswith("Portal")], key=lambda s: int(s[1:])))[-1]












import sys;sys.exit(0)
import siemens_tia_scripting as tia
#tia.set_logging("./tia.log", False)
import os
tia.Enums.ExportFormats.ExternalSource
tia.Enums.ExportFormats.SimaticSD
tia.Enums.ExportFormats.SimaticML
tia.Enums.ExportOptions.WithReadOnly
tia.Enums.ExportOptions.WithDefaults
tia.Enums.HarmonizeOptions.HarmonizeNames
tia.Enums.HarmonizeOptions.HarmonizePaths
tia.Enums.HarmonizeOptions.HarmonizePathsAndNames
tia.Enums.LibraryExportOptions.OnlyLibraryVersionInfoFile
tia.Enums.LibraryExportOptions.WithLibraryVersionInfoFile
tia.Enums.LibraryExportOptions.Nan
tia.Enums.PortalMode.AnyUserInterface
tia.Enums.PortalMode.WithGraphicalUserInterface
tia.Enums.PortalMode.WithoutGraphicalUserInterface
tia.Enums.UmacUserMode.Global
tia.Enums.UmacUserMode.Project
tia.Enums.DependenciesMode.AutomaticallyCreateOrReleaseDependenciesIfRequired
tia.Enums.DependenciesMode.DoNotAutomaticallyCreateOrReleaseDependencies
tia.Enums.CleanUpMode.DeleteUnusedTypes
tia.Enums.CleanUpMode.PreserveDefaultVersionOfUnusedTypes


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
            time.sleep(10)
    # import time
    # time.sleep(30)
    # portal = tia.attach_portal()

# import shutil
# shutil.rmtree(os.path.join(os.getcwd(), "output", "project"), ignore_errors=True)
# shutil.copytree(os.path.join(os.getcwd(), "template"), os.path.join(os.getcwd(), "output", "project"))
project = portal.get_project()
# if project is not None:
    # project.save()
    # project.close()
# print("step 1 done")
# project = portal.open_project(os.path.join(os.getcwd(), "output", "project", "template.ap20"))
plcs = project.get_plcs()
plc = plcs[0]
plc.open_device_editor()
# system = plc.get_system_blocks()
plc.import_blocks(os.path.join(os.getcwd(), "output", "blocks"))
blocks = plc.get_program_blocks()


for block in blocks:
    if not block.is_consistent():
        block.compile()
for block in blocks:
    if block.get_property(name="ProgrammingLanguage") == "SCL":
        print(f"'{block.get_name()}', '{block.get_path_full()}', '{block.get_property(name='ProgrammingLanguage')}'")
        block.export(os.path.join(os.getcwd(), "blocks_source1"), tia.Enums.ExportOptions.WithDefaults, tia.Enums.ExportFormats.ExternalSource, True)
        print(block.get_property(name="SecondaryType"))