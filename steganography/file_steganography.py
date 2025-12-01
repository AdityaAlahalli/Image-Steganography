from PIL import Image
import struct
import numpy as np

def encode_file_to_image(image_path, file_bytes: bytes, output_path):
    # Prepend 4-byte length header
    header = struct.pack('>I', len(file_bytes))
    full_data = header + file_bytes
    binary_data = ''.join(format(byte, '08b') for byte in full_data)

    image = Image.open(image_path).convert('RGB')
    pixels = list(image.getdata())

    max_capacity = len(pixels) * 3 * 2  # 2 bits per channel
    if len(binary_data) > max_capacity:
        raise ValueError("File too large to encode in this image.")

    new_pixels = []
    data_index = 0
    for r, g, b in pixels:
        channels = [r, g, b]
        new_channels = []

        for c in channels:
            if data_index + 1 < len(binary_data):
                bits = binary_data[data_index:data_index + 2]
                new_c = (c & ~3) | int(bits, 2)
                data_index += 2
            elif data_index < len(binary_data):
                bit = binary_data[data_index]
                new_c = (c & ~3) | int(bit)
                data_index += 1
            else:
                new_c = c
            new_channels.append(new_c)

        new_pixels.append(tuple(new_channels))

    image.putdata(new_pixels)
    image.save(output_path, 'PNG')


def decode_file_from_image(image_path):
    img = Image.open(image_path).convert('RGB')
    raw = np.frombuffer(img.tobytes(), dtype=np.uint8)
    two_bits = raw & 0b11

    # Convert to binary string
    binary = ''.join(f"{b:02b}" for b in two_bits)

    if len(binary) < 32:
        raise ValueError("Not enough data for header")
    
    hbits = binary[:32]
    data_len = struct.unpack('>I', int(hbits, 2).to_bytes(4, 'big'))[0]
    total_bits = (data_len + 4) * 8

    if len(binary) < total_bits:
        raise ValueError(f"Incomplete data: expected {total_bits} bits, got {len(binary)} bits")

    data_bits = binary[32:total_bits]
    print(f"✅ Payload bytes length: {data_len} (expected {data_len})")

    return bytes(int(data_bits[i:i + 8], 2) for i in range(0, len(data_bits), 8))