from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import os
import zipfile
import time
import traceback
from steganography import text_steganography, file_steganography, encryption
from steganography.compression_utils import zip_text, zip_file, unzip_bytes
from steganography.multi_image_steganography import encode_chunks_to_images, decode_chunks_from_images, calculate_capacity
from flask import jsonify


app = Flask(__name__)
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/encode', methods=['POST'])
def encode():
    image = request.files['image']
    text_data = request.form.get('text_data')
    file_data = request.files.get('file_data')
    password = request.form.get('password')
    custom_filename = request.form.get('custom_filename')

    if image.filename == '':
        return render_template('index.html', error='No image selected.')

    image_filename = secure_filename(image.filename)
    raw_image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
    image.save(raw_image_path)

    img = Image.open(raw_image_path).convert('RGB')
    png_image_filename = os.path.splitext(image_filename)[0] + '_converted.png'
    png_image_path = os.path.join(app.config['UPLOAD_FOLDER'], png_image_filename)
    img.save(png_image_path, 'PNG')
    os.remove(raw_image_path)

    encoded_filename = secure_filename(custom_filename) + '.png' if custom_filename else 'encoded_image.png'
    encoded_image_path = os.path.join(app.config['UPLOAD_FOLDER'], encoded_filename)

    try:
        if file_data and file_data.filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file_data.filename))
            file_data.save(file_path)
            zipped = zip_file(file_path)
            os.remove(file_path)

            original_filename = secure_filename(file_data.filename)
            filename_header = original_filename.encode() + b'::FN::'
            combined = filename_header + zipped
            encrypted = encryption.encrypt_data(combined, password)    
            file_steganography.encode_file_to_image(png_image_path, encrypted, encoded_image_path)

        elif text_data:
            zipped = zip_text(text_data)
            encrypted = encryption.encrypt_data(zipped, password)
            text_steganography.encode_text_to_image(png_image_path, encrypted, encoded_image_path)

        else:
            return render_template('index.html', error='Please provide text or file to encode.')

    except Exception as e:
        return render_template('index.html', error=f'Encoding failed: {str(e)}')

    return render_template('index.html', encoded_image=encoded_filename, original_image=os.path.basename(png_image_path))


@app.route('/decode', methods=['POST'])
def decode():
    encoded_image = request.files['encoded_image']
    password = request.form.get('password')

    if encoded_image.filename == '':
        return render_template('index.html', error='No image selected.')

    filename = secure_filename(encoded_image.filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    encoded_image.save(image_path)

    # --- 🧠 Try TEXT decoding ---
    try:
        encrypted_data = text_steganography.decode_text_from_image(image_path)
        print("✅ Encrypted data extracted from text:", len(encrypted_data))
        decrypted = encryption.decrypt_data(encrypted_data, password)
        print("✅ Decryption succeeded")

        try:
            # Try to unzip (if zipped text)
            files = unzip_bytes(decrypted)
            print("📦 Archive contents:", list(files.keys()))
            text_file = next(iter(files.values()))
            return render_template('index.html', decoded_text=text_file.decode())
        except Exception as unzip_err:
            print("⚠️ Unzip failed, trying raw text:", unzip_err)
            # Fallback to raw text
            return render_template('index.html', decoded_text=decrypted.decode())
    except Exception as e:
        print("Text decode failed:", e)

    # --- 🧠 Try FILE decoding ---
    try:
        encrypted_data = file_steganography.decode_file_from_image(image_path)
        decrypted = encryption.decrypt_data(encrypted_data, password)

        split_marker = b'::FN::'
        if split_marker not in decrypted:
            raise ValueError("This image does not contain a file.")

        filename_bytes, zipped_file_bytes = decrypted.split(split_marker, 1)
        files = unzip_bytes(zipped_file_bytes, extract_to=app.config['UPLOAD_FOLDER'])

        filename = filename_bytes.decode()
        saved_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))

        return render_template('index.html', decoded_file=secure_filename(filename))

    except Exception as e:
        print("File decode failed:", e)
        return render_template('index.html', error="Decoding failed. Ensure correct password and stego image.")




@app.route('/advanced/encode', methods=['POST'])
def advanced_encode():
    action = request.form.get('action')
    images = request.files.getlist('images')
    password = request.form.get('password')
    file = request.files.get('file_data')
    text_data = request.form.get('text_data')

    if file and file.filename:
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_path)
        zipped = zip_file(temp_path)
        os.remove(temp_path)
        filename_header = secure_filename(file.filename).encode() + b'::FN::'
        combined = filename_header + zipped
    elif text_data:
        combined = zip_text(text_data)
    else:
        return render_template('index.html', error="Provide text or file to encode.")

    encrypted = encryption.encrypt_data(combined, password)
    required_bits = len(encrypted) * 8

    image_paths = []
    capacities = []
    for img in images:
        if img.filename:
            path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(img.filename))
            img.save(path)
            image_paths.append(path)
            capacities.append(calculate_capacity(path) * 8)

    total_capacity_bits = sum(capacities)

    if action == "check":
        if total_capacity_bits >= required_bits:
            msg = f"✅ Capacity OK. Required: {required_bits} bits. Available: {total_capacity_bits} bits."
        else:
            extra = required_bits - total_capacity_bits
            avg_image_bits = total_capacity_bits / len(image_paths) if image_paths else 0
            more = int((extra / avg_image_bits) + 1) if avg_image_bits else "N/A"
            msg = f"❌ Not enough capacity. Required: {required_bits} bits. Available: {total_capacity_bits} bits. Add {more} more image(s)."
        return render_template('index.html', capacity_result=msg)

    try:
        print("encrypted payload size:",len(encrypted))
        encoded_paths = encode_chunks_to_images(image_paths, encrypted, app.config['UPLOAD_FOLDER'])
        zip_output = os.path.join(app.config['UPLOAD_FOLDER'], 'multi_encoded.zip')
        with zipfile.ZipFile(zip_output, 'w') as zipf:
            for path in encoded_paths:
                zipf.write(path, arcname=os.path.basename(path))
        return send_file(zip_output, as_attachment=True)
    except Exception as e:
        return render_template('index.html', error=f"Multi-image encoding failed: {str(e)}")


