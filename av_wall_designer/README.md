# PROMARK LED STUDIO — Python LED Wall Designer

Original Python/Flask designer using the five supplied Unilumin catalogue models. It does not depend on UniDesigner's code or services.

## Windows startup

Extract the ZIP, then double-click **START-HERE.bat** in the outer folder. It creates a virtual environment, installs Flask and starts the server. Open http://127.0.0.1:5000 and keep the console open. Ctrl+C stops it. No PowerShell activation is required.

The outer folder now also contains **app.py**. To use PowerShell there:

```powershell
python -m pip install -r requirements.txt
python app.py
```

The app also runs from the nested `av_wall_designer` folder. Windows launcher code was inspected; automated tests ran on Linux.

## Supplied models

| Model | Environment | Cabinet W × H × D (mm) | Pitch (mm) | Brightness (nits) | Refresh (Hz) | Maintenance |
|---|---|---|---|---|---|---|
| UDAⅡ 1.2 | Indoor | 640 × 480 × 61.5 | 1.25 | 600 | 4200 | Front |
| UDAⅡ 1.5 | Indoor | 640 × 480 × 61.5 | 1.53 | 600 | 4200 | Front |
| UDAⅡ 2.5 | Indoor | 640 × 480 × 61.5 | 2.5 | 600 | 4200 | Front |
| UDAⅡ 1.8 | Indoor | 640 × 480 × 61.5 | 1.86 | 600 | 4200 | Front |
| Umate SF4 | Outdoor | 960 × 960 × 94 | 4.44 | 5000 | 3840 | Front & Rear |

Dimensions, brightness, refresh and maintenance come from the user's text. Pitch, listed regions, certifications and curve ranges come from the five screenshots dated 5 October 2026. Indoor/outdoor family classification was checked against manufacturer pages:
- https://www.unilumin.com/products/professional/uda-ii.html
- https://www.unilumin.com/products/dooh/umate-sf-for-outdoor-unilumin.html

The user selected catalogue dimensions for calculations. Indoor cabinets are approximately **2.100 × 1.575 ft**, outdoor **3.150 × 3.150 ft**. “2 by 2” / “3 by 3” do not override the supplied metric dimensions. The listed curve ranges are reference specs; geometry is for flat walls.

## Included

- Five models, indoor/outdoor filtering, catalogue cards and model specification dialog.
- Conference, hospital, sports, control room, retail, live events, exhibition and virtual production contexts.
- Default dimensions and reset presets; exact conceptual preview and separate buildable whole-cabinet layout.
- Live updates; typed decimal values are preserved; one-unit and model-specific button steps.
- Fit within / nearest / meet or exceed sizing; cabinet grid, clearances, overflow checking.
- Background finishes, wall photo, screen content image and human scale reference.
- View Results with all supplied model specifications and calculated quantities.
- Projects saved locally in SQLite; design JSON export; browser Print / Save PDF report.
- Cabinet and installation estimate from manually entered rates and tax.
- Responsive desktop and phone layout.

## Missing catalogue fields

The user has supplied cabinet pixel settings: 416 × 312 for every indoor model and 216 × 216 for Umate SF4. These are marked as user-supplied settings, not independently confirmed manufacturer native resolutions. They enable pixel readouts and resolution-target sizing. The screenshot pitch values are preserved separately. Weight, power, IP rating, pricing and controller/receiving-card compatibility remain `null` / Not provided.

Processor choices are manual selections from the supplied screenshots. Complete quotations and compatibility checks need processor specifications and prices. Application selection records planning context; it does not certify suitability for hospitals, sports or other installations.

Edit `catalogue.json` to add confirmed values, or import a JSON catalogue using Catalogue. `weight_kg`, `typical_w`, `maximum_w` are **per cabinet**, not per square metre. Session imports are retained in selected-product snapshots when saving projects; edit the JSON file for a permanent full catalogue update. Saved photos are not retained.

## Validation

Run from the nested folder:

```powershell
python -m unittest discover -s tests
```

