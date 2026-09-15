import os
import unittest
from utils.verhoeff import generate_verhoeff
from utils.aadhaar_masker import AadhaarMasker, mask_aadhaar_string, is_aadhaar_number

class TestMultiNumberAadhaarMasker(unittest.TestCase):

    def test_aadhaar_identification(self):
        # 1. Genuine Aadhaar number (Verhoeff checksum valid)
        prefix = "99998888777"
        check_digit = generate_verhoeff(prefix)
        valid_aadhaar = f"{prefix}{check_digit}"
        self.assertTrue(is_aadhaar_number(valid_aadhaar))

        # 2. Sample Aadhaar template number
        mock_aadhaar = "000011112222"
        self.assertTrue(is_aadhaar_number(mock_aadhaar))

        # 3. Non-Aadhaar 12-digit number without Verhoeff checksum or context
        random_account_num = "123456789012"
        self.assertFalse(is_aadhaar_number(random_account_num))

        # 4. Phone number (10 digits)
        phone_num = "9876543210"
        self.assertFalse(is_aadhaar_number(phone_num))

        # 5. PIN code (6 digits)
        pincode = "110001"
        self.assertFalse(is_aadhaar_number(pincode))

    def test_text_with_multiple_numbers(self):
        prefix = "99998888777"
        check_digit = generate_verhoeff(prefix)
        valid_aadhaar = f"9999 8888 777{check_digit}"

        doc_text = f"""
        Document Summary:
        Name: Jane Smith
        Mobile Number: 9876543210
        Pin Code: 110001
        Account No: 123456789012
        Aadhaar Number: {valid_aadhaar}
        """

        masked_result = mask_aadhaar_string(doc_text)

        # Aadhaar number should be masked (first 8 digits)
        self.assertIn(f"XXXX XXXX 777{check_digit}", masked_result)
        self.assertNotIn(valid_aadhaar, masked_result)

        # Phone number, PIN code, and Account number MUST remain untouched
        self.assertIn("9876543210", masked_result)
        self.assertIn("110001", masked_result)
        self.assertIn("123456789012", masked_result)

if __name__ == '__main__':
    unittest.main()
