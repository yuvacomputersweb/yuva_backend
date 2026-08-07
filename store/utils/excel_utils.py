"""
store/utils/excel_utils.py
Excel Import / Export for Yuva Computers store.

Sheets:
  1. Categories
  2. Brands
  3. UsageTags
  4. Products
  5. ProductVariants
  6. Reviews
  7. Coupons
  8. SiteConfig

Images: paste a public URL (Google Drive share link, direct image URL, etc.)
        Import will download and save the image automatically.
"""
from __future__ import annotations

import io
import urllib.request
import urllib.error
import os
from decimal import Decimal, InvalidOperation
from typing import Any

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


# ──────────────────────────── Style constants ────────────────────────────────

HEADER_FILL  = PatternFill("solid", fgColor="1F4C8C")   # Yuva primary blue
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
LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)


# ──────────────────────────── Style helpers ──────────────────────────────────

def _style_header_row(ws: Worksheet, row: int, num_cols: int) -> None:
    for col in range(1, num_cols + 1):
        c = ws.cell(row=row, column=col)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = CENTER
        c.border = BORDER


def _style_help_row(ws: Worksheet, row: int, num_cols: int) -> None:
    for col in range(1, num_cols + 1):
        c = ws.cell(row=row, column=col)
        c.fill = SECTION_FILL
        c.font = SECTION_FONT
        c.alignment = LEFT
        c.border = BORDER


def _style_data_row(ws: Worksheet, row: int, num_cols: int, alt: bool = False) -> None:
    for col in range(1, num_cols + 1):
        c = ws.cell(row=row, column=col)
        if alt:
            c.fill = ALT_FILL
        c.font = NORMAL_FONT
        c.alignment = LEFT
        c.border = BORDER


def _freeze_and_fit(ws: Worksheet) -> None:
    ws.freeze_panes = ws.cell(row=3, column=1)  # freeze help+header rows
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 50)


# ──────────────────────────── Type coercers ──────────────────────────────────

def _str(val: Any) -> str:
    return str(val).strip() if val is not None else ""


def _bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().upper() in ("TRUE", "YES", "1")


def _dec(val: Any, default: str = "0.00") -> Decimal:
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, TypeError):
        return Decimal(default)


def _int(val: Any, default: int = 0) -> int:
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default


# ──────────────────────────── Image downloader ───────────────────────────────

def _download_image(url: str, upload_to: str) -> str | None:
    """
    Download an image from a public URL (including Google Drive share links)
    and save it to MEDIA_ROOT/<upload_to>/.
    Returns the relative path (for ImageField.name) or None on failure.
    """
    if not url:
        return None

    # Convert Google Drive share links to direct download
    # e.g. https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    #   -> https://drive.google.com/uc?export=download&id=FILE_ID
    url = url.strip()
    if "drive.google.com/file/d/" in url:
        try:
            file_id = url.split("/file/d/")[1].split("/")[0]
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
        except IndexError:
            pass

    try:
        from django.conf import settings
        import uuid

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "image/jpeg")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"
            elif "gif" in content_type:
                ext = ".gif"

            filename = f"{uuid.uuid4().hex}{ext}"
            rel_path = os.path.join(upload_to, filename)
            abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)

            os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            with open(abs_path, "wb") as f:
                f.write(response.read())

        return rel_path

    except Exception as e:
        return None


# ──────────────────────────── Sheet builders (Export) ────────────────────────

def _build_categories_sheet(ws: Worksheet, categories) -> None:
    ws.title = "Categories"
    help_row = ["(blank=create new)", "Required", "Auto if blank", "TRUE/FALSE", "TRUE/FALSE"]
    headers  = ["id", "name", "slug", "is_featured", "image_url"]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, cat in enumerate(categories, start=3):
        ws.append([
            cat.id, cat.name, cat.slug,
            str(cat.is_featured),
            cat.image.url if cat.image else "",
        ])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


def _build_brands_sheet(ws: Worksheet, brands) -> None:
    ws.title = "Brands"
    help_row = ["(blank=create)", "Required", "Auto if blank"]
    headers  = ["id", "name", "slug"]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, b in enumerate(brands, start=3):
        ws.append([b.id, b.name, b.slug])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


