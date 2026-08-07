# Save as generate_sheet.py and run: python generate_sheet.py
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()
wb.remove(wb.active)

HEADER_FILL  = PatternFill("solid", fgColor="1F4C8C")
SECTION_FILL = PatternFill("solid", fgColor="2E75B6")
ALT_FILL     = PatternFill("solid", fgColor="EBF3FB")
HEADER_FONT  = Font(bold=True, color="FFFFFF", size=11)
SECTION_FONT = Font(bold=True, color="FFFFFF", size=10)
NORMAL_FONT  = Font(size=10)
BORDER = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
CENTER = Alignment(horizontal="center", vertical="center")
LEFT   = Alignment(horizontal="left", vertical="center", wrap_text=True)

def style_sheet(ws, help_row, headers, data_rows):
    ws.append(help_row)
    ws.append(headers)
    
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col)
        c.fill = SECTION_FILL
        c.font = SECTION_FONT
        c.alignment = LEFT
        c.border = BORDER
        
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=2, column=col)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = CENTER
        c.border = BORDER
        
    for idx, row in enumerate(data_rows, start=3):
        ws.append(row)
        alt = (idx % 2 == 0)
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=idx, column=col)
            if alt:
                c.fill = ALT_FILL
            c.font = NORMAL_FONT
            c.alignment = LEFT
            c.border = BORDER
            
    ws.freeze_panes = ws.cell(row=3, column=1)
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 50)

# 1. Categories
ws1 = wb.create_sheet("Categories")
style_sheet(ws1, 
    ["(blank=create new)", "Required", "Auto if blank", "TRUE/FALSE", "TRUE/FALSE"],
    ["id", "name", "slug", "is_featured", "image_url"],
    [
        ["", "Laptops", "laptops", "TRUE", "https://drive.google.com/file/d/1LV8QU7gxlH_cWHdL8GfbV30zcEr1UYBk/view?usp=sharing"],
        ["", "Desktops", "desktops", "FALSE", ""]
    ]
)

# 2. Brands
ws2 = wb.create_sheet("Brands")
style_sheet(ws2,
    ["(blank=create)", "Required", "Auto if blank"],
    ["id", "name", "slug"],
    [["", "Dell", "dell"], ["", "HP", "hp"], ["", "Lenovo", "lenovo"]]
)

# 3. UsageTags
ws3 = wb.create_sheet("UsageTags")
style_sheet(ws3,
    ["(blank=create)", "Required", "Auto if blank", "Lucide icon name e.g. gamepad"],
    ["id", "name", "slug", "icon"],
    [["", "Gaming", "gaming", "gamepad"], ["", "Business", "business", "briefcase"], ["", "Coding", "coding", "code"]]
)

