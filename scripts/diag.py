import clr
import sys

CONTRACT_API_DLL = r"C:\Program Files\Siemens\Automation\Portal V20\Bin\PublicAPI\Siemens.Engineering.Contract.dll"
HMI_API_DLL = r"C:\Program Files\Siemens\Automation\Portal V20\PublicAPI\V20\Siemens.Engineering.Hmi.dll"
TIA_API_DLL = r"C:\Program Files\Siemens\Automation\Portal V20\PublicAPI\V20\Siemens.Engineering.dll"

clr.AddReference(CONTRACT_API_DLL)
clr.AddReference(HMI_API_DLL)
clr.AddReference(TIA_API_DLL)

from Siemens.Engineering import TiaPortal
from Siemens.Engineering.CrossReference import CrossReferenceService

def main():
    processes = TiaPortal.GetProcesses()
    if processes.Count == 0: return
    portal = processes[0].Attach()
    project = portal.Projects[0]
    
    # Check if we can get anything from CrossReferenceService
    crs = project.GetService[CrossReferenceService]()
    if crs:
        print("!!! Found CrossReferenceService on Project")
        # I'll just see what it has
        print(dir(crs))

if __name__ == "__main__":
    main()
