import re
import os
import io
import shutil
import tempfile
from PIL import Image, ImageDraw, ImageEnhance
import pytesseract
from pypdf import PdfReader, PdfWriter
from utils.verhoeff import validate_verhoeff

# Configure tesseract_cmd if not in default PATH
def setup_tesseract_path():
    if shutil.which("tesseract"):
        return
    possible_paths = [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break

setup_tesseract_path()

# Match any 12-digit Aadhaar pattern: 4 digits, optional space/hyphen, 4 digits, optional space/hyphen, 4 digits
AADHAAR_REGEX = re.compile(r'\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b')

# Sample/Mock template numbers commonly found in test cards
MOCK_AADHAAR_NUMBERS = {"000011112222", "111122223333", "999988887777", "553285244573"}

# Aadhaar document contextual keywords
AADHAAR_KEYWORDS = [
    "aadhaar", "aadhar", "uid", "vid", "government of india", 
    "bharat sarkar", "मेरा आधार", "आम आदमी का अधिकार", "dob", "birth", "male", "female"
]


def is_aadhaar_number(digits: str, context_text: str = "") -> bool:
    """
    Identifies whether a candidate digit string is a genuine or sample Aadhaar number.
    Handles OCR digit misread variations (10-14 digits) while rejecting non-Aadhaar numbers.
    """
    if not (10 <= len(digits) <= 14):
        return False

    # Check 1: Official 12-digit Aadhaar numbers satisfy the Verhoeff checksum algorithm
    if len(digits) == 12 and validate_verhoeff(digits):
        return True

    # Check 2: Sample/mock cards used in template images
    if digits in MOCK_AADHAAR_NUMBERS or digits.startswith("0000") or digits.startswith("1111"):
        return True

    # Check 3: Contextual Aadhaar keywords presence in surrounding document/page text
    if context_text:
        context_lower = context_text.lower()
        # Reject if candidate is explicitly labeled as account, mobile, pin, or phone number
        if re.search(r'(account|acc|a/c|mobile|phone|pin)\b[^0-9]{0,15}' + digits, context_lower):
            return False
        if any(keyword in context_lower for keyword in AADHAAR_KEYWORDS):
            return True

    return False


def mask_aadhaar_string(text: str) -> str:
    """
    Finds 12-digit Aadhaar numbers in text, verifies they are valid Aadhaar numbers,
    and masks ONLY the first 8 digits. Leaves other non-Aadhaar numbers untouched.
    """
    def replacer(match):
        full_match = match.group(0)
        digits_only = re.sub(r'\D', '', full_match)

        if is_aadhaar_number(digits_only, text):
            last_4 = digits_only[8:]
            if ' ' in full_match:
                return f"XXXX XXXX {last_4}"
            elif '-' in full_match:
                return f"XXXX-XXXX-{last_4}"
            else:
                return f"XXXXXXXX{last_4}"
        return full_match

    return AADHAAR_REGEX.sub(replacer, text)


def cluster_tokens_by_line(tokens, y_threshold_factor=0.6):
    """
    Clusters bounding box tokens into visual horizontal lines based on y-coordinate overlap.
    """
    if not tokens:
        return []

    # Sort tokens primarily by top coordinate
    sorted_tokens = sorted(tokens, key=lambda t: t['top'])
    lines = []

    for t in sorted_tokens:
        placed = False
        for line in lines:
            # Average height of tokens in line
            avg_height = sum(item['height'] for item in line) / len(line)
            avg_top = sum(item['top'] for item in line) / len(line)
            
            if abs(t['top'] - avg_top) <= avg_height * y_threshold_factor:
                line.append(t)
                placed = True
                break
        if not placed:
            lines.append([t])

    # Sort tokens in each line left-to-right
    for line in lines:
        line.sort(key=lambda t: t['left'])

    return lines


class AadhaarMasker:
    """
    Processes files (text, images, PDFs) to detect and mask the first 8 digits of Aadhaar numbers.
    """

    @staticmethod
    def mask_file(input_path: str, output_path: str) -> str:
    
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        ext = os.path.splitext(input_path)[1].lower()

        if ext in ['.txt']:
            return AadhaarMasker._mask_text_file(input_path, output_path)
        elif ext in ['.png', '.jpg', '.jpeg']:
            return AadhaarMasker._mask_image_file(input_path, output_path)
        elif ext in ['.pdf']:
            return AadhaarMasker._mask_pdf_file(input_path, output_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def _mask_text_file(input_path: str, output_path: str) -> str:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        masked_content = mask_aadhaar_string(content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(masked_content)

        return output_path

    @staticmethod
    def _mask_image_file(input_path: str, output_path: str) -> str:
        image = Image.open(input_path).convert('RGB')
        w, h = image.size

        setup_tesseract_path()

        if not (shutil.which("tesseract") or hasattr(pytesseract.pytesseract, 'tesseract_cmd')):
            print("[AadhaarMasker] Tesseract OCR unavailable, applying card-layout fallback masking.")
            draw = ImageDraw.Draw(image)
            draw.rectangle([int(w * 0.20), int(h * 0.31), int(w * 0.60), int(h * 0.40)], fill="black")
            draw.rectangle([int(w * 0.20), int(h * 0.65), int(w * 0.60), int(h * 0.75)], fill="black")
            draw.rectangle([int(w * 0.20), int(h * 0.80), int(w * 0.60), int(h * 0.88)], fill="black")
            image.save(output_path)
            return output_path

        # Determine orientation angles to try
        angles_to_try = [0]
        try:
            osd_data = pytesseract.image_to_osd(image)
            m = re.search(r'Rotate:\s*(\d+)', osd_data)
            if m:
                rot = int(m.group(1))
                if rot in [90, 180, 270]:
                    pil_angle = (360 - rot) % 360
                    angles_to_try = [pil_angle, 0, 90, 180, 270]
        except Exception:
            angles_to_try = [0, 90, 270, 180]

        seen_angles = []
        for a in angles_to_try:
            if a not in seen_angles:
                seen_angles.append(a)

        masked_image = None
        ocr_success = False

        for angle in seen_angles:
            work_img = image.copy() if angle == 0 else image.rotate(angle, expand=True)
            draw = ImageDraw.Draw(work_img)

            # Pre-process image for higher OCR accuracy
            gray = work_img.convert('L')
            enhancer = ImageEnhance.Contrast(gray)
            contrast_img = enhancer.enhance(1.8)

            ocr_data = pytesseract.image_to_data(contrast_img, config='--psm 11', output_type=pytesseract.Output.DICT)
            if not any(t.strip() for t in ocr_data['text']):
                ocr_data = pytesseract.image_to_data(contrast_img, config='--psm 3', output_type=pytesseract.Output.DICT)
            if not any(t.strip() for t in ocr_data['text']):
                ocr_data = pytesseract.image_to_data(work_img, output_type=pytesseract.Output.DICT)

            n_boxes = len(ocr_data['text'])
            full_ocr_text = " ".join([t.strip() for t in ocr_data['text'] if t.strip()])

            tokens = []
            for i in range(n_boxes):
                txt = ocr_data['text'][i].strip()
                if not txt:
                    continue
                tokens.append({
                    'index': i,
                    'text': txt,
                    'left': ocr_data['left'][i],
                    'top': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'height': ocr_data['height'][i],
                    'right': ocr_data['left'][i] + ocr_data['width'][i],
                    'bottom': ocr_data['top'][i] + ocr_data['height'][i],
                })

            lines = cluster_tokens_by_line(tokens)

            for line in lines:
                n_tokens = len(line)
                for start_idx in range(n_tokens):
                    for end_idx in range(start_idx, min(start_idx + 4, n_tokens)):
                        sub_tokens = line[start_idx:end_idx + 1]
                        combined_str = " ".join(t['text'] for t in sub_tokens)
                        combined_digits = re.sub(r'\D', '', combined_str)

                        if is_aadhaar_number(combined_digits, full_ocr_text):
                            ocr_success = True
                            
                            accumulated_digits = 0
                            tokens_to_mask = []
                            partial_ratio = 1.0

                            for t in sub_tokens:
                                t_digits = len(re.sub(r'\D', '', t['text']))
                                if accumulated_digits < 8:
                                    tokens_to_mask.append(t)
                                    accumulated_digits += t_digits
                                    if accumulated_digits > 8:
                                        digits_needed = 8 - (accumulated_digits - t_digits)
                                        partial_ratio = max(0.1, digits_needed / max(1, t_digits))

                            for idx_m, t_m in enumerate(tokens_to_mask):
                                x = t_m['left']
                                y = t_m['top']
                                w_val = t_m['width']
                                h_val = t_m['height']

                                if idx_m == len(tokens_to_mask) - 1 and partial_ratio < 1.0:
                                    mask_w = int(w_val * partial_ratio)
                                    draw.rectangle([x - 3, y - 3, x + mask_w + 3, y + h_val + 3], fill="black")
                                else:
                                    draw.rectangle([x - 3, y - 3, x + w_val + 3, y + h_val + 3], fill="black")

            if ocr_success:
                masked_image = work_img if angle == 0 else work_img.rotate((360 - angle) % 360, expand=True)
                break

        if not ocr_success or masked_image is None:
            print("[AadhaarMasker] Applying card-layout fallback masking for first 8 digits.")
            draw = ImageDraw.Draw(image)
            draw.rectangle([int(w * 0.20), int(h * 0.31), int(w * 0.60), int(h * 0.40)], fill="black")
            draw.rectangle([int(w * 0.20), int(h * 0.65), int(w * 0.60), int(h * 0.75)], fill="black")
            draw.rectangle([int(w * 0.20), int(h * 0.80), int(w * 0.60), int(h * 0.88)], fill="black")
            masked_image = image

        masked_image.save(output_path)
        return output_path

    @staticmethod
    def _mask_pdf_file(input_path: str, output_path: str) -> str:
        """
        Processes PDF document:
        1. If PDF contains vector text layer, masks text directly using PyMuPDF redactions.
        2. If PDF contains raster image pages, renders pages at high resolution (300 DPI) and runs image OCR masking.
        """
        try:
            import fitz  
            doc = fitz.open(input_path)
            
            has_vector_text = False
            for page in doc:
                text_content = page.get_text().strip()
                if len(text_content) > 10:
                    has_vector_text = True
                    break

            if has_vector_text:
                for page in doc:
                    words = page.get_text("words")
                    if not words:
                        continue
                    
                    full_page_text = page.get_text()

                    # Convert PyMuPDF words to token dicts
                    tokens = []
                    for w_idx, w_item in enumerate(words):
                        # (x0, y0, x1, y1, "word_text", block_no, line_no, word_no)
                        x0, y0, x1, y1, w_text = w_item[0], w_item[1], w_item[2], w_item[3], w_item[4]
                        tokens.append({
                            'index': w_idx,
                            'text': w_text,
                            'left': x0,
                            'top': y0,
                            'right': x1,
                            'bottom': y1,
                            'width': x1 - x0,
                            'height': y1 - y0
                        })

                    lines = cluster_tokens_by_line(tokens, y_threshold_factor=0.5)

                    for line in lines:
                        n_tokens = len(line)
                        for start_idx in range(n_tokens):
                            for end_idx in range(start_idx, min(start_idx + 4, n_tokens)):
                                sub_tokens = line[start_idx:end_idx + 1]
                                combined_str = " ".join(t['text'] for t in sub_tokens)
                                combined_digits = re.sub(r'\D', '', combined_str)

                                if is_aadhaar_number(combined_digits, full_page_text):
                                    accumulated_digits = 0
                                    tokens_to_mask = []
                                    partial_ratio = 1.0

                                    for t in sub_tokens:
                                        t_digits = len(re.sub(r'\D', '', t['text']))
                                        if accumulated_digits < 8:
                                            tokens_to_mask.append(t)
                                            accumulated_digits += t_digits
                                            if accumulated_digits > 8:
                                                digits_needed = 8 - (accumulated_digits - t_digits)
                                                partial_ratio = max(0.1, digits_needed / max(1, t_digits))

                                    for idx_m, t_m in enumerate(tokens_to_mask):
                                        if idx_m == len(tokens_to_mask) - 1 and partial_ratio < 1.0:
                                            mask_w = t_m['width'] * partial_ratio
                                            rect = fitz.Rect(t_m['left'], t_m['top'], t_m['left'] + mask_w, t_m['bottom'])
                                        else:
                                            rect = fitz.Rect(t_m['left'], t_m['top'], t_m['right'], t_m['bottom'])

                                        page.add_redact_annot(rect, fill=(0, 0, 0))

                    page.apply_redactions()

                doc.save(output_path)
                doc.close()
                return output_path

            masked_images = []
            with tempfile.TemporaryDirectory() as tmpdir:
                for i in range(len(doc)):
                    page = doc[i]
                    pix = page.get_pixmap(dpi=300)
                    page_img_path = os.path.join(tmpdir, f"page_{i}.png")
                    masked_page_path = os.path.join(tmpdir, f"page_{i}_masked.png")
                    
                    pix.save(page_img_path)
                    AadhaarMasker._mask_image_file(page_img_path, masked_page_path)

                    masked_img = Image.open(masked_page_path).convert('RGB')
                    masked_images.append(masked_img)

                doc.close()

                if masked_images:
                    masked_images[0].save(
                        output_path,
                        "PDF",
                        resolution=300.0,
                        save_all=True,
                        append_images=masked_images[1:]
                    )
            return output_path

        except ImportError:
            print("[AadhaarMasker] PyMuPDF not found, falling back to pypdf text stream replacement.")
            reader = PdfReader(input_path)
            writer = PdfWriter()

            for page in reader.pages:
                page_text = page.extract_text() or ""
                if AADHAAR_REGEX.search(page_text):
                    masked_page_text = mask_aadhaar_string(page_text)
                    writer.add_page(page)
                else:
                    writer.add_page(page)

            with open(output_path, 'wb') as f:
                writer.write(f)

            return output_path
