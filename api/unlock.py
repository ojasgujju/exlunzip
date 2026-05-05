import zipfile
import io
import os
import xml.etree.ElementTree as ET

def remove_sheet_protection(xml_bytes):
    tree = ET.ElementTree(ET.fromstring(xml_bytes))
    root = tree.getroot()

    namespaces = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

    removed = False

    for elem in root.findall('.//ns:sheetProtection', namespaces) + root.findall('.//sheetProtection'):
        parent = root
        for p in root.iter():
            if elem in list(p):
                parent = p
                break
        parent.remove(elem)
        removed = True

    if removed:
        output = io.BytesIO()
        tree.write(output, encoding='utf-8', xml_declaration=True)
        return output.getvalue()

    return xml_bytes


def handler(request):
    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": "Method Not Allowed"
        }

    try:
        file = request.files.get("file")
        if not file:
            return {"statusCode": 400, "body": "No file uploaded"}

        filename = file.filename
        name_no_ext = filename.replace(".xlsx", "")

        input_bytes = file.read()

        zip_in = zipfile.ZipFile(io.BytesIO(input_bytes))
        output_buffer = io.BytesIO()

        with zipfile.ZipFile(output_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for item in zip_in.infolist():
                data = zip_in.read(item.filename)

                if item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                    data = remove_sheet_protection(data)

                zip_out.writestr(item, data)

        output_buffer.seek(0)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Content-Disposition": f'attachment; filename="{name_no_ext}_unlocked.xlsx"'
            },
            "body": output_buffer.read(),
            "isBase64Encoded": True
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": str(e)
        }