@app.route('/advanced/decode', methods=['POST'])
def advanced_decode():
    stego_images = request.files.getlist('stego_images')
    print("Raw stego_images list length:", len(stego_images))
    for f in stego_images:
        print("Received file object:", f.filename)
    password = request.form.get('password')
    
    image_paths = []

    if not stego_images:
        return render_template('index.html', error="Upload the stego images to decode.")

    

    image_paths = []
    for img in stego_images:
        if img.filename:
            path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(img.filename))
            img.save(path)
            image_paths.append(path)
            
    print("files uploaded:")
    for path in image_paths:
        print("  - ",os.path.basename(path))

    try:
        start = time.time()
        try:
            merged_encrypted_data = decode_chunks_from_images(image_paths)
            print("✅ Decoding complete. Bytes merged:", len(merged_encrypted_data))
        except Exception as e:
            import traceback
            traceback.print_exc()
            return render_template('index.html',error=f"Multi-image decoding failed: {str(e)}")
        print(f"chunk decode took {time.time() - start:.2f}s")
        print("✅ Decoding complete. Bytes merged:", len(merged_encrypted_data))
        print("📦 First 64 bytes:", merged_encrypted_data[:64])
        print("📦 Last 64 bytes:", merged_encrypted_data[-64:])
        start = time.time()
        decrypted = encryption.decrypt_data(merged_encrypted_data, password)
        print(f"decryption took {time.time() - start:.2f}s")
        print("✅ Decryption successful. Size:", len(decrypted))

        try:
            start = time.time()
            files = unzip_bytes(decrypted, extract_to=app.config['UPLOAD_FOLDER'])
            print(f"unzipping took {time.time() - start:.2f}s")
            start = time.time()
            for name, content in files.items():
                try:
                    decoded = content.decode('utf-8')
                    return render_template('index.html',decoded_text=decoded)
                except UnicodeDecodeError:
                    path = os.path.join(app.config['UPLOAD_FOLDER'],secure_filename(name))
                    with open(path, 'wb') as f:
                        f.write(content)
                    return render_template('index.html', decoded_file=secure_filename(name))
            print(f"file save took {time.time() - start:.2f}s")
            return render_template('index.html', error="no readable content found") 
              

        except Exception as e:
            import traceback
            traceback.print_exc()
            return render_template('index.html', error="Multi-image decoding failed: " + str(e))

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("📦 Decoding failed after merging chunks.")
        print("🧩 Encrypted data length (bytes):", len(merged_encrypted_data))
        print("🔐 Password used:", password)
        return render_template('index.html', error=f"Multi-image decoding failed: {str(e)}")



@app.route('/check_capacity', methods=['POST'])
def check_capacity():
    images = request.files.getlist('images')
    password = request.form.get('password', 'default')
    file = request.files.get('file_data')
    text_data = request.form.get('text_data')

    if file and file.filename:
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_path)
        zipped = zip_file(temp_path)
        os.remove(temp_path)
        combined = secure_filename(file.filename).encode() + b'::FN::' + zipped
    elif text_data:
        combined = zip_text(text_data)
    else:
        return render_template('index.html', capacity_result="❌ No data provided")

    encrypted = encryption.encrypt_data(combined, password)
    required_bits = len(encrypted) * 8

    image_paths = []
    total_capacity = 0
    for img in images:
        if img.filename:
            path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(img.filename))
            img.save(path)
            cap = calculate_capacity(path) * 8
            total_capacity += cap
            image_paths.append(path)

    if total_capacity >= required_bits:
        msg = f"✅ Capacity OK. Required: {required_bits} bits. Available: {total_capacity} bits."
    else:
        extra = required_bits - total_capacity
        avg_image_bits = total_capacity / len(image_paths) if image_paths else 0
        more = int((extra / avg_image_bits) + 1) if avg_image_bits else "N/A"
        msg = f"❌ Not enough capacity. Required: {required_bits} bits. Available: {total_capacity} bits. Add at least {more} more image(s)."

    return render_template('index.html', capacity_result=msg, advanced_text = text_data, advanced_password = password)


if __name__ == '__main__':
    app.run(debug=True)
