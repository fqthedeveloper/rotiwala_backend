# Test script - create a test_pdf.py file
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)
pdf.cell(200, 10, txt="Test PDF", ln=True, align='C')
pdf.cell(200, 10, txt="Hello World", ln=True, align='C')
pdf.output("test.pdf")

print("PDF created successfully!")