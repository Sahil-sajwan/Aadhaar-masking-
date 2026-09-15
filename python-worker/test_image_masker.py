import os
import unittest
from PIL import Image, ImageDraw, ImageFont
from utils.aadhaar_masker import AadhaarMasker, mask_aadhaar_string

class TestImageAadhaarMasker(unittest.TestCase):

    def test_sample_card_string_masking(self):
        sample_card_text = "Government of India\nNAME\n0000 1111 2222"
        masked = mask_aadhaar_string(sample_card_text)
        self.assertIn("XXXX XXXX 2222", masked)
        self.assertNotIn("0000 1111 2222", masked)

    def test_image_masking(self):
        test_dir = os.path.dirname(os.path.abspath(__file__))
        input_img_path = os.path.join(test_dir, 'sample_aadhaar_card.png')
        output_img_path = os.path.join(test_dir, 'masked_aadhaar_card.png')

        # Create a sample Aadhaar card image
        img = Image.new('RGB', (600, 350), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw header & mock details
        draw.text((150, 30), "Government of India", fill=(0, 0, 0))
        draw.text((150, 80), "NAME: John Doe", fill=(0, 0, 0))
        draw.text((150, 110), "DOB: 01/01/1990", fill=(0, 0, 0))
        
        # Draw Aadhaar Number: 0000 1111 2222
        draw.text((150, 200), "0000 1111 2222", fill=(0, 0, 0))
        
        img.save(input_img_path)

        # Process image with AadhaarMasker
        out_path = AadhaarMasker.mask_file(input_img_path, output_img_path)
        self.assertTrue(os.path.exists(out_path))

        # Cleanup
        if os.path.exists(input_img_path): os.remove(input_img_path)
        if os.path.exists(output_img_path): os.remove(output_img_path)

if __name__ == '__main__':
    unittest.main()