## User model defaults and steps

| Model group | Unit | Screen start W × H | Width step | Height step | Wall start W × H | Wall step |
|---|---|---|---|---|---|---|
| All four UDAⅡ models | m | 0.64 × 0.48 | ±0.64 | ±0.48 | 5 × 3 | ±1 |
| All four UDAⅡ models | ft | 2.0997 × 1.5748 | ±2.0998 | ±1.5748 | 16.4 × 9.84 | ±1 |
| Umate SF4 | m | 0.96 × 0.96 | ±0.96 | ±0.96 | 5 × 3 | ±1 |
| Umate SF4 | ft | 3.1496 × 3.1496 | ±3.1496 | ±3.1496 | 16.4 × 9.84 | ±1 |

Model defaults are the starting preset. Changing the model resets screen dimensions and screen steps; it preserves the background wall. Reset with the model preset restores the screen and background defaults. Minus stops at the starting one-cabinet size; manually typed dimensions remain supported.

The user's feet defaults and steps are rounded values and are stored independently from metre values. When switching units, unedited defaults and the model-step sequence map to the corresponding unit settings; custom values convert using exactly 0.3048 m/ft. Custom background values convert normally. Dimension fields and preview labels show up to four digits after the decimal. Extra digits are truncated, never rounded up. Trailing zeros within those four digits are preserved. Decimal button arithmetic uses integer coefficients to avoid floating-point step errors.

Nearest-achievable sizing is the default: this handles rounded feet sizes without losing the first cabinet. Fit-within and cover remain available and use strict physical cabinet boundaries; a rounded requested size can differ slightly from an actual cabinet. Exact preview preserves the entered dimensions; cabinet preview uses physical manufacturer geometry.

## Four-decimal dimensions

Dimension inputs, previews and reports use up to four digits after the decimal. Extra digits are removed when leaving a field: `12.61149` becomes `12.6114`, not `12.6115`. Values already within four places remain unchanged: `2.0997`, `1.5748`, `3.1496`, `0.64` and `0.48`. Plus/minus uses exact decimal arithmetic and retains the specified model steps. Unit conversions and display dimensions use the same four-place truncation. This limits display/input precision; it does not change physical cabinet dimensions.

## Linked pixel controls

Pixel width and height appear beside the metre/feet settings. The readouts represent whole cabinets, not fractional LEDs. Width steps are 416 px for each indoor model and 216 px for Umate SF4; height steps are 312 px indoors and 216 px outdoors. Starting at one cabinet, one increase doubles the relevant axis; each later increase adds one cabinet rather than multiplying the previous pixel total. For example: 416 → 832 → 1248; 312 → 624 → 936; 216 → 432 → 648. Minus reverses these steps and stops at one cabinet. Pixel clicks use nearest-cabinet dimension mode, keep physical dimension fields visible, and link them to the corresponding cabinet count. Dimension/grid/resolution changes refresh pixel readouts after calculation.

The 416 × 312 setting is applied to all indoor models as explicitly requested. It is not necessarily the manufacturer native resolution for every pitch. Confirm each model's datasheet before using these pixel totals to specify controller capacity.

## Control System update

Audio planning has been removed from the designer, current exports and results table. The display control panel follows the supplied screenshots: Synchronizing / Asynchronizing mode buttons; VX400, SD700E and SDS6E processor dropdown; System Solutions dropdown with Standard, XR/VP Solutions, Content Security Solutions and Audio-Visual Integrated Solutions; Backup dropdown; Video support toggle and processor Details dialog. Video support records a project requirement, not a verified hardware capability. No processor specifications or compatibility guarantees are invented. The Audio-Visual Integrated Solutions option records a solution category; audio planning remains removed. Selected controls are preserved when loading saved projects, exported in JSON and shown in the results report. Older saved projects without these fields load with VX400, Standard and video support Not specified. Old synchronous/asynchronous labels map to the new mode names.

## PROMARK LED STUDIO update