def _build_usagetags_sheet(ws: Worksheet, tags) -> None:
    ws.title = "UsageTags"
    help_row = ["(blank=create)", "Required", "Auto if blank", "Lucide icon name e.g. gamepad"]
    headers  = ["id", "name", "slug", "icon"]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, t in enumerate(tags, start=3):
        ws.append([t.id, t.name, t.slug, t.icon])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


def _build_products_sheet(ws: Worksheet, products) -> None:
    ws.title = "Products"
    help_row = [
        "(blank=create)", "Required", "Auto if blank", "Required-unique",
        "Must match Brands slug", "Must match Categories slug",
        "like_new/excellent/good/value",
        "Required", "Optional",
        "e.g. Intel i5-10th", "e.g. 8GB DDR4", "e.g. 256GB SSD",
        "e.g. 14inch FHD", "e.g. NVIDIA GTX", "e.g. Windows 11 Pro",
        "e.g. 6 Cell", "e.g. 1.8 kg", "e.g. USB-A x2 USB-C x1",
        "e.g. Wi-Fi 6", "e.g. Bluetooth 5.0",
        "Optional", "Newline-separated highlights",
        "e.g. 40+ Quality Checks", "Newline-separated points",
        "e.g. 6 Months Warranty", "Newline-separated details",
        "e.g. 350+ Service Centers", "e.g. 1 Year Warranty", "e.g. 14 Days Return",
        "TRUE/FALSE", "TRUE/FALSE", "TRUE/FALSE", "TRUE/FALSE", "TRUE/FALSE",
        "Comma-separated usage tag slugs e.g. gaming,coding",
    ]
    headers = [
        "id", "title", "slug", "sku",
        "brand_slug", "category_slug", "condition",
        "price", "original_price",
        "processor", "ram", "storage", "display", "graphics",
        "operating_system", "battery", "weight", "ports", "wifi", "bluetooth",
        "description", "highlights",
        "refurbishment_summary", "refurbishment_points",
        "warranty_summary", "warranty_details",
        "service_centers", "warranty_period", "return_policy",
        "is_new_arrival", "is_best_seller", "is_trending", "is_best_deal", "is_active",
        "usage_tag_slugs",
    ]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, p in enumerate(products, start=3):
        usage_slugs = ",".join(p.usage_tags.values_list("slug", flat=True))
        ws.append([
            p.id, p.title, p.slug, p.sku,
            p.brand.slug if p.brand else "",
            p.category.slug if p.category else "",
            p.condition,
            str(p.price),
            str(p.original_price) if p.original_price else "",
            p.processor, p.ram, p.storage, p.display, p.graphics,
            p.operating_system, p.battery, p.weight, p.ports, p.wifi, p.bluetooth,
            p.description, p.highlights,
            p.refurbishment_summary, p.refurbishment_points,
            p.warranty_summary, p.warranty_details,
            p.service_centers, p.warranty_period, p.return_policy,
            str(p.is_new_arrival), str(p.is_best_seller),
            str(p.is_trending), str(p.is_best_deal), str(p.is_active),
            usage_slugs,
        ])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


def _build_variants_sheet(ws: Worksheet, variants) -> None:
    ws.title = "ProductVariants"
    help_row = [
        "(blank=create)", "Must match Products sku",
        "e.g. Intel i5-10th Gen (blank if not used)",
        "e.g. 8GB", "e.g. 256GB SSD",
        "Integer ≥ 0", "Extra amount added to base price (0 if none)",
    ]
    headers = ["id", "product_sku", "processor", "ram", "storage", "stock", "price_override"]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, v in enumerate(variants, start=3):
        ws.append([
            v.id, v.product.sku,
            v.processor, v.ram, v.storage,
            v.stock, str(v.price_override),
        ])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


def _build_reviews_sheet(ws: Worksheet, reviews) -> None:
    ws.title = "Reviews"
    help_row = [
        "(blank=create)", "Must match Products sku",
        "Required", "1-5", "Required",
        "e.g. Hyderabad, India", "TRUE/FALSE",
    ]
    headers = ["id", "product_sku", "user_name", "rating", "comment", "location", "is_featured"]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, r in enumerate(reviews, start=3):
        ws.append([
            r.id, r.product.sku, r.user_name,
            r.rating, r.comment, r.location,
            str(r.is_featured),
        ])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