# 4. Products
ws4 = wb.create_sheet("Products")
style_sheet(ws4,
    [
        "(blank=create)", "Required", "Auto if blank", "Required-unique",
        "Must match Brands slug", "Must match Categories slug", "like_new/excellent/good/value",
        "Required", "Optional", "e.g. Intel i5-10th", "e.g. 8GB DDR4", "e.g. 256GB SSD",
        "e.g. 14inch FHD", "e.g. NVIDIA GTX", "e.g. Windows 11 Pro", "e.g. 6 Cell",
        "e.g. 1.8 kg", "e.g. USB-A x2 USB-C x1", "e.g. Wi-Fi 6", "e.g. Bluetooth 5.0",
        "Optional", "Newline-separated highlights", "e.g. 40+ Quality Checks",
        "Newline-separated points", "e.g. 6 Months Warranty", "Newline-separated details",
        "e.g. 350+ Service Centers", "e.g. 1 Year Warranty", "e.g. 14 Days Return",
        "TRUE/FALSE", "TRUE/FALSE", "TRUE/FALSE", "TRUE/FALSE", "TRUE/FALSE",
        "Comma-separated usage tag slugs e.g. gaming,coding"
    ],
    [
        "id", "title", "slug", "sku", "brand_slug", "category_slug", "condition",
        "price", "original_price", "processor", "ram", "storage", "display", "graphics",
        "operating_system", "battery", "weight", "ports", "wifi", "bluetooth",
        "description", "highlights", "refurbishment_summary", "refurbishment_points",
        "warranty_summary", "warranty_details", "service_centers", "warranty_period",
        "return_policy", "is_new_arrival", "is_best_seller", "is_trending", "is_best_deal",
        "is_active", "usage_tag_slugs"
    ],
    [
        [
            "", "HP EliteBook 840 G7", "hp-elitebook-840-g7", "HP-ELITE-840G7",
            "hp", "laptops", "like_new", "38500.00", "52000.00",
            "Intel Core i7 10th Gen", "16GB DDR4", "512GB NVMe SSD", "14-inch Full HD IPS",
            "Intel UHD Graphics", "Windows 11 Pro", "3-Cell 53Wh", "1.33 kg",
            "USB 3.1 x2, Type-C Thunderbolt x2, HDMI x1", "Wi-Fi 6", "Bluetooth 5.0",
            "Premium lightweight business ultrabook with exceptional build quality.",
            "Intel i7 10th Gen\n16GB RAM & 512GB SSD\nUltra-slim Aluminum Chassis",
            "40+ Quality Checks Passed", "Display Checked\nBattery Health > 90%\nSound & Mic Tested",
            "6 Months Warranty Included", "Covers internal components and adapter replacement.",
            "350+ Service Centers", "6 Months Warranty", "7 Days Replacement",
            "TRUE", "FALSE", "TRUE", "TRUE", "TRUE", "business,coding"
        ]
    ]
)

# 5. ProductVariants
ws5 = wb.create_sheet("ProductVariants")
style_sheet(ws5,
    ["(blank=create)", "Must match Products sku", "e.g. Intel i5-10th Gen", "e.g. 8GB", "e.g. 256GB SSD", "Integer >= 0", "Extra amount"],
    ["id", "product_sku", "processor", "ram", "storage", "stock", "price_override"],
    [
        ["", "HP-ELITE-840G7", "Intel Core i7 10th Gen", "16GB DDR4", "512GB NVMe SSD", 8, "0.00"],
        ["", "HP-ELITE-840G7", "Intel Core i7 10th Gen", "32GB DDR4", "1TB NVMe SSD", 3, "6000.00"]
    ]
)

# 6. Reviews
ws6 = wb.create_sheet("Reviews")
style_sheet(ws6,
    ["(blank=create)", "Must match Products sku", "Required", "1-5", "Required", "e.g. Hyderabad", "TRUE/FALSE"],
    ["id", "product_sku", "user_name", "rating", "comment", "location", "is_featured"],
    [["", "HP-ELITE-840G7", "Ananya Reddy", 5, "Super lightweight and powerful laptop!", "Bengaluru", "TRUE"]]
)

# 7. Coupons
ws7 = wb.create_sheet("Coupons")
style_sheet(ws7,
    ["(blank=create)", "Unique code", "percentage OR fixed", "e.g. 10", "0 = no min", "YYYY-MM-DD HH:MM", "YYYY-MM-DD HH:MM", "TRUE/FALSE", "Integer"],
    ["id", "code", "discount_type", "value", "min_order_value", "valid_from", "valid_to", "active", "usage_limit"],
    [["", "WELCOME10", "percentage", "10", "1000", "2026-01-01 00:00", "2026-12-31 23:59", "TRUE", 100]]
)

# 8. SiteConfig
ws8 = wb.create_sheet("SiteConfig")
style_sheet(ws8,
    ["(blank=create)", "e.g. 100.00", "e.g. 999.00", "e.g. 2.00", "e.g. 0.00", "With country code"],
    ["id", "shipping_fee", "free_shipping_threshold", "cod_surcharge_percentage", "tax_percentage", "whatsapp_number"],
    [["1", "0.00", "1000.00", "2.00", "0.00", "919709888456"]]
)

wb.save("yuva_store_data_updated.xlsx")
print("✅ Saved as yuva_store_data_updated.xlsx")