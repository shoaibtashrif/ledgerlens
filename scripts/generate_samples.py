"""Generate 10 representative test cases (PDFs and receipt images).
Covers:
1. Clean digital SaaS invoice (AWS)
2. Professional services invoice (Upwork agency)
3. Travel & flight receipt (Emirates)
4. Restaurant meal receipt (Image / JPG)
5. Utility / Telecom bill (PTCL / Internet)
6. Edge case: Subtotal + Tax arithmetic MISMATCH (Calculated bug)
7. Edge case: Missing invoice number & foreign currency (AED)
8. Edge case: Duplicate invoice (same vendor + invoice number as case 1)
9. Edge case: Handwritten/Noisy store receipt (Image / PNG)
10. Failure case: Non-invoice document (Confidentiality agreement / NDA)
"""
from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
SAMPLES.mkdir(exist_ok=True)

def make_pdf(filename: str, title: str, lines: list[str]):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4
    text = f"{title.upper()}\n" + "=" * 40 + "\n\n" + "\n".join(lines)
    page.insert_text((50, 70), text, fontsize=12, fontname="helv")
    path = SAMPLES / filename
    doc.save(path)
    doc.close()
    print(f"Created {filename}")

def make_receipt_img(filename: str, title: str, lines: list[str]):
    img = Image.new("RGB", (600, 800), color=(250, 248, 245))
    draw = ImageDraw.Draw(img)
    y = 50
    draw.text((180, y), f"*** {title} ***", fill=(30, 30, 30))
    y += 40
    draw.line([(40, y), (560, y)], fill=(120, 120, 120), width=2)
    y += 30
    for line in lines:
        draw.text((50, y), line, fill=(40, 40, 40))
        y += 28
    draw.line([(40, y + 20), (560, y + 20)], fill=(120, 120, 120), width=2)
    path = SAMPLES / filename
    img.save(path)
    print(f"Created {filename}")

