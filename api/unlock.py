import os
import zipfile
import tempfile
import shutil
import xml.etree.ElementTree as ET

def remove_sheet_protection(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    namespaces = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

    removed = False

    for elem in root.findall('.//ns:sheetProtection', namespaces) + root.findall('.//sheetProtection'):
        for parent in root.iter():
            if elem in list(parent):
                parent.remove(elem)
                removed = True
                break

    if removed:
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    return removed


def handler(request):
    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": "Method Not Allowed"
        }

    file = request.files.get("file")

    if not file:
        return {
            "statusCode": 400,
            "body": "No file uploaded"
        }

    filename = file.filename
    name = filename.replace(".xlsx", "")

    with tempfile.TemporaryDirectory() as work_dir:
        zip_path = os.path.join(work_dir, "file.zip")

        with open(zip_path, "wb") as f:
            f.write(file.read())

        extract_dir = os.path.join(work_dir, "extracted")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        worksheets = os.path.join(extract_dir, "xl", "worksheets")

        if os.path.exists(worksheets):
            for fxml in os.listdir(worksheets):
                if fxml.endswith(".xml"):
                    remove_sheet_protection(os.path.join(worksheets, fxml))

        output_zip = os.path.join(work_dir, "out.zip")

        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(extract_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, extract_dir)
                    zipf.write(full, rel)

        output_xlsx = os.path.join(work_dir, f"{name}_unlocked.xlsx")
        shutil.move(output_zip, output_xlsx)

        with open(output_xlsx, "rb") as f:
            data = f.read()

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Content-Disposition": f'attachment; filename="{name}_unlocked.xlsx"'
        },
        "body": data,
        "isBase64Encoded": True
    }
