from PIL import Image
import struct

def encode_text_to_image(image_path, data: bytes, output_path):
    # Prefix with 4-byte length header
    data_length = len(data)
    header = struct.pack('>I', data_length)  # 4 bytes, big-endian
    full_data = header + data
    binary_data = ''.join(format(byte, '08b') for byte in full_data)

    image = Image.open(image_path).convert('RGB')
    pixels = list(image.getdata())
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


def decode_text_from_image(image_path) -> bytes:
    image = Image.open(image_path).convert('RGB')
    binary_data = ''

    for pixel in image.getdata():
        for c in pixel[:3]:
            binary_data += format(c & 0b11, '02b')

    # Read 4 bytes = 32 bits = data length prefix
    header_bits = binary_data[:32]
    if len(header_bits) < 32:
        raise ValueError("Not enough data for length header.")

    data_len = struct.unpack('>I', int(header_bits, 2).to_bytes(4, 'big'))[0]
    total_bits_needed = (data_len + 4) * 8  # 4 bytes for header + data

    if len(binary_data) < total_bits_needed:
        raise ValueError("Encoded image is too small or corrupted.")

    useful_bits = binary_data[32:total_bits_needed]
    data_bytes = [useful_bits[i:i + 8] for i in range(0, len(useful_bits), 8)]
    return bytes(int(b, 2) for b in data_bytes)