def generate_all():
    # 1. AWS Cloud Services (Clean SaaS)
    make_pdf("01_clean_aws_cloud_invoice.pdf", "Amazon Web Services Inc. - Tax Invoice", [
        "Vendor: Amazon Web Services, Inc.",
        "Invoice Number: INV-AWS-2026-9812",
        "Invoice Date: 2026-03-15",
        "Due Date: 2026-04-15",
        "Currency: USD",
        "",
        "Line Items:",
        "1. Amazon Elastic Compute Cloud (EC2) - Linux instance: $120.00",
        "2. Amazon Simple Storage Service (S3) - Standard Storage: $25.50",
        "3. AWS Data Transfer Out - Global: $14.50",
        "",
        "Subtotal: $160.00",
        "Tax / VAT (0%): $0.00",
        "Total Amount Due: $160.00",
        "",
        "Payment Terms: Net 30 days. Automated bank debit."
    ])

    # 2. Upwork Freelance Agency (Professional Services)
    make_pdf("02_freelance_dev_consulting.pdf", "Wosler Tech Solutions - Professional Invoice", [
        "Vendor: Wosler Tech Solutions Ltd.",
        "Client: Apex Digital Media",
        "Invoice Number: WOS-2026-044",
        "Invoice Date: 2026-03-20",
        "Due Date: 2026-04-05",
        "Currency: USD",
        "",
        "Line Items:",
        "1. Full-stack Agentic AI Automation sprint (40 hrs @ $50/hr): $2000.00",
        "2. Cloud Infrastructure Architecture setup: $500.00",
        "",
        "Subtotal: $2500.00",
        "Sales Tax (5%): $125.00",
        "Total Amount: $2625.00",
        "",
        "Thank you for your business. Wire transfer details enclosed."
    ])

    # 3. Airline Travel Receipt (Travel & Lodging)
    make_pdf("03_emirates_flight_receipt.pdf", "Emirates Airlines - Electronic Ticket Receipt", [
        "Vendor: Emirates Airline",
        "Booking Reference: EK-9824XJ",
        "Invoice Number: TKT-176-902341",
        "Date of Issue: 2026-02-10",
        "Currency: USD",
        "",
        "Passenger: Shoaib Rao",
        "Flight: DXB to LHR (Business Class)",
        "",
        "Base Fare: $1850.00",
        "Taxes & Airport Surcharges: $210.00",
        "Total Fare Paid: $2060.00",
        "",
        "Payment Method: VISA ending in 4119"
    ])

    # 4. Restaurant Meal (Image JPG)
    make_receipt_img("04_restaurant_bistro_receipt.jpg", "THE ARTISAN BISTRO & GRILL", [
        "Merchant: The Artisan Bistro",
        "Receipt #: REC-88712",
        "Date: 2026-03-18",
        "Table: 14 | Server: Marcus",
        "",
        "1x Ribeye Steak 12oz ......... $ 48.00",
        "2x Sparkling Mineral Water ... $ 12.00",
        "1x Artisan Tiramisu .......... $ 14.00",
        "",
        "Subtotal: $ 74.00",
        "City Tax (8.25%): $ 6.10",
        "Tip / Gratuity: $ 15.00",
        "Total Paid: $ 95.10",
        "",
        "Payment: Apple Pay (Mastercard)"
    ])

    # 5. Telecom / Internet Bill
    make_pdf("05_telecom_internet_bill.pdf", "PTCL Broadband & Fiber - Monthly Statement", [
        "Vendor: PTCL Telecommunications Ltd",
        "Customer Account: ACC-9081234",
        "Invoice Number: BILL-2026-03-771",
        "Issue Date: 2026-03-01",
        "Due Date: 2026-03-22",
        "Currency: PKR",
        "",
        "Package: 100 Mbps Flash Fiber Corporate Link",
        "Monthly Service Charges: Rs 8,500.00",
        "Static IP Add-on: Rs 1,000.00",
        "",
        "Subtotal: Rs 9,500.00",
        "Provincial GST (19.5%): Rs 1,852.50",
        "Total Amount Payable: Rs 11,352.50"
    ])

    # 6. EDGE CASE: Math Mismatch (Subtotal + Tax != Total)
    make_pdf("06_edge_math_mismatch_hardware.pdf", "Dell Technologies - Quotation & Invoice", [
        "Vendor: Dell Technologies Inc.",
        "Invoice Number: DELL-INV-5501",
        "Invoice Date: 2026-03-12",
        "Currency: USD",
        "",
        "Item: Dell XPS 15 Developer Edition Laptop",
        "Subtotal: $1800.00",
        "Sales Tax: $180.00",
        "Total Due: $2450.00",  # INTENTIONAL MISMATCH: 1800 + 180 = 1980, NOT 2450!
        "",
        "Note: Hand-edited discrepancy by vendor salesperson."
    ])

    # 7. EDGE CASE: Missing Invoice Number & Foreign Currency (AED)
    make_pdf("07_edge_foreign_aed_no_inv_num.pdf", "Dubai Tech Supplies FZ-LLC", [
        "Vendor: Dubai Tech Supplies FZ-LLC",
        "Invoice Date: 2026-02-28",
        # Notice: NO INVOICE NUMBER SPECIFIED
        "Currency: AED",
        "",
        "Description: 2x 4K UltraWide Monitor Displays",
        "Subtotal: 3200.00 AED",
        "VAT (5%): 160.00 AED",
        "Total Payable: 3360.00 AED",
        "",
        "Payable via Emirates NBD transfer."
    ])

    # 8. EDGE CASE: Suspected Duplicate Invoice
    # Same vendor and same invoice number as Case 1!
    make_pdf("08_edge_duplicate_aws_invoice.pdf", "Amazon Web Services Inc. - Duplicate Copy", [
        "Vendor: Amazon Web Services, Inc.",
        "Invoice Number: INV-AWS-2026-9812",  # DUPLICATE of test 1
        "Invoice Date: 2026-03-15",
        "Currency: USD",
        "",
        "Amazon Web Services Cloud Monthly Charges",
        "Subtotal: $160.00",
        "Tax: $0.00",
        "Total Amount Due: $160.00"
    ])

    # 9. EDGE CASE: Scanned Store Receipt Image (PNG)
    make_receipt_img("09_scanned_office_supplies.png", "STAPLES & OFFICE DEPOT STORE", [
        "Store #491 - Austin, TX",
        "Vendor: Staples Office Supplies",
        "Receipt #: ST-77219",
        "Date: 2026-03-14",
        "",
        "Copy Paper Letter Ream (10pk) .. $ 45.99",
        "Gel Pen Set Black (24pk) ....... $ 14.50",
        "Heavy Duty Packing Tape ........ $ 12.00",
        "",
        "Subtotal: $ 72.49",
        "State Tax (6%): $ 4.35",
        "Total: $ 76.84",
        "",
        "Barcode: ||| | ||||| |||| || |||"
    ])

    # 10. FAILURE CASE: Non-Invoice Document (NDA Agreement)
    make_pdf("10_failure_nda_legal_contract.pdf", "NON-DISCLOSURE AGREEMENT (NDA)", [
        "This Mutual Non-Disclosure Agreement is entered into between",
        "Party A: Wosler Solutions LLC",
        "Party B: Client Partner Corp.",
        "",
        "1. Confidential Information: Both parties agree to protect proprietary",
        "source code, trade secrets, algorithms, and client data.",
        "2. Term: This agreement shall remain in effect for 3 years.",
        "3. Jurisdiction: Laws of the State of Delaware.",
        "",
        "Signed: John Doe, Director               Date: 2026-01-10",
        "Signed: Shoaib Rao, Principal Consultant   Date: 2026-01-10"
    ])

if __name__ == "__main__":
    generate_all()
