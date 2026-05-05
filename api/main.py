from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import zipfile
import tempfile
import xml.etree.ElementTree as ET

app = FastAPI()

# Allow CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def remove_sheet_protection(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        removed = False
        namespaces = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

        for elem in root.findall('.//ns:sheetProtection', namespaces) + root.findall('.//sheetProtection'):
            parent = root
            for p in root.iter():
                if elem in list(p):
                    parent = p
                    break
            parent.remove(elem)
            removed = True

        if removed:
            tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            return True
        return False
    except Exception:
        return False

@app.post("/api/unlock")
async def unlock_excel(file: UploadFile = File(...)):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    filename_no_ext = os.path.splitext(file.filename)[0]
    
    # Vercel serverless functions only have write access to /tmp
    work_dir = tempfile.mkdtemp(dir="/tmp")
    input_path = os.path.join(work_dir, file.filename)
    
    try:
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        zip_path = os.path.join(work_dir, filename_no_ext + ".zip")
        shutil.move(input_path, zip_path)

        # Extract
        extract_dir = os.path.join(work_dir, "extracted")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        worksheets_path = os.path.join(extract_dir, "xl", "worksheets")
        
        if os.path.exists(worksheets_path):
            xml_files = [f for f in os.listdir(worksheets_path) if f.endswith(".xml")]
            for xml_file in xml_files:
                file_path = os.path.join(worksheets_path, xml_file)
                remove_sheet_protection(file_path)

        # Repack
        output_zip = os.path.join(work_dir, "output.zip")
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root_dir, dirs, files in os.walk(extract_dir):
                for f in files:
                    full_path = os.path.join(root_dir, f)
                    rel_path = os.path.relpath(full_path, extract_dir)
                    zipf.write(full_path, rel_path)

        output_xlsx = os.path.join(work_dir, f"{filename_no_ext}_unlocked.xlsx")
        shutil.move(output_zip, output_xlsx)

        # Return the file as a downloadable response
        return FileResponse(
            path=output_xlsx, 
            filename=f"{filename_no_ext}_unlocked.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