def _build_coupons_sheet(ws: Worksheet, coupons) -> None:
    ws.title = "Coupons"
    help_row = [
        "(blank=create)", "Unique code",
        "percentage OR fixed", "e.g. 10 or 200",
        "0 = no minimum", "YYYY-MM-DD HH:MM",
        "YYYY-MM-DD HH:MM", "TRUE/FALSE", "Integer",
        "Read-only — auto managed",
    ]
    headers = [
        "id", "code", "discount_type", "value",
        "min_order_value", "valid_from", "valid_to",
        "active", "usage_limit", "uses_count",
    ]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, c in enumerate(coupons, start=3):
        ws.append([
            c.id, c.code, c.discount_type, str(c.value),
            str(c.min_order_value),
            c.valid_from.strftime("%Y-%m-%d %H:%M") if c.valid_from else "",
            c.valid_to.strftime("%Y-%m-%d %H:%M") if c.valid_to else "",
            str(c.active), c.usage_limit, c.uses_count,
        ])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


def _build_siteconfig_sheet(ws: Worksheet, configs) -> None:
    ws.title = "SiteConfig"
    help_row = [
        "(blank=create)", "e.g. 100.00", "e.g. 999.00",
        "e.g. 2.00 (% for COD)", "e.g. 0.00",
        "With country code e.g. 919709888456",
    ]
    headers = [
        "id", "shipping_fee", "free_shipping_threshold",
        "cod_surcharge_percentage", "tax_percentage", "whatsapp_number",
    ]
    ws.append(help_row)
    ws.append(headers)
    _style_help_row(ws, 1, len(headers))
    _style_header_row(ws, 2, len(headers))

    for idx, cfg in enumerate(configs, start=3):
        ws.append([
            cfg.id,
            str(cfg.shipping_fee),
            str(cfg.free_shipping_threshold),
            str(cfg.cod_surcharge_percentage),
            str(cfg.tax_percentage),
            cfg.whatsapp_number,
        ])
        _style_data_row(ws, idx, len(headers), alt=(idx % 2 == 0))
    _freeze_and_fit(ws)


# ──────────────────────────── Public export API ──────────────────────────────

def export_to_excel(
    categories, brands, usage_tags, products,
    variants, reviews, coupons, site_configs
) -> bytes:
    """Build the full workbook and return raw bytes for an HttpResponse."""
    wb = Workbook()
    wb.remove(wb.active)  # remove default blank sheet

    _build_categories_sheet(wb.create_sheet(), categories)
    _build_brands_sheet(wb.create_sheet(), brands)
    _build_usagetags_sheet(wb.create_sheet(), usage_tags)
    _build_products_sheet(wb.create_sheet(), products)
    _build_variants_sheet(wb.create_sheet(), variants)
    _build_reviews_sheet(wb.create_sheet(), reviews)
    _build_coupons_sheet(wb.create_sheet(), coupons)
    _build_siteconfig_sheet(wb.create_sheet(), site_configs)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────── Import result tracker ─────────────────────────

class ExcelImportResult:
    def __init__(self):
        self.created: dict[str, int] = {}
        self.updated: dict[str, int] = {}
        self.skipped: int = 0
        self.errors: list[str] = []

    def add_created(self, sheet: str) -> None:
        self.created[sheet] = self.created.get(sheet, 0) + 1

    def add_updated(self, sheet: str) -> None:
        self.updated[sheet] = self.updated.get(sheet, 0) + 1

    def add_skipped(self) -> None:
        self.skipped += 1

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def summary(self) -> str:
        parts = []
        for sheet, n in self.created.items():
            parts.append(f"{n} {sheet} created")
        for sheet, n in self.updated.items():
            parts.append(f"{n} {sheet} updated")
        if self.skipped:
            parts.append(f"{self.skipped} rows skipped (empty)")
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        return " · ".join(parts) if parts else "No changes made."

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "summary": self.summary(),
        }


# ──────────────────────────── Sheet reader ───────────────────────────────────

