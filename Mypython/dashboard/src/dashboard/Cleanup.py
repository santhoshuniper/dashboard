import os
import glob

# ---------------- CONFIG ----------------
ROOT = r"C:\Dashboard"
SYSTEM_FOLDERS = ["VAT-P","USIP1","Neon","USIP2","Endur"]

def cleanup():
    for system in SYSTEM_FOLDERS:
        system_path = os.path.join(ROOT, system)

        # Skip if folder does not exist
        if not os.path.exists(system_path):
            continue

        # Get all files in main folder
        for file in glob.glob(os.path.join(system_path, "*.*")):
            if os.path.isfile(file):
                os.remove(file)

        # Check subfolders like success and failure
        for sub in ["success","failure"]:
            sub_path = os.path.join(system_path, sub)
            if os.path.exists(sub_path):
                for file in glob.glob(os.path.join(sub_path,"*.*")):
                    if os.path.isfile(file):
                        os.remove(file)

    print("Cleanup complete! All files in VAT-P, USIP1, Neon, USIP2, Endur deleted.")

if __name__=="__main__":
    cleanup()