import struct
from PIL import Image
import os
import numpy as np

BITS_PER_CHANNEL = 2

def calculate_capacity(image_path):
    img = Image.open(image_path)
    w, h = img.size
    return (w * h * 3 * BITS_PER_CHANNEL) // 8

def encode_chunks_to_images(image_paths, data: bytes, output_dir):
    header = struct.pack('>I', len(data))
    full_data = header + data
    binary = ''.join(format(b, '08b') for b in full_data)
    bit_list = list(binary)
    total_bits = len(bit_list)

    results = []
    index = 0

    for i, img_path in enumerate(image_paths):
        img = Image.open(img_path).convert('RGB')
        pixels = list(img.getdata())
        capacity_bits = len(pixels) * 3 * BITS_PER_CHANNEL

        bits_this = min(total_bits - index, capacity_bits)
        if bits_this <= 0:
            print(f"⚠️ Skipping {img_path} (eempty chunk)")
            continue

        new_pixels = []
        di = 0  # bit index within this chunk

        for r, g, b in pixels:
            new_channels = []
            for c in (r, g, b):
                if di + 1 < bits_this:
                    b1 = bit_list[index + di]
                    b2 = bit_list[index + di + 1]
                    new_c = (c & ~0b11) | int(b1 + b2, 2)
                    di += 2
                elif di < bits_this:
                    b1 = bit_list[index + di]
                    new_c = (c & ~0b11) | int(b1 + '0', 2)  # pad last bit with 0
                    di += 1
                else:
                    new_c = c
                new_channels.append(new_c)
            new_pixels.append(tuple(new_channels))

        index += bits_this
        out_path = os.path.join(output_dir, f'chunk_{i+1}.png')
        img.putdata(new_pixels)
        img.save(out_path, 'PNG')
        results.append(out_path)
        print(f"✅ Saved: {out_path}, bits encoded: {bits_this}")

        if index >= total_bits:
            print("✅ All data successfully encoded.")
            break

    if index < total_bits:
        raise ValueError(f"❌ Not enough image capacity: needed {total_bits} bits, only encoded {index}")

    return results


def decode_chunks_from_images(image_paths):
    bit_arrays = []

    for path in image_paths:
        img = Image.open(path).convert('RGB')
        raw = np.frombuffer(img.tobytes(), dtype=np.uint8)
        two_bits = raw & 0b11  # Array of 2-bit values (0–3)
        bit_arrays.append(two_bits)
        print(f"Decoded chunk {os.path.basename(path)}: {len(two_bits)*BITS_PER_CHANNEL} bits")

    all_bits = np.concatenate(bit_arrays)
    # Convert to a string of bits
    binary = ''.join(f"{b:02b}" for b in all_bits)

    # Extract header
    if len(binary) < 32:
        raise ValueError("Not enough data for header")
    hbits = binary[:32]
    data_len = struct.unpack('>I', int(hbits, 2).to_bytes(4, 'big'))[0]
    total_bits = (data_len + 4) * 8

    if len(binary) < total_bits:
        raise ValueError(f"Incomplete data: expected {total_bits}, got {len(binary)} bits")

    data_bits = binary[32:total_bits]
    print(f"Total payload: {data_len} bytes -> {total_bits} bits")

    # Convert bitstring to bytes
    return bytes(int(data_bits[i:i+8], 2) for i in range(0, len(data_bits), 8))