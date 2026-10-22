"""Product-independent LED geometry. Decimal prevents cabinet-boundary drift."""
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_UP


def number(value, name, minimum=0, maximum=10000000):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError(f"{name} must be a number") from None
    if not result.is_finite() or result < minimum or result > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def integer(value, name, maximum=2000):
    result = number(value, name, 1, maximum)
    if result != result.to_integral_value():
        raise ValueError(f"{name} must be a whole number")
    return int(result)


def calculate(data):
    product = data.get("product")
    if not isinstance(product, dict):
        raise ValueError("Select a product")
    unit = data.get("unit", "m")
    if unit not in ("m", "ft"):
        raise ValueError("Unit must be m or ft")
    scale = Decimal("0.3048") if unit == "ft" else Decimal(1)
    # Canonical nanometre precision removes drift from rounded feet inputs.
    metre = lambda value: value.quantize(Decimal(".000000001"), rounding=ROUND_HALF_UP)
    wall_w = metre(number(data.get("wall_width"), "Wall width", .01, 1000) * scale)
    wall_h = metre(number(data.get("wall_height"), "Wall height", .01, 1000) * scale)
    cw = number(product.get("width_mm"), "Cabinet width", 1, 10000) / 1000
    ch = number(product.get("height_mm"), "Cabinet height", 1, 10000) / 1000
    raw_pw, raw_ph = product.get("pixels_w"), product.get("pixels_h")
    if (raw_pw in (None, "")) != (raw_ph in (None, "")):
        raise ValueError("Provide both cabinet pixel width and height, or leave both unknown")
    pw = None if raw_pw in (None, "") else integer(raw_pw, "Cabinet pixel width", 10000)
    ph = None if raw_ph in (None, "") else integer(raw_ph, "Cabinet pixel height", 10000)
    mode = data.get("mode", "dimensions")
    policy = data.get("policy", "within")
    rounding = {"within": ROUND_FLOOR, "nearest": ROUND_HALF_UP, "cover": ROUND_CEILING}
    if policy not in rounding:
        raise ValueError("Unknown sizing policy")
    requested = None
    if mode == "grid":
        cols = integer(data.get("columns"), "Columns")
        rows = integer(data.get("rows"), "Rows")
    elif mode == "resolution":
        if pw is None or ph is None:
            raise ValueError("Target-resolution sizing requires confirmed cabinet pixel width and height. Use dimensions or cabinet grid for this model.")
        rw = integer(data.get("target_pixels_w"), "Target pixel width", 100000)
        rh = integer(data.get("target_pixels_h"), "Target pixel height", 100000)
        cols = int((Decimal(rw) / pw).to_integral_value(rounding=ROUND_CEILING))
        rows = int((Decimal(rh) / ph).to_integral_value(rounding=ROUND_CEILING))
        requested = {"pixels_w": rw, "pixels_h": rh}
    elif mode == "dimensions":
        rw = number(data.get("screen_width"), "Screen width", .001, 1000) * scale
        rh = number(data.get("screen_height"), "Screen height", .001, 1000) * scale
        # A size typed in feet is rounded to 3 decimals (e.g. 14.698 ft for 7 x 640 mm), so
        # treat anything within a tiny fraction of a cabinet as exactly that many cabinets.
        def whole(value, cabinet):
            ratio = metre(value) / cabinet
            nearest = ratio.to_integral_value(rounding=ROUND_HALF_UP)
            return nearest if nearest >= 1 and abs(ratio - nearest) <= Decimal("0.001") else None
        snap_w, snap_h = whole(rw, cw), whole(rh, ch)
        cols = int(snap_w) if snap_w is not None else int((metre(rw) / cw).to_integral_value(rounding=rounding[policy]))
        rows = int(snap_h) if snap_h is not None else int((metre(rh) / ch).to_integral_value(rounding=rounding[policy]))
        requested = {"width_m": float(rw), "height_m": float(rh), "width_m_exact": str(rw), "height_m_exact": str(rh), "width_input": str(data.get("screen_width")), "height_input": str(data.get("screen_height")), "unit": unit}
    else:
        raise ValueError("Unknown sizing mode")
    if cols < 1 or rows < 1:
        raise ValueError("The requested size cannot contain one whole cabinet. Increase it or change the sizing policy.")
    if cols > 2000 or rows > 2000 or cols * rows > 100000:
        raise ValueError("Layout exceeds the prototype's 100,000-cabinet limit")
    sw, sh, count = cols * cw, rows * ch, cols * rows
    size_difference = None
    cover_size = None
    if mode == "dimensions":
        size_difference = {"width": float(rw - sw), "height": float(rh - sh)}
        cover_size = {
            "width": float((rw / cw).to_integral_value(rounding=ROUND_CEILING) * cw),
            "height": float((rh / ch).to_integral_value(rounding=ROUND_CEILING) * ch),
        }
    if data.get("position", "centre") not in ("centre", "custom"):
        raise ValueError("Unknown screen position")
    x = (wall_w - sw) / 2 if data.get("position", "centre") == "centre" else metre(number(data.get("left", 0), "Left offset", 0, 1000) * scale)
    bottom = (wall_h - sh) / 2 if data.get("position", "centre") == "centre" else metre(number(data.get("bottom", 0), "Bottom offset", 0, 1000) * scale)
    margins = {"left": x, "right": wall_w - sw - x, "bottom": bottom, "top": wall_h - sh - bottom}
    # Exact conceptual geometry is independent from the whole-cabinet option.
    design_w, design_h = (rw, rh) if mode == "dimensions" else (sw, sh)
    design_x = (wall_w - design_w) / 2 if data.get("position", "centre") == "centre" else x
    design_bottom = (wall_h - design_h) / 2 if data.get("position", "centre") == "centre" else bottom
    design_margins = {"left": design_x, "right": wall_w - design_w - design_x, "bottom": design_bottom, "top": wall_h - design_h - design_bottom}
    design = {"width_m": float(design_w), "height_m": float(design_h), "area_m2": float(design_w * design_h), "margins_m": {k: float(v) for k, v in design_margins.items()}, "fits": all(v >= 0 for v in design_margins.values())}
    warnings = []
    fits = all(v >= 0 for v in margins.values())
    if not fits:
        warnings.append("The cabinet option exceeds the entered wall or position. The wall dimensions have been preserved.")
    if not design["fits"]:
        warnings.append("The exact design exceeds the entered wall or position.")
    environment = data.get("environment", "indoor")
    if environment not in ("indoor", "outdoor"):
        raise ValueError("Unknown environment")
    if product.get("environment") != environment:
        warnings.append("Selected product environment differs from the installation environment.")
    warnings.append("Controller compatibility, cabling and mounting require equipment and installation data.")
    if product.get("pixel_source") and not product.get("resolution_confirmed"):
        warnings.append("Pixel resolution uses user-supplied cabinet settings. Confirm model-specific native pixel counts before selecting a display controller.")
    if pw is None:
        warnings.append("Cabinet pixel resolution was not supplied. Dimensions and cabinet quantities are calculated; native resolution and controller capacity remain unconfirmed.")
    if product.get("demo", True):
        warnings.append("This is a fictional sample cabinet, not a manufacturer specification.")
    totals = {}
    for key in ("weight_kg", "typical_w", "maximum_w"):
        value = product.get(key)
        totals[key] = None if value in (None, "") else float(number(value, key) * count)
    if totals["typical_w"] is not None and totals["maximum_w"] is not None and totals["typical_w"] > totals["maximum_w"]:
        raise ValueError("Typical power must not exceed maximum power")
    price = data.get("cabinet_price")
    install = number(data.get("installation_cost", 0), "Installation cost", 0, 1000000000)
    tax = number(data.get("tax_percent", 0), "Tax percentage", 0, 100)
    quote = None
    if price not in (None, ""):
        cabinet_total = number(price, "Cabinet unit price", 0, 1000000000) * count
        subtotal = cabinet_total + install
        tax_value = (subtotal * tax / 100).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        quote = {"cabinet_total": float(cabinet_total), "installation": float(install), "subtotal": float(subtotal), "tax": float(tax_value), "total": float(subtotal + tax_value), "status": "Partial estimate: LED cabinets and installation only; other equipment excluded."}
    return {"columns": cols, "rows": rows, "count": count, "width_m": float(sw), "height_m": float(sh), "area_m2": float(sw * sh), "pixels_w": None if pw is None else cols * pw, "pixels_h": None if ph is None else rows * ph, "total_pixels": None if pw is None else cols * pw * rows * ph, "wall_width_m": float(wall_w), "wall_height_m": float(wall_h), "margins_m": {k: float(v) for k, v in margins.items()}, "fits": fits, "design": design, "requested": requested, "size_difference_m": size_difference, "cover_size_m": cover_size, "totals": totals, "warnings": warnings, "quote": quote}
