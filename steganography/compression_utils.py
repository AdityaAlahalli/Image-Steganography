
import os
import zipfile
import io

def zip_file(file_path: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zipf:
        arcname = os.path.basename(file_path)
        zipf.write(file_path, arcname)
    return buffer.getvalue()



def zip_text(text: str, filename: str = "text.txt") -> bytes:
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, text)
    memory_file.seek(0)  # ✅ CRITICAL
    return memory_file.getvalue()


def unzip_bytes(zip_bytes: bytes, extract_to: str = None) -> dict:
    result = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
        print("Archive contents:",zf.namelist())
        if extract_to:
            zf.extractall(extract_to)
            for name in zf.namelist():
                with open(os.path.join(extract_to, name), 'rb') as f:
                    result[name] = f.read()
        else:
            for name in zf.namelist():
                result[name] = zf.read(name)
    return result
