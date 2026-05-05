import zipfile
import io
import base64
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)

        # Simple multipart parsing (Vercel doesn't give Flask-style request)
        boundary = self.headers['Content-Type'].split("boundary=")[-1].encode()
        parts = body.split(b"--" + boundary)

        file_content = None
        filename = "output.xlsx"

        for part in parts:
            if b"filename=" in part:
                header, file_data = part.split(b"\r\n\r\n", 1)
                file_content = file_data.rstrip(b"\r\n--")
                
                for line in header.split(b"\r\n"):
                    if b"filename=" in line:
                        filename = line.split(b'filename="')[1].split(b'"')[0].decode()

        if not file_content:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No file uploaded")
            return

        def remove_protection(xml_bytes):
            tree = ET.ElementTree(ET.fromstring(xml_bytes))
            root = tree.getroot()

            ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

            for elem in root.findall('.//ns:sheetProtection', ns) + root.findall('.//sheetProtection'):
                for parent in root.iter():
                    if elem in list(parent):
                        parent.remove(elem)
                        break

            output = io.BytesIO()
            tree.write(output, encoding='utf-8', xml_declaration=True)
            return output.getvalue()

        zip_in = zipfile.ZipFile(io.BytesIO(file_content))
        output_buffer = io.BytesIO()

        with zipfile.ZipFile(output_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for item in zip_in.infolist():
                data = zip_in.read(item.filename)

                if item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                    data = remove_protection(data)

                zip_out.writestr(item, data)

        output_buffer.seek(0)

        out_name = filename.replace(".xlsx", "_unlocked.xlsx")

        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", f'attachment; filename="{out_name}"')
        self.end_headers()
        self.wfile.write(output_buffer.read())