**Branding.** The app is named *PROMARK LED STUDIO* (page title, header, footer, report heading and exported JSON file name). The Promark logo is installed as `av_wall_designer/static/logo.png` (header and printed report) with a square `favicon.png` for the browser tab. To swap in a different logo, replace `logo.png` (a transparent PNG works best) and refresh. If `logo.png` is missing, a "PM" badge and the text "PROMARK LED STUDIO" are shown instead. When the logo is present, the header reads logo + "PROMARK LED STUDIO", because the logo already carries the Promark name.

**Model pictures.** Every catalogue card, the sidebar summary and the specification dialog show a distinct representative illustration (files in `static/models/`, linked through the `image` field in `catalogue.json`):

| Model | Picture |
|---|---|
| UDAⅡ 1.2 | Angled front cabinet view |
| UDAⅡ 1.5 | Straight front view with colourful screen content |
| UDAⅡ 1.8 | Front and rear cabinet views together |
| UDAⅡ 2.5 | Cabinet with a module removed, showing front maintenance |
| Umate SF4 | Outdoor square cabinet, angled view |

These are drawn illustrations, not product photographs. They show the cabinet style only and do not indicate pixel pitch. To use real photos, replace the SVG files (keep the `models/<id>.svg` name) or change the `image` path.

**Screen picture with cabinet grid lines.** The default screen content is now a *Sample picture*, and the grid lines are drawn over it (or over any uploaded screen image / studio graphic) in both preview modes. As the screen is made larger or smaller, with the − / + buttons, typed values, pixel buttons or cabinet columns/rows, the grid redraws immediately. In the exact-dimension preview the lines are spaced at the real cabinet size (640 × 480 mm indoor, 960 × 960 mm outdoor) counting from the bottom-left corner, so a partial cabinet at the top or right is visible. In the buildable layout preview the lines show the whole-cabinet columns and rows. The lines can be switched off with the *Cabinet grid lines* checkbox.

## Accuracy fixes (pixels and area)

- **Pixels per cabinet** now follow each model's pitch: UDAⅡ 1.2 = 512 × 384 px, 1.5 = 416 × 312, 1.8 = 344 × 258, 2.5 = 256 × 192, Umate SF4 = 216 × 216. Previously all UDAⅡ models used 416 × 312, so P1.25 showed 2,912 × 1,560 px for 7 × 5 cabinets instead of 3,584 × 1,920. Please confirm these counts against the manufacturer datasheets.
- **Feet sizes and area:** cabinet steps are now exact multiples of the cabinet size (7 × 640 mm = 14.6982 ft, not 14.6985 ft), values are rounded rather than cut off at 4 decimals, and a size that is a whole number of cabinets is treated as exact, so design area matches (35 cabinets = 10.752 m² = 115.734 ft²).

## Space guides

The live elevation now shows the empty space around the screen with dotted guide lines. A row above the wall gives left space | screen width (with pixels) | right space, and a column on the right gives top space | screen height (with pixels) | bottom space. Dotted lines run from the screen edges to those rows. Pixel counts appear when the design is a whole number of cabinets. Use the *Space guides* checkbox above the preview to hide or show them.

**Best viewing distance.** Beside the person figure a dotted line to the wall shows the best (minimum comfortable) viewing distance, labelled "Best viewing distance". It uses the common rule of thumb of 1 metre per 1 mm of pixel pitch (P1.25 = 1.25 m = 4.1 ft, P2.5 = 2.5 m = 8.2 ft). The line is a marker only, not drawn to scale. It follows the *Space guides* checkbox and changes with the selected model and unit.

## Dimension display

Widths are shown to 4 decimal places (for example 14.6982 ft) and heights to 3 decimal places (for example 7.874 ft), in the inputs, results, drawing labels and space guides. Internally the calculation keeps full precision, and a size within about 0.6 mm of a whole number of cabinets is treated as exactly that many cabinets, so 14.6982 × 7.874 ft is still 7 × 5 cabinets (3,584 × 1,920 px).