def _read_sheet(wb: Workbook, name: str) -> list[dict]:
    """
    Return list-of-dicts from a named sheet.
    Row 1 = help text (skipped)
    Row 2 = column headers
    Row 3+ = data
    """
    if name not in wb.sheetnames:
        return []
    ws = wb[name]
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 3:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[1]]
    result = []
    for row in rows[2:]:
        if all(v is None or str(v).strip() == "" for v in row):
            continue  # skip completely empty rows
        result.append(dict(zip(headers, row)))
    return result


# ──────────────────────────── Public import API ──────────────────────────────

def import_from_excel(file_obj) -> ExcelImportResult:
    """
    Parse the uploaded Excel workbook and upsert all model objects.
    Processes sheets in dependency order:
      Categories → Brands → UsageTags → Products → Variants → Reviews → Coupons → SiteConfig
    """
    from django.utils.text import slugify
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone

    from store.models import (
        Brand, Category, UsageTag, Product, ProductVariant,
        Review, Coupon, SiteConfig,
    )

    result = ExcelImportResult()
    wb = openpyxl.load_workbook(file_obj)

    # ── 1. Categories ────────────────────────────────────────────────────────
    for row in _read_sheet(wb, "Categories"):
        try:
            name = _str(row.get("name"))
            if not name:
                result.add_skipped()
                continue

            slug = _str(row.get("slug")) or slugify(name)
            defaults = dict(
                name=name,
                slug=slug,
                is_featured=_bool(row.get("is_featured", False)),
            )

            # Handle image URL
            img_url = _str(row.get("image_url"))
            if img_url:
                saved_path = _download_image(img_url, "categories")
                if saved_path:
                    defaults["image"] = saved_path

            rid = row.get("id")
            if rid:
                obj, created = Category.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                obj, created = Category.objects.update_or_create(
                    slug=slug, defaults=defaults
                )
            result.add_created("Category") if created else result.add_updated("Category")

        except Exception as e:
            result.add_error(f"[Categories] Row '{row.get('name', '?')}': {e}")

    # ── 2. Brands ────────────────────────────────────────────────────────────
    for row in _read_sheet(wb, "Brands"):
        try:
            name = _str(row.get("name"))
            if not name:
                result.add_skipped()
                continue

            slug = _str(row.get("slug")) or slugify(name)
            defaults = dict(name=name, slug=slug)

            rid = row.get("id")
            if rid:
                obj, created = Brand.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                obj, created = Brand.objects.update_or_create(
                    slug=slug, defaults=defaults
                )
            result.add_created("Brand") if created else result.add_updated("Brand")

        except Exception as e:
            result.add_error(f"[Brands] Row '{row.get('name', '?')}': {e}")

    # ── 3. UsageTags ─────────────────────────────────────────────────────────
    for row in _read_sheet(wb, "UsageTags"):
        try:
            name = _str(row.get("name"))
            if not name:
                result.add_skipped()
                continue

            slug = _str(row.get("slug")) or slugify(name)
            defaults = dict(
                name=name,
                slug=slug,
                icon=_str(row.get("icon")),
            )

            rid = row.get("id")
            if rid:
                obj, created = UsageTag.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                obj, created = UsageTag.objects.update_or_create(
                    slug=slug, defaults=defaults
                )
            result.add_created("UsageTag") if created else result.add_updated("UsageTag")

        except Exception as e:
            result.add_error(f"[UsageTags] Row '{row.get('name', '?')}': {e}")

    # ── 4. Products ──────────────────────────────────────────────────────────
    for row in _read_sheet(wb, "Products"):
        try:
            title = _str(row.get("title"))
            sku   = _str(row.get("sku"))

            if not title or not sku:
                result.add_skipped()
                continue

            # Resolve foreign keys
            brand_slug = _str(row.get("brand_slug"))
            cat_slug   = _str(row.get("category_slug"))

            try:
                brand = Brand.objects.get(slug=brand_slug)
            except Brand.DoesNotExist:
                result.add_error(
                    f"[Products] SKU='{sku}': brand slug '{brand_slug}' not found. Row skipped."
                )
                continue

            try:
                category = Category.objects.get(slug=cat_slug)
            except Category.DoesNotExist:
                result.add_error(
                    f"[Products] SKU='{sku}': category slug '{cat_slug}' not found. Row skipped."
                )
                continue

            # Validate condition value
            condition = _str(row.get("condition", "excellent")).lower()
            valid_conditions = ["like_new", "excellent", "good", "value"]
            if condition not in valid_conditions:
                result.add_error(
                    f"[Products] SKU='{sku}': condition '{condition}' invalid. "
                    f"Use one of: {', '.join(valid_conditions)}. Row skipped."
                )
                continue

            slug = _str(row.get("slug")) or slugify(title)
            orig = row.get("original_price")

            defaults = dict(
                title=title,
                slug=slug,
                brand=brand,
                category=category,
                condition=condition,
                price=_dec(row.get("price")),
                original_price=_dec(orig) if orig else None,
                processor=_str(row.get("processor")),
                ram=_str(row.get("ram")),
                storage=_str(row.get("storage")),
                display=_str(row.get("display")),
                graphics=_str(row.get("graphics")),
                operating_system=_str(row.get("operating_system")) or "Windows 11 Pro",
                battery=_str(row.get("battery")),
                weight=_str(row.get("weight")),
                ports=_str(row.get("ports")),
                wifi=_str(row.get("wifi")) or "Wi-Fi 6",
                bluetooth=_str(row.get("bluetooth")) or "Bluetooth 5.0",
                description=_str(row.get("description")),
                highlights=_str(row.get("highlights")),
                refurbishment_summary=_str(row.get("refurbishment_summary")) or "40+ Quality Checks Passed",
                refurbishment_points=_str(row.get("refurbishment_points")),
                warranty_summary=_str(row.get("warranty_summary")) or "6 Months Warranty",
                warranty_details=_str(row.get("warranty_details")),
                service_centers=_str(row.get("service_centers")) or "350+ Service Centers",
                warranty_period=_str(row.get("warranty_period")) or "1 Year Warranty",
                return_policy=_str(row.get("return_policy")) or "14 Days Return",
                is_new_arrival=_bool(row.get("is_new_arrival", False)),
                is_best_seller=_bool(row.get("is_best_seller", False)),
                is_trending=_bool(row.get("is_trending", False)),
                is_best_deal=_bool(row.get("is_best_deal", False)),
                is_active=_bool(row.get("is_active", True)),
            )

            rid = row.get("id")
            if rid:
                obj, created = Product.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                obj, created = Product.objects.update_or_create(
                    sku=sku, defaults=defaults
                )

            # Handle usage tags (comma-separated slugs)
            usage_slugs_raw = _str(row.get("usage_tag_slugs"))
            if usage_slugs_raw:
                slugs = [s.strip() for s in usage_slugs_raw.split(",") if s.strip()]
                tags = UsageTag.objects.filter(slug__in=slugs)
                obj.usage_tags.set(tags)

            result.add_created("Product") if created else result.add_updated("Product")

        except Exception as e:
            result.add_error(f"[Products] SKU='{row.get('sku', '?')}': {e}")

    # ── 5. ProductVariants ───────────────────────────────────────────────────
    for row in _read_sheet(wb, "ProductVariants"):
        try:
            prod_sku = _str(row.get("product_sku"))
            ram      = _str(row.get("ram"))
            storage  = _str(row.get("storage"))

            if not prod_sku or not ram or not storage:
                result.add_skipped()
                continue

            try:
                product = Product.objects.get(sku=prod_sku)
            except Product.DoesNotExist:
                result.add_error(
                    f"[ProductVariants] product_sku='{prod_sku}' not found. Row skipped."
                )
                continue

            processor = _str(row.get("processor"))  # can be blank

            defaults = dict(
                stock=_int(row.get("stock", 0)),
                price_override=_dec(row.get("price_override", "0.00")),
            )

            rid = row.get("id")
            if rid:
                obj, created = ProductVariant.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                obj, created = ProductVariant.objects.update_or_create(
                    product=product,
                    processor=processor,
                    ram=ram,
                    storage=storage,
                    defaults=defaults,
                )
            result.add_created("Variant") if created else result.add_updated("Variant")

        except Exception as e:
            result.add_error(
                f"[ProductVariants] product_sku='{row.get('product_sku', '?')}' "
                f"ram='{row.get('ram', '?')}' storage='{row.get('storage', '?')}': {e}"
            )

    # ── 6. Reviews ───────────────────────────────────────────────────────────
    for row in _read_sheet(wb, "Reviews"):
        try:
            prod_sku  = _str(row.get("product_sku"))
            user_name = _str(row.get("user_name"))
            comment   = _str(row.get("comment"))

            if not prod_sku or not user_name or not comment:
                result.add_skipped()
                continue

            try:
                product = Product.objects.get(sku=prod_sku)
            except Product.DoesNotExist:
                result.add_error(
                    f"[Reviews] product_sku='{prod_sku}' not found. Row skipped."
                )
                continue

            rating = _int(row.get("rating", 5))
            if rating not in range(1, 6):
                rating = 5

            defaults = dict(
                product=product,
                user_name=user_name,
                rating=rating,
                comment=comment,
                location=_str(row.get("location")) or "India",
                is_featured=_bool(row.get("is_featured", False)),
            )

            rid = row.get("id")
            if rid:
                obj, created = Review.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                # Reviews don't have a natural unique key besides product+user
                # so always create new if no id provided
                Review.objects.create(**defaults)
                created = True

            result.add_created("Review") if created else result.add_updated("Review")

        except Exception as e:
            result.add_error(
                f"[Reviews] product_sku='{row.get('product_sku', '?')}' "
                f"user='{row.get('user_name', '?')}': {e}"
            )

    # ── 7. Coupons ───────────────────────────────────────────────────────────
    for row in _read_sheet(wb, "Coupons"):
        try:
            code = _str(row.get("code", "")).upper()
            if not code:
                result.add_skipped()
                continue

            discount_type = _str(row.get("discount_type", "percentage")).lower()
            if discount_type not in ("percentage", "fixed"):
                result.add_error(
                    f"[Coupons] code='{code}': discount_type must be 'percentage' or 'fixed'. Row skipped."
                )
                continue

            vf_raw = _str(row.get("valid_from"))
            vt_raw = _str(row.get("valid_to"))
            vf = parse_datetime(vf_raw) if vf_raw else timezone.now()
            vt = parse_datetime(vt_raw) if vt_raw else timezone.now()

            if not vf:
                result.add_error(
                    f"[Coupons] code='{code}': valid_from '{vf_raw}' is not a valid datetime "
                    f"(use YYYY-MM-DD HH:MM). Row skipped."
                )
                continue
            if not vt:
                result.add_error(
                    f"[Coupons] code='{code}': valid_to '{vt_raw}' is not a valid datetime. Row skipped."
                )
                continue

            defaults = dict(
                discount_type=discount_type,
                value=_dec(row.get("value", "0")),
                min_order_value=_dec(row.get("min_order_value", "0")),
                valid_from=vf,
                valid_to=vt,
                active=_bool(row.get("active", True)),
                usage_limit=_int(row.get("usage_limit", 100)),
            )

            rid = row.get("id")
            if rid:
                obj, created = Coupon.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                obj, created = Coupon.objects.update_or_create(
                    code=code, defaults=defaults
                )
            result.add_created("Coupon") if created else result.add_updated("Coupon")

        except Exception as e:
            result.add_error(f"[Coupons] code='{row.get('code', '?')}': {e}")

    # ── 8. SiteConfig ────────────────────────────────────────────────────────
    for row in _read_sheet(wb, "SiteConfig"):
        try:
            defaults = dict(
                shipping_fee=_dec(row.get("shipping_fee", "0")),
                free_shipping_threshold=_dec(row.get("free_shipping_threshold", "0")),
                cod_surcharge_percentage=_dec(row.get("cod_surcharge_percentage", "2")),
                tax_percentage=_dec(row.get("tax_percentage", "0")),
                whatsapp_number=_str(row.get("whatsapp_number", "919709888456")),
            )

            rid = row.get("id")
            if rid:
                obj, created = SiteConfig.objects.update_or_create(
                    id=_int(rid), defaults=defaults
                )
            else:
                obj = SiteConfig.objects.first()
                if obj:
                    for k, v in defaults.items():
                        setattr(obj, k, v)
                    obj.save()
                    created = False
                else:
                    SiteConfig.objects.create(**defaults)
                    created = True

            result.add_created("SiteConfig") if created else result.add_updated("SiteConfig")

        except Exception as e:
            result.add_error(f"[SiteConfig] Row: {e}")

    return result