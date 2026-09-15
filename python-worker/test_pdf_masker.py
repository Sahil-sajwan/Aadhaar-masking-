import os
import unittest
from PIL import Image, ImageDraw
from utils.aadhaar_masker import AadhaarMasker

class TestPdfAadhaarMasker(unittest.TestCase):

    def test_pdf_masking(self):
        test_dir = os.path.dirname(os.path.abspath(__file__))
        input_pdf_path = os.path.join(test_dir, 'sample_aadhaar.pdf')
        output_pdf_path = os.path.join(test_dir, 'masked_aadhaar.pdf')

        # Create a 2-page sample PDF containing Aadhaar numbers
        img1 = Image.new('RGB', (600, 800), color=(255, 255, 255))
        d1 = ImageDraw.Draw(img1)
        d1.text((100, 100), "Name: Adarsh Kumar", fill=(0, 0, 0))
        d1.text((100, 300), "5532 8524 4573", fill=(0, 0, 0))

        img2 = Image.new('RGB', (600, 800), color=(255, 255, 255))
        d2 = ImageDraw.Draw(img2)
        d2.text((100, 200), "0000 1111 2222", fill=(0, 0, 0))
        d2.text((100, 500), "0000 1111 2222", fill=(0, 0, 0))

        img1.save(input_pdf_path, "PDF", save_all=True, append_images=[img2])

        # Run AadhaarMasker.mask_file on PDF
        out_path = AadhaarMasker.mask_file(input_pdf_path, output_pdf_path)

        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 0)

        # Cleanup
        if os.path.exists(input_pdf_path): os.remove(input_pdf_path)
        if os.path.exists(output_pdf_path): os.remove(output_pdf_path)

if __name__ == '__main__':
    unittest.main()
