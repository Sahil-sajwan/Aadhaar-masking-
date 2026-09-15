import os
import sys
import unittest
from utils.verhoeff import validate_verhoeff, generate_verhoeff
from utils.aadhaar_masker import AadhaarMasker, mask_aadhaar_string

class TestAadhaarMasker(unittest.TestCase):

    def test_verhoeff_validation(self):
        # Generate valid 12-digit Aadhaar number
        prefix = "99998888777"
        check_digit = generate_verhoeff(prefix)
        valid_aadhaar = f"{prefix}{check_digit}"
        self.assertTrue(validate_verhoeff(valid_aadhaar))

        # Invalid checksum
        invalid_aadhaar = f"{prefix}{(check_digit + 1) % 10}"
        self.assertFalse(validate_verhoeff(invalid_aadhaar))

    def test_string_masking(self):
        prefix = "99998888777"
        check_digit = generate_verhoeff(prefix)
        valid_aadhaar = f"9999 8888 777{check_digit}"
        sample_text = f"My Aadhaar card number is {valid_aadhaar}."
        masked = mask_aadhaar_string(sample_text)
        self.assertIn(f"XXXX XXXX 777{check_digit}", masked)

    def test_text_file_masking(self):
        test_dir = os.path.dirname(os.path.abspath(__file__))
        input_txt = os.path.join(test_dir, 'sample_input.txt')
        output_txt = os.path.join(test_dir, 'sample_output.txt')

        prefix = "99998888777"
        check_digit = generate_verhoeff(prefix)
        valid_aadhaar = f"9999 8888 777{check_digit}"

        with open(input_txt, 'w', encoding='utf-8') as f:
            f.write(f"Aadhaar Number: {valid_aadhaar}\nName: John Doe")

        out_path = AadhaarMasker.mask_file(input_txt, output_txt)
        self.assertTrue(os.path.exists(out_path))

        with open(output_txt, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn(f"XXXX XXXX 777{check_digit}", content)
            self.assertNotIn(valid_aadhaar, content)

        # Cleanup
        if os.path.exists(input_txt): os.remove(input_txt)
        if os.path.exists(output_txt): os.remove(output_txt)


if __name__ == '__main__':
    unittest.main()
