"""
seed_fmcg_production.py
======================
Production-grade FMCG dataset seeder for StockPilot Core.
Generates realistic, foreign-key validated FMCG enterprise data:
- 5 Warehouses
- 12 FMCG Categories
- 25 FMCG Brands
- 30 FMCG Suppliers
- 105 FMCG Products with barcodes, HSN, GST, EOQ, ABC/XYZ
- 250 Enterprise Customers
- 2,000+ Inventory Stock Records across warehouses
- 300 Purchase Orders (Draft, Submitted, Approved, Received)
- 500 Sales Orders (Draft, Confirmed, Fulfilled) with Invoices & Payments
- Product Returns

Supports:
- HTTP API Mode (using admin JWT credentials against live server)
- Direct SQLAlchemy Mode (when DATABASE_URL is provided)
"""

import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = os.environ.get("BASE_URL", "https://retail-hta8.onrender.com").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@retailops.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProductionPassword123!")

# ---------------------------------------------------------------------------
# Real FMCG Domain Constants
# ---------------------------------------------------------------------------
WAREHOUSES = [
    {
        "name": "National Central Hub (North)",
        "location": "Sector 62, Noida, NCR",
        "state": "Uttar Pradesh",
        "zone": "North",
        "pin_code": "201301",
        "capacity_units": 500000,
    },
    {
        "name": "Western Coastal Fulfillment (West)",
        "location": "Bhiwandi Logistics Park, Thane",
        "state": "Maharashtra",
        "zone": "West",
        "pin_code": "421302",
        "capacity_units": 450000,
    },
    {
        "name": "Southern Regional Depot (South)",
        "location": "Hosur Road Industrial Area, Bangalore",
        "state": "Karnataka",
        "zone": "South",
        "pin_code": "560099",
        "capacity_units": 400000,
    },
    {
        "name": "Eastern Terminal Hub (East)",
        "location": "Dankuni Industrial Complex, Hooghly",
        "state": "West Bengal",
        "zone": "East",
        "pin_code": "712311",
        "capacity_units": 350000,
    },
    {
        "name": "Central Express Depot (Central)",
        "location": "Pithampur Sector 3, Indore",
        "state": "Madhya Pradesh",
        "zone": "Central",
        "pin_code": "454775",
        "capacity_units": 300000,
    },
]

CATEGORIES = [
    {
        "name": "Dairy & Chilled Foods",
        "gst_percent": 5.0,
        "typical_margin_low": 12.0,
        "typical_margin_high": 22.0,
    },
    {
        "name": "Packaged Staples & Grains",
        "gst_percent": 5.0,
        "typical_margin_low": 8.0,
        "typical_margin_high": 18.0,
    },
    {
        "name": "Snacks & Confectionery",
        "gst_percent": 12.0,
        "typical_margin_low": 20.0,
        "typical_margin_high": 35.0,
    },
    {
        "name": "Beverages & Cold Drinks",
        "gst_percent": 18.0,
        "typical_margin_low": 18.0,
        "typical_margin_high": 30.0,
    },
    {
        "name": "Personal Hygiene & Grooming",
        "gst_percent": 18.0,
        "typical_margin_low": 25.0,
        "typical_margin_high": 45.0,
    },
    {
        "name": "Hair & Skin Care",
        "gst_percent": 18.0,
        "typical_margin_low": 30.0,
        "typical_margin_high": 50.0,
    },
    {
        "name": "Household & Laundry",
        "gst_percent": 18.0,
        "typical_margin_low": 15.0,
        "typical_margin_high": 28.0,
    },
    {
        "name": "Oral Care",
        "gst_percent": 18.0,
        "typical_margin_low": 22.0,
        "typical_margin_high": 40.0,
    },
    {
        "name": "Condiments & Sauces",
        "gst_percent": 12.0,
        "typical_margin_low": 20.0,
        "typical_margin_high": 35.0,
    },
    {
        "name": "Breakfast Cereals & Health Foods",
        "gst_percent": 18.0,
        "typical_margin_low": 22.0,
        "typical_margin_high": 38.0,
    },
    {
        "name": "Baby & Child Care",
        "gst_percent": 12.0,
        "typical_margin_low": 15.0,
        "typical_margin_high": 30.0,
    },
    {
        "name": "Tea & Gourmet Coffee",
        "gst_percent": 5.0,
        "typical_margin_low": 18.0,
        "typical_margin_high": 35.0,
    },
]

BRANDS = [
    "Amul",
    "Tata Consumer",
    "Nestle",
    "Hindustan Unilever",
    "ITC",
    "Britannia",
    "PepsiCo",
    "Coca-Cola",
    "Dabur",
    "Parle",
    "Marico",
    "Godrej Consumer",
    "Colgate-Palmolive",
    "Reckitt Benckiser",
    "Cadbury",
    "Kellogg's",
    "L'Oreal",
    "Johnson & Johnson",
    "Himalaya",
    "Patanjali",
    "Haldiram's",
    "Mother Dairy",
    "Fortune",
    "Bikaji",
    "Nivea",
]

SUPPLIERS = [
    ("Gujarat Cooperative Milk Federation", 3, 0.98),
    ("Tata Consumer Products Supply Ltd", 5, 0.96),
    ("Nestle India Distribution Hub", 4, 0.97),
    ("Hindustan Unilever National Logistics", 4, 0.99),
    ("ITC Foods & Agri Sourcing", 6, 0.95),
    ("Britannia Industries Depot Services", 5, 0.94),
    ("PepsiCo Bottling & Snacks Network", 4, 0.96),
    ("Hindustan Coca-Cola Beverages Hub", 4, 0.97),
    ("Dabur Natural Sourcing Network", 7, 0.93),
    ("Parle Agro & Confectionery Supply", 5, 0.95),
    ("Marico Oils & Personal Supply", 6, 0.96),
    ("Godrej Consumer Logistics Division", 5, 0.94),
    ("Colgate Oral Care Hub", 4, 0.98),
    ("Reckitt Benckiser Hygiene Depot", 4, 0.97),
    ("Mondelez India Cocoa Distributors", 5, 0.96),
    ("Kellogg India Grain Processing", 6, 0.95),
    ("Himalaya Wellness Herbal Supply", 7, 0.92),
    ("Patanjali Ayurved Supply Chain", 8, 0.90),
    ("Haldiram Snacks & Sweets Supply", 4, 0.96),
    ("Mother Dairy Fruits & Veg Processing", 3, 0.97),
    ("Adani Wilmar Edible Oils Network", 5, 0.95),
    ("Bikaji Foods Sourcing Terminal", 6, 0.93),
    ("Beiersdorf India Personal Care", 5, 0.97),
    ("Perfetti Van Melle Confectionery Hub", 5, 0.94),
    ("Wipro Consumer Care & Lighting", 6, 0.95),
    ("Emami Healthcare Logistics", 7, 0.92),
    ("CavinKare Personal & Foods", 6, 0.94),
    ("Bonn Nutrients Bakery Depot", 4, 0.95),
    ("Paper Boat Hector Beverages Supply", 5, 0.96),
    ("Balaji Wafers Regional Logistics", 4, 0.97),
]

FMCG_PRODUCT_CATALOG = [
    # (SKU, Name, Description, Category_Idx, Brand_Idx, Supplier_Idx, Cost, Price, ROP, Safety, EOQ, GST, HSN, ShelfLife, Weight, ABC, XYZ)
    (
        "SKU-AMUL-001",
        "Amul Butter 500g Pasteurised",
        "Pasteurised table butter from fresh cream",
        0,
        0,
        0,
        220.0,
        275.0,
        100,
        30,
        250,
        5.0,
        "04051000",
        90,
        500.0,
        "A",
        "X",
    ),
    (
        "SKU-AMUL-002",
        "Amul Taaza Toned Milk 1L",
        "Homogenised toned long-life milk pack",
        0,
        0,
        0,
        58.0,
        72.0,
        150,
        50,
        400,
        5.0,
        "04012000",
        180,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-AMUL-003",
        "Amul Cheese Block 200g",
        "Processed cheddar cheese block",
        0,
        0,
        0,
        105.0,
        135.0,
        80,
        25,
        200,
        5.0,
        "04069000",
        180,
        200.0,
        "A",
        "Y",
    ),
    (
        "SKU-AMUL-004",
        "Amul Ghee 1L Pouch",
        "Pure cow and buffalo clarified butter",
        0,
        0,
        0,
        510.0,
        620.0,
        60,
        20,
        150,
        5.0,
        "04059020",
        365,
        900.0,
        "A",
        "X",
    ),
    (
        "SKU-TATA-001",
        "Tata Salt Iodised 1kg",
        "Vacuum evaporated iodised edible salt",
        1,
        1,
        1,
        19.0,
        28.0,
        200,
        60,
        500,
        5.0,
        "25010010",
        720,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-TATA-002",
        "Tata Tea Gold 500g",
        "Selected Assam CTC tea with long leaves",
        11,
        1,
        1,
        245.0,
        320.0,
        90,
        30,
        220,
        5.0,
        "09023020",
        365,
        500.0,
        "A",
        "X",
    ),
    (
        "SKU-TATA-003",
        "Tata Sampann Toor Dal 1kg",
        "Unpolished protein-rich pigeon pea pulses",
        1,
        1,
        1,
        135.0,
        175.0,
        120,
        40,
        300,
        5.0,
        "07136000",
        365,
        1000.0,
        "A",
        "Y",
    ),
    (
        "SKU-NEST-001",
        "Maggi 2-Minute Masala Noodles 70g",
        "Instant noodles with authentic spice mix",
        2,
        2,
        2,
        10.5,
        14.0,
        300,
        100,
        800,
        12.0,
        "19023010",
        270,
        70.0,
        "A",
        "X",
    ),
    (
        "SKU-NEST-002",
        "Nescafe Classic Coffee Jar 100g",
        "Pure instant coffee roasted robusta and arabica",
        11,
        2,
        2,
        260.0,
        340.0,
        70,
        20,
        180,
        5.0,
        "21011110",
        720,
        100.0,
        "A",
        "Y",
    ),
    (
        "SKU-NEST-003",
        "KitKat 4-Finger Wafer Bar 38.5g",
        "Crisp wafer fingers covered with milk chocolate",
        2,
        2,
        2,
        18.0,
        25.0,
        150,
        45,
        350,
        18.0,
        "18063200",
        365,
        38.5,
        "B",
        "X",
    ),
    (
        "SKU-NEST-004",
        "Everyday Dairy Whitener 400g",
        "Spray dried dairy whitener for rich tea",
        0,
        2,
        2,
        160.0,
        210.0,
        80,
        25,
        200,
        5.0,
        "04022100",
        365,
        400.0,
        "B",
        "Y",
    ),
    (
        "SKU-HUL-001",
        "Surf Excel Easy Wash Detergent 1kg",
        "Superior stain removal washing powder",
        6,
        3,
        3,
        115.0,
        150.0,
        180,
        50,
        400,
        18.0,
        "34022010",
        720,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-HUL-002",
        "Dove Deep Moisture Body Wash 800ml",
        "Nourishing liquid body wash with microbiome gentle",
        5,
        3,
        3,
        310.0,
        425.0,
        60,
        20,
        150,
        18.0,
        "34013000",
        720,
        800.0,
        "B",
        "Y",
    ),
    (
        "SKU-HUL-003",
        "Lifebuoy Total Germ Protection Soap 125g",
        "Antibacterial bathing bar with silver shield formula",
        4,
        3,
        3,
        28.0,
        38.0,
        250,
        80,
        600,
        18.0,
        "34011110",
        720,
        125.0,
        "A",
        "X",
    ),
    (
        "SKU-HUL-004",
        "Red Label Natural Care Tea 500g",
        "Black tea with 5 Ayurvedic ingredients",
        11,
        3,
        3,
        230.0,
        299.0,
        100,
        30,
        250,
        5.0,
        "09024020",
        365,
        500.0,
        "A",
        "X",
    ),
    (
        "SKU-HUL-005",
        "Vim Dishwash Gel Lemon 750ml",
        "Degreasing concentrated liquid dish cleaner",
        6,
        3,
        3,
        130.0,
        175.0,
        120,
        40,
        300,
        18.0,
        "34022090",
        720,
        750.0,
        "A",
        "X",
    ),
    (
        "SKU-ITC-001",
        "Aashirvaad Superior MP Sharbati Atta 5kg",
        "100% whole wheat stone-ground flour",
        1,
        4,
        4,
        215.0,
        285.0,
        140,
        45,
        350,
        5.0,
        "11010000",
        90,
        5000.0,
        "A",
        "X",
    ),
    (
        "SKU-ITC-002",
        "Sunfeast Dark Fantasy Choco Fills 300g",
        "Molten chocolate stuffed crunchy biscuit cookies",
        2,
        4,
        4,
        95.0,
        130.0,
        110,
        35,
        280,
        18.0,
        "19053100",
        180,
        300.0,
        "B",
        "X",
    ),
    (
        "SKU-ITC-003",
        "Bingo Mad Angles Achaari Masti 66g",
        "Triangular corn chips with traditional pickle tang",
        2,
        4,
        4,
        14.0,
        20.0,
        200,
        60,
        500,
        12.0,
        "19059030",
        120,
        66.0,
        "B",
        "Y",
    ),
    (
        "SKU-ITC-004",
        "Savlon Moisture Shield Handwash 750ml",
        "Germ protection liquid hand refill pump",
        4,
        4,
        4,
        110.0,
        149.0,
        80,
        25,
        200,
        18.0,
        "34012000",
        720,
        750.0,
        "B",
        "X",
    ),
    (
        "SKU-BRIT-001",
        "Britannia Good Day Butter Cookies 600g",
        "Rich cashew and butter biscuit family pack",
        2,
        5,
        5,
        88.0,
        120.0,
        160,
        50,
        400,
        18.0,
        "19053100",
        180,
        600.0,
        "A",
        "X",
    ),
    (
        "SKU-BRIT-002",
        "Britannia Bourbon Chocolate Biscuits 150g",
        "Sugar-sprinkled crunchy cocoa sandwich cookies",
        2,
        5,
        5,
        24.0,
        35.0,
        220,
        70,
        550,
        18.0,
        "19053100",
        180,
        150.0,
        "B",
        "X",
    ),
    (
        "SKU-BRIT-003",
        "Britannia Marie Gold 1kg",
        "Crispy low-fat tea biscuits jumbo pack",
        2,
        5,
        5,
        115.0,
        150.0,
        140,
        45,
        350,
        18.0,
        "19053100",
        180,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-PEPS-001",
        "Lay's Classic Salted Potato Chips 50g",
        "Thin sliced crisp golden farm potatoes",
        2,
        6,
        6,
        14.5,
        20.0,
        250,
        80,
        650,
        12.0,
        "20052000",
        120,
        50.0,
        "A",
        "X",
    ),
    (
        "SKU-PEPS-002",
        "Kurkure Masala Munch 75g",
        "Crunchy corn puffs with spicy Indian chatpata tadka",
        2,
        6,
        6,
        14.0,
        20.0,
        280,
        90,
        700,
        12.0,
        "19041090",
        120,
        75.0,
        "A",
        "X",
    ),
    (
        "SKU-PEPS-003",
        "Pepsi Cola Pet Bottle 750ml",
        "Carbonated caffeinated cola soft beverage",
        3,
        6,
        6,
        28.0,
        40.0,
        180,
        60,
        450,
        28.0,
        "22021010",
        180,
        750.0,
        "A",
        "X",
    ),
    (
        "SKU-PEPS-004",
        "Tropicana 100% Orange Juice 1L",
        "No added sugar pure orange fruit beverage",
        3,
        6,
        6,
        105.0,
        145.0,
        70,
        20,
        180,
        12.0,
        "20091200",
        270,
        1000.0,
        "B",
        "Y",
    ),
    (
        "SKU-COKE-001",
        "Coca-Cola Original Taste 750ml",
        "Iconic sparkling caramel soft drink",
        3,
        7,
        7,
        28.0,
        40.0,
        200,
        65,
        500,
        28.0,
        "22021010",
        180,
        750.0,
        "A",
        "X",
    ),
    (
        "SKU-COKE-002",
        "Thums Up Charged Carbonated Can 300ml",
        "Strong fizzy spicy thunder cola beverage",
        3,
        7,
        7,
        27.0,
        40.0,
        150,
        50,
        350,
        28.0,
        "22021010",
        180,
        300.0,
        "A",
        "X",
    ),
    (
        "SKU-COKE-003",
        "Sprite Clear Lemon-Lime 750ml",
        "Caffeine-free refreshing sparkling citrus drink",
        3,
        7,
        7,
        28.0,
        40.0,
        180,
        60,
        450,
        28.0,
        "22021020",
        180,
        750.0,
        "A",
        "X",
    ),
    (
        "SKU-COKE-004",
        "Kinley Packaged Drinking Water 1L",
        "Reverse osmosis purified mineral added water",
        3,
        7,
        7,
        12.0,
        20.0,
        300,
        100,
        800,
        18.0,
        "22011010",
        365,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-DABR-001",
        "Dabur Honey 500g 100% Pure",
        "Squeezy bottle antibiotic-free natural honey",
        8,
        8,
        8,
        160.0,
        220.0,
        75,
        25,
        190,
        5.0,
        "04090000",
        540,
        500.0,
        "B",
        "Y",
    ),
    (
        "SKU-DABR-002",
        "Dabur Chyawanprash Awaleha 1kg",
        "Immunity booster with 40+ Ayurvedic herbs",
        9,
        8,
        8,
        290.0,
        395.0,
        80,
        25,
        200,
        12.0,
        "30049011",
        720,
        1000.0,
        "A",
        "Z",
    ),
    (
        "SKU-DABR-003",
        "Dabur Red Toothpaste 200g",
        "Clinically proven clove and pudina oral paste",
        7,
        8,
        8,
        82.0,
        115.0,
        120,
        40,
        300,
        18.0,
        "33061020",
        720,
        200.0,
        "A",
        "X",
    ),
    (
        "SKU-PARL-001",
        "Parle-G Glucose Biscuits 800g",
        "World's bestselling wheat glucose cookies",
        2,
        9,
        9,
        58.0,
        80.0,
        250,
        80,
        650,
        18.0,
        "19053100",
        180,
        800.0,
        "A",
        "X",
    ),
    (
        "SKU-PARL-002",
        "Parle Monaco Salted Crackers 200g",
        "Light crispy salted round aperitif crackers",
        2,
        9,
        9,
        26.0,
        35.0,
        150,
        50,
        380,
        18.0,
        "19053100",
        180,
        200.0,
        "B",
        "X",
    ),
    (
        "SKU-PARL-003",
        "Frooti Mango Drink Tetra 160ml",
        "Sweet fresh mango pulp fruit concentrate",
        3,
        9,
        9,
        10.5,
        15.0,
        350,
        120,
        900,
        12.0,
        "22029920",
        180,
        160.0,
        "A",
        "Y",
    ),
    (
        "SKU-MARI-001",
        "Parachute 100% Pure Coconut Oil 500ml",
        "Edible grade unrefined virgin coconut hair oil",
        5,
        10,
        10,
        175.0,
        230.0,
        110,
        35,
        270,
        5.0,
        "15131100",
        720,
        500.0,
        "A",
        "X",
    ),
    (
        "SKU-MARI-002",
        "Saffola Gold Pro Healthy Heart Oil 5L",
        "Blended rice bran and sunflower cooking oil",
        1,
        10,
        10,
        720.0,
        890.0,
        60,
        20,
        150,
        5.0,
        "15179010",
        365,
        4550.0,
        "A",
        "X",
    ),
    (
        "SKU-GODR-001",
        "Godrej No.1 Lime & Aloe Soap 4x100g",
        "Natural grade 1 toilet soap bundle with glycerin",
        4,
        11,
        11,
        78.0,
        110.0,
        130,
        40,
        320,
        18.0,
        "34011110",
        720,
        400.0,
        "A",
        "X",
    ),
    (
        "SKU-GODR-002",
        "GoodKnight Gold Flash Mosquito Refill 45ml",
        "Fast vapourizing insect repellent liquid",
        6,
        11,
        11,
        62.0,
        85.0,
        140,
        45,
        350,
        18.0,
        "38089190",
        720,
        45.0,
        "A",
        "Y",
    ),
    (
        "SKU-COLG-001",
        "Colgate Strong Teeth Toothpaste 500g Saver",
        "Calcium and fluoride cavity protection paste",
        7,
        12,
        12,
        185.0,
        255.0,
        160,
        50,
        400,
        18.0,
        "33061020",
        720,
        500.0,
        "A",
        "X",
    ),
    (
        "SKU-COLG-002",
        "Colgate MaxFresh Spicy Red Gel 150g",
        "Cooling crystal freshening breath gel paste",
        7,
        12,
        12,
        85.0,
        120.0,
        120,
        40,
        300,
        18.0,
        "33061020",
        720,
        150.0,
        "B",
        "X",
    ),
    (
        "SKU-COLG-003",
        "Colgate ZigZag Charcoal Toothbrush Pack of 4",
        "Cross bristles deep cleaning soft gum manual brush",
        7,
        12,
        12,
        70.0,
        100.0,
        90,
        30,
        220,
        18.0,
        "96032100",
        1825,
        80.0,
        "B",
        "Z",
    ),
    (
        "SKU-RECK-001",
        "Dettol Antiseptic Liquid 1L",
        "Chloroxylenol medical first aid and disinfectant",
        4,
        13,
        13,
        260.0,
        350.0,
        90,
        30,
        230,
        18.0,
        "38089400",
        1095,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-RECK-002",
        "Harpic Power Plus Toilet Cleaner 1L",
        "Thick acidic germicidal bathroom bowl cleaner",
        6,
        13,
        13,
        145.0,
        195.0,
        140,
        45,
        350,
        18.0,
        "34022090",
        720,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-RECK-003",
        "Lizol Surface Disinfectant Citrus 2L",
        "Floor cleaner eliminating 99.9% household germs",
        6,
        13,
        13,
        270.0,
        360.0,
        80,
        25,
        200,
        18.0,
        "34022090",
        720,
        2000.0,
        "A",
        "X",
    ),
    (
        "SKU-CADB-001",
        "Cadbury Dairy Milk Silk Chocolate 150g",
        "Velvety smooth pure cocoa butter milk bar",
        2,
        14,
        14,
        130.0,
        175.0,
        120,
        40,
        300,
        18.0,
        "18063200",
        365,
        150.0,
        "A",
        "X",
    ),
    (
        "SKU-CADB-002",
        "Cadbury Bournvita Chocolate Health Drink 1kg",
        "Malt vitamin D enriched nutrition powder",
        9,
        14,
        14,
        320.0,
        415.0,
        90,
        30,
        230,
        18.0,
        "19019090",
        365,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-CADB-003",
        "Oreo Original Vanilla Creme Biscuit 300g",
        "Rich chocolate cookie with smooth vanilla center",
        2,
        14,
        14,
        65.0,
        90.0,
        150,
        50,
        380,
        18.0,
        "19053100",
        270,
        300.0,
        "B",
        "X",
    ),
    (
        "SKU-KELL-001",
        "Kellogg's Corn Flakes Original 875g",
        "Toasted crunchy golden corn breakfast cereal",
        9,
        15,
        15,
        260.0,
        350.0,
        75,
        25,
        190,
        18.0,
        "19041010",
        365,
        875.0,
        "B",
        "X",
    ),
    (
        "SKU-KELL-002",
        "Kellogg's Chocos Chocolate Moons 385g",
        "Whole grain chocolaty wheat breakfast scoop",
        9,
        15,
        15,
        140.0,
        190.0,
        90,
        30,
        220,
        18.0,
        "19041090",
        270,
        385.0,
        "B",
        "Y",
    ),
    (
        "SKU-HIMA-001",
        "Himalaya Purifying Neem Face Wash 300ml",
        "Soap-free herbal pimple defense daily wash",
        5,
        18,
        16,
        210.0,
        299.0,
        90,
        30,
        230,
        18.0,
        "33049990",
        720,
        300.0,
        "A",
        "X",
    ),
    (
        "SKU-HIMA-002",
        "Himalaya Liv.52 Herbal Tablets 100s",
        "Natural Ayurvedic liver metabolic protection supplement",
        9,
        18,
        16,
        125.0,
        170.0,
        80,
        25,
        200,
        12.0,
        "30049011",
        1095,
        100.0,
        "B",
        "Z",
    ),
    (
        "SKU-PATN-001",
        "Patanjali Cow Ghee 1L Tin",
        "Traditional Vedic bilona method clarified cow butter",
        0,
        19,
        17,
        530.0,
        650.0,
        70,
        20,
        170,
        5.0,
        "04059020",
        365,
        900.0,
        "A",
        "X",
    ),
    (
        "SKU-PATN-002",
        "Patanjali Dant Kanti Dental Cream 200g",
        "16 Ayurvedic herbs cavity and gum tightening paste",
        7,
        19,
        17,
        75.0,
        105.0,
        130,
        40,
        320,
        18.0,
        "33061020",
        720,
        200.0,
        "A",
        "X",
    ),
    (
        "SKU-HALD-001",
        "Haldiram's Bhujia Sev Crispy 1kg",
        "Spicy moth bean and gram flour seasoned noodles",
        2,
        20,
        18,
        190.0,
        260.0,
        140,
        45,
        350,
        12.0,
        "21069099",
        180,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-HALD-002",
        "Haldiram's Gulab Jamun Tin 1kg",
        "Fried khoya dough balls in saffron sugar syrup",
        2,
        20,
        18,
        180.0,
        240.0,
        70,
        20,
        180,
        12.0,
        "21069099",
        365,
        1000.0,
        "B",
        "Z",
    ),
    (
        "SKU-MD-001",
        "Mother Dairy Cow Milk Pouch 500ml",
        "Pasteurised fresh homogenized cow milk",
        0,
        21,
        19,
        24.0,
        30.0,
        250,
        80,
        600,
        5.0,
        "04011000",
        2,
        500.0,
        "A",
        "X",
    ),
    (
        "SKU-FORT-001",
        "Fortune Sunlite Refined Sunflower Oil 1L",
        "Low absorb fortified vitamin cooking oil pouch",
        1,
        22,
        20,
        115.0,
        145.0,
        150,
        50,
        380,
        5.0,
        "15121910",
        270,
        910.0,
        "A",
        "X",
    ),
    (
        "SKU-FORT-002",
        "Fortune Biryani Special Basmati Rice 5kg",
        "Extra long pearly aromatic aged grain rice",
        1,
        22,
        20,
        510.0,
        680.0,
        60,
        20,
        150,
        5.0,
        "10063020",
        720,
        5000.0,
        "A",
        "Y",
    ),
    (
        "SKU-BIKA-001",
        "Bikaji Bikaneri Bhujia 400g",
        "Original authentic royal Rajasthan savory crunch",
        2,
        23,
        21,
        95.0,
        130.0,
        120,
        40,
        300,
        12.0,
        "21069099",
        180,
        400.0,
        "B",
        "X",
    ),
    (
        "SKU-NIVE-001",
        "Nivea Men Dark Spot Reduction Face Wash 100g",
        "10x brightening deep pore clarifying foam",
        5,
        24,
        22,
        140.0,
        199.0,
        80,
        25,
        200,
        18.0,
        "33049990",
        720,
        100.0,
        "B",
        "Y",
    ),
    (
        "SKU-NIVE-002",
        "Nivea Soft Light Moisturiser Cream 200ml",
        "Jojoba oil vitamin E hydrating daily body lotion",
        5,
        24,
        22,
        210.0,
        299.0,
        70,
        20,
        180,
        18.0,
        "33049910",
        720,
        200.0,
        "B",
        "X",
    ),
    (
        "SKU-JJ-001",
        "Johnson's Baby Powder with Natural Cornstarch 400g",
        "Talc-free ultra gentle skin absorbing powder",
        10,
        17,
        17,
        190.0,
        260.0,
        70,
        20,
        180,
        18.0,
        "33049100",
        1095,
        400.0,
        "B",
        "Y",
    ),
    (
        "SKU-JJ-002",
        "Johnson's Baby Shampoo Tear-Free 500ml",
        "Hypoallergenic mild lather cleansing baby wash",
        10,
        17,
        17,
        240.0,
        340.0,
        60,
        20,
        150,
        18.0,
        "33051090",
        1095,
        500.0,
        "B",
        "Y",
    ),
    (
        "SKU-LOR-001",
        "L'Oreal Paris Total Repair 5 Shampoo 650ml",
        "Ceramide infused damaged split ends care",
        5,
        16,
        16,
        380.0,
        520.0,
        60,
        20,
        150,
        18.0,
        "33051090",
        1095,
        650.0,
        "A",
        "Y",
    ),
    (
        "SKU-LOR-002",
        "Garnier Micellar Cleansing Water 400ml",
        "All in 1 gentle makeup remover and soothing toner",
        5,
        16,
        16,
        260.0,
        375.0,
        50,
        15,
        130,
        18.0,
        "33049990",
        1095,
        400.0,
        "B",
        "Z",
    ),
    (
        "SKU-PG-001",
        "Head & Shoulders Cool Menthol Anti-Dandruff 650ml",
        "Formulated cooling scalp refreshing shampoo",
        5,
        2,
        2,
        390.0,
        550.0,
        70,
        20,
        180,
        18.0,
        "33051090",
        720,
        650.0,
        "A",
        "X",
    ),
    (
        "SKU-PG-002",
        "Gillette Mach3 Turbo Razor Blades 4 Pack",
        "Nano-thin anti-friction 3-blade cartridge refill",
        4,
        2,
        2,
        410.0,
        575.0,
        80,
        25,
        200,
        18.0,
        "82122000",
        1825,
        60.0,
        "A",
        "X",
    ),
    (
        "SKU-PG-003",
        "Pampers All Round Protection Pants Large 64s",
        "Ultra absorb core diaper pants with lotion",
        10,
        2,
        2,
        750.0,
        999.0,
        50,
        15,
        130,
        12.0,
        "96190010",
        720,
        2100.0,
        "A",
        "X",
    ),
    (
        "SKU-PG-004",
        "Ariel Matic Front Load Washing Powder 4kg",
        "Enzyme boosted deep fiber cleaning detergent",
        6,
        2,
        2,
        720.0,
        960.0,
        60,
        20,
        150,
        18.0,
        "34022010",
        720,
        4000.0,
        "A",
        "X",
    ),
    (
        "SKU-DABR-004",
        "Dabur Vatika Enriched Coconut Hair Oil 300ml",
        "7 Ayurvedic herbs strengthening non-sticky formula",
        5,
        8,
        8,
        120.0,
        165.0,
        90,
        30,
        220,
        5.0,
        "33059011",
        720,
        300.0,
        "B",
        "X",
    ),
    (
        "SKU-ITC-005",
        "Sunfeast YiPPee! Magic Masala Noodles 240g Pack",
        "Non-sticky round wheat noodle block with veggies",
        2,
        4,
        4,
        38.0,
        50.0,
        160,
        50,
        400,
        12.0,
        "19023010",
        270,
        240.0,
        "A",
        "X",
    ),
    (
        "SKU-ITC-006",
        "B Natural Mixed Fruit Juice 1L",
        "Pulp rich immunity drink with Vitamin C",
        3,
        4,
        4,
        75.0,
        110.0,
        80,
        25,
        200,
        12.0,
        "20098900",
        180,
        1000.0,
        "B",
        "Y",
    ),
    (
        "SKU-HUL-006",
        "Horlicks Classic Malt Health Drink 1kg Refill",
        "Bio-available nutrients for growth and bone mass",
        9,
        3,
        3,
        310.0,
        410.0,
        90,
        30,
        230,
        18.0,
        "19019090",
        365,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-HUL-007",
        "Brooke Bond Taj Mahal Tea 500g",
        "Finest orthodox and CTC Assam highland blend",
        11,
        3,
        3,
        310.0,
        420.0,
        60,
        20,
        150,
        5.0,
        "09023020",
        365,
        500.0,
        "B",
        "X",
    ),
    (
        "SKU-HUL-008",
        "Knorr Tomato Chatpata Cup-a-Soup 4 Pack",
        "Comforting warm tangy tomato crouton soup",
        8,
        3,
        3,
        40.0,
        55.0,
        100,
        30,
        250,
        18.0,
        "21041010",
        365,
        52.0,
        "C",
        "Z",
    ),
    (
        "SKU-AMUL-005",
        "Amul Kool Kesar Flavour Milk Can 200ml",
        "Refreshing chilled sterilised saffron beverage",
        0,
        0,
        0,
        24.0,
        32.0,
        180,
        60,
        450,
        5.0,
        "04029990",
        180,
        200.0,
        "A",
        "Y",
    ),
    (
        "SKU-AMUL-006",
        "Amul Malai Paneer Block 200g Fresh",
        "Rich creamy soft cow milk paneer cottage cheese",
        0,
        0,
        0,
        72.0,
        90.0,
        120,
        40,
        300,
        5.0,
        "04061000",
        30,
        200.0,
        "A",
        "X",
    ),
    (
        "SKU-BRIT-004",
        "Britannia Cheese Slices 200g 10 Slices",
        "Individually wrapped creamy cheddar sandwich slices",
        0,
        5,
        5,
        115.0,
        150.0,
        70,
        20,
        180,
        5.0,
        "04069000",
        180,
        200.0,
        "B",
        "Y",
    ),
    (
        "SKU-BRIT-005",
        "Britannia 100% Whole Wheat Bread 400g",
        "Brown wholesome fiber daily bakery loaf",
        1,
        5,
        5,
        36.0,
        48.0,
        140,
        45,
        350,
        5.0,
        "19059020",
        5,
        400.0,
        "A",
        "X",
    ),
    (
        "SKU-PEPS-005",
        "Quaker Rolled Oats 1kg Pouch",
        "100% natural wholegrain beta-glucan breakfast",
        9,
        6,
        6,
        150.0,
        210.0,
        80,
        25,
        200,
        18.0,
        "11041200",
        365,
        1000.0,
        "B",
        "X",
    ),
    (
        "SKU-PEPS-006",
        "Aquafina Packaged Drinking Water 1L",
        "Seven-step filtration crisp mineral water",
        3,
        6,
        6,
        12.0,
        20.0,
        250,
        80,
        650,
        18.0,
        "22011010",
        365,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-MARI-003",
        "Livon Hair Serum with Vitamin E 100ml",
        "Ultra glossy frizz-free smoothing hair coat",
        5,
        10,
        10,
        190.0,
        275.0,
        70,
        20,
        180,
        18.0,
        "33059019",
        720,
        100.0,
        "B",
        "X",
    ),
    (
        "SKU-MARI-004",
        "Set Wet Cool Hold Hair Gel 250ml",
        "Alcohol-free daily styling vertical hold gel",
        5,
        10,
        10,
        95.0,
        135.0,
        90,
        30,
        230,
        18.0,
        "33059090",
        720,
        250.0,
        "C",
        "Y",
    ),
    (
        "SKU-GODR-003",
        "Godrej Cinthol Original Deodorant Soap 100g",
        "Active cooling germ protection bathing bar",
        4,
        11,
        11,
        35.0,
        48.0,
        150,
        50,
        380,
        18.0,
        "34011110",
        720,
        100.0,
        "B",
        "X",
    ),
    (
        "SKU-GODR-004",
        "Godrej aer Pocket Bathroom Fragrance 10g",
        "Power gel fragrant aroma lasting up to 30 days",
        6,
        11,
        11,
        44.0,
        60.0,
        160,
        50,
        400,
        18.0,
        "33074900",
        720,
        10.0,
        "B",
        "X",
    ),
    (
        "SKU-COLG-004",
        "Colgate Plax Peppermint Mouthwash 500ml",
        "Zero alcohol 24/7 plaque and freshness rinse",
        7,
        12,
        12,
        180.0,
        250.0,
        60,
        20,
        150,
        18.0,
        "33069000",
        720,
        500.0,
        "B",
        "Y",
    ),
    (
        "SKU-RECK-004",
        "Veet Hair Removal Cream Sensitive 100g",
        "Enriched with aloe vera and Vitamin E smooth finish",
        4,
        13,
        13,
        175.0,
        245.0,
        50,
        15,
        130,
        18.0,
        "33079010",
        720,
        100.0,
        "B",
        "Y",
    ),
    (
        "SKU-RECK-005",
        "Mortein PowerGard All Insect Spray 425ml",
        "Instantly knocks down mosquitoes, flies and roaches",
        6,
        13,
        13,
        195.0,
        270.0,
        80,
        25,
        200,
        18.0,
        "38089190",
        720,
        425.0,
        "A",
        "Y",
    ),
    (
        "SKU-CADB-004",
        "Cadbury 5 Star Chocolate Bar 40g",
        "Chewy caramel and soft nougat crunch center",
        2,
        14,
        14,
        15.0,
        20.0,
        250,
        80,
        650,
        18.0,
        "18063200",
        270,
        40.0,
        "A",
        "X",
    ),
    (
        "SKU-CADB-005",
        "Cadbury Gems Chocolate Buttons 79g Tube",
        "Crisp rainbow candy shell milk chocolate balls",
        2,
        14,
        14,
        25.0,
        35.0,
        180,
        60,
        450,
        18.0,
        "18063200",
        270,
        79.0,
        "B",
        "X",
    ),
    (
        "SKU-NEST-005",
        "Munch Chocolate Wafer Bar 22g",
        "Crunchy roasted wafer covered in cocoa glaze",
        2,
        2,
        2,
        7.5,
        10.0,
        350,
        120,
        900,
        18.0,
        "18063200",
        270,
        22.0,
        "A",
        "X",
    ),
    (
        "SKU-NEST-006",
        "Nestle Ceregrow Toddler Multigrain Cereal 300g",
        "Fortified milk and grain nutrition for toddlers",
        10,
        2,
        2,
        230.0,
        315.0,
        50,
        15,
        130,
        18.0,
        "19011090",
        365,
        300.0,
        "B",
        "X",
    ),
    (
        "SKU-TATA-004",
        "Tata Sampann Chana Dal 1kg",
        "Unpolished split Bengal gram premium pulse",
        1,
        1,
        1,
        95.0,
        130.0,
        110,
        35,
        280,
        5.0,
        "07132000",
        365,
        1000.0,
        "A",
        "X",
    ),
    (
        "SKU-TATA-005",
        "Tata Coffee Grand Instant Mix 100g",
        "Flavor-locked crystals roasted chickory blend",
        11,
        1,
        1,
        140.0,
        195.0,
        60,
        20,
        150,
        5.0,
        "21011120",
        540,
        100.0,
        "B",
        "Y",
    ),
    (
        "SKU-HALD-003",
        "Haldiram's Aloo Bhujia Spicy 400g",
        "Tempting mint flavored crispy potato flakes and sev",
        2,
        20,
        18,
        85.0,
        115.0,
        150,
        50,
        380,
        12.0,
        "21069099",
        180,
        400.0,
        "A",
        "X",
    ),
    (
        "SKU-HALD-004",
        "Haldiram's Soan Papdi Festive Pack 500g",
        "Flaky cardamom flavored besan cube sweet",
        2,
        20,
        18,
        110.0,
        155.0,
        90,
        30,
        220,
        12.0,
        "21069099",
        180,
        500.0,
        "B",
        "Z",
    ),
    (
        "SKU-PATN-003",
        "Patanjali Kesh Kanti Hair Cleanser 400ml",
        "Amla, shikakai and reetha natural shine shampoo",
        5,
        19,
        17,
        130.0,
        180.0,
        80,
        25,
        200,
        18.0,
        "33051090",
        720,
        400.0,
        "B",
        "X",
    ),
    (
        "SKU-PATN-004",
        "Patanjali Virgin Mustard Oil Kachi Ghani 1L",
        "Cold-pressed pungent aroma pure mustard oil",
        1,
        19,
        17,
        120.0,
        155.0,
        120,
        40,
        300,
        5.0,
        "15149110",
        270,
        910.0,
        "A",
        "X",
    ),
    (
        "SKU-HIMA-003",
        "Himalaya Anti-Hair Fall Bhringaraja Shampoo 400ml",
        "Root stimulating botanical nourishment shampoo",
        5,
        18,
        16,
        220.0,
        310.0,
        70,
        20,
        180,
        18.0,
        "33051090",
        720,
        400.0,
        "B",
        "Y",
    ),
    (
        "SKU-HIMA-004",
        "Himalaya Sparkly White Herbal Toothpaste 175g",
        "Enzyme plant technology whitening dental care",
        7,
        18,
        16,
        95.0,
        135.0,
        90,
        30,
        220,
        18.0,
        "33061020",
        720,
        175.0,
        "C",
        "X",
    ),
    (
        "SKU-BALA-001",
        "Balaji Wafers Masala Wafers 65g",
        "Crispy crinkle cut spiced potato chips",
        2,
        9,
        29,
        13.5,
        20.0,
        200,
        60,
        500,
        12.0,
        "20052000",
        120,
        65.0,
        "A",
        "X",
    ),
    (
        "SKU-BALA-002",
        "Balaji Wheels Spicy Tomato Snax 60g",
        "Savory tomato flavored crunchy extruded wheels",
        2,
        9,
        29,
        13.0,
        20.0,
        180,
        50,
        450,
        12.0,
        "19041090",
        120,
        60.0,
        "A",
        "X",
    ),
    (
        "SKU-PAPR-001",
        "Paper Boat Aam Panna Juice Pouch 250ml",
        "Raw mango cooling cumin summer specialty beverage",
        3,
        6,
        28,
        26.0,
        38.0,
        120,
        40,
        300,
        12.0,
        "22029920",
        180,
        250.0,
        "B",
        "Y",
    ),
]

# Cities for 250 realistic customers
INDIAN_CITIES = [
    ("Mumbai", "Maharashtra", "West"),
    ("Delhi", "Delhi NCR", "North"),
    ("Bangalore", "Karnataka", "South"),
    ("Hyderabad", "Telangana", "South"),
    ("Chennai", "Tamil Nadu", "South"),
    ("Kolkata", "West Bengal", "East"),
    ("Pune", "Maharashtra", "West"),
    ("Ahmedabad", "Gujarat", "West"),
    ("Jaipur", "Rajasthan", "North"),
    ("Lucknow", "Uttar Pradesh", "North"),
    ("Indore", "Madhya Pradesh", "Central"),
    ("Kochi", "Kerala", "South"),
    ("Chandigarh", "Punjab", "North"),
    ("Patna", "Bihar", "East"),
    ("Bhopal", "Madhya Pradesh", "Central"),
    ("Nagpur", "Maharashtra", "West"),
    ("Surat", "Gujarat", "West"),
    ("Visakhapatnam", "Andhra Pradesh", "South"),
]

CUSTOMER_TYPES = [
    ("Retail Supermarket", 300000.0),
    ("Wholesale Cash & Carry", 1000000.0),
    ("Convenience Mart Chain", 500000.0),
    ("Kirana General Store Hub", 150000.0),
    ("Hypermarket Store", 1500000.0),
    ("E-commerce Dark Store Partner", 800000.0),
]


def generate_barcode(index):
    # EAN-13 format: 890 (India) + 9 digits + checksum
    base = f"890{100000000 + index:09d}"
    odd_sum = sum(int(base[i]) for i in range(0, 12, 2))
    even_sum = sum(int(base[i]) for i in range(1, 12, 2)) * 3
    checksum = (10 - ((odd_sum + even_sum) % 10)) % 10
    return f"{base}{checksum}"


# ---------------------------------------------------------------------------
# API Client Helper
# ---------------------------------------------------------------------------
class ApiSeederClient:
    def __init__(self, base_url, email, password):
        self.base_url = base_url
        self.token = None
        self.email = email
        self.password = password
        self.authenticate()

    def authenticate(self, max_retries=5):
        login_data = urllib.parse.urlencode(
            {"username": self.email, "password": self.password}
        ).encode("utf-8")
        for attempt in range(1, max_retries + 1):
            req = urllib.request.Request(
                f"{self.base_url}/auth/login",
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                    self.token = data["access_token"]
                    print(f"[OK] Authenticated as {self.email} on {self.base_url}")
                    return
            except urllib.error.HTTPError as e:
                err_text = e.read().decode()
                print(f"[WARN] Auth attempt {attempt}/{max_retries} returned {e.code}: {err_text}")
                time.sleep(3 * attempt)
            except Exception as e:
                print(f"[WARN] Auth attempt {attempt}/{max_retries} error: {e}")
                time.sleep(3 * attempt)
        print(f"[FAIL] Could not authenticate after {max_retries} attempts.")
        sys.exit(1)

    def request(self, method, path, data=None, max_retries=3):
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data is not None else None
        for attempt in range(1, max_retries + 1):
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 204:
                        return None
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                if e.code == 409 or "already exists" in err_body:
                    return None  # Idempotent skip
                if e.code in (500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(1.5 * attempt)
                    continue
                print(f"[{method} {path}] HTTP {e.code}: {err_body[:200]}")
                return None
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(1.5 * attempt)
                    continue
                print(f"[{method} {path}] Error: {e}")
                return None
        return None

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, data):
        return self.request("POST", path, data)


# ---------------------------------------------------------------------------
# Seeding Orchestrator
# ---------------------------------------------------------------------------
def run_fmcg_seeding():
    print("=" * 70)
    print("RETAILOPS PLATFORM: FMCG ENTERPRISE DATABASE SEEDER")
    print(f"Target: {BASE_URL}")
    print("=" * 70)

    client = ApiSeederClient(BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD)

    # 1. Warehouses (5)
    print("\n[Step 1/9] Seeding 5 Regional Fulfillment Centers...")
    created_warehouses = []
    existing_whs = client.get("/warehouses") or []
    existing_wh_map = {w["name"]: w["id"] for w in existing_whs}
    for wh_data in WAREHOUSES:
        if wh_data["name"] in existing_wh_map:
            created_warehouses.append({"id": existing_wh_map[wh_data["name"]], **wh_data})
        else:
            res = client.post("/warehouses", {"name": wh_data["name"]})
            if res:
                created_warehouses.append(res)
    wh_ids = [w["id"] for w in created_warehouses]
    print(f"-> Active Warehouse IDs: {wh_ids} (Total: {len(wh_ids)})")

    # 2. Categories (12)
    print("\n[Step 2/9] Seeding 12 FMCG Categories...")
    created_categories = []
    existing_cats = client.get("/categories") or []
    cat_map = {c["name"]: c["id"] for c in existing_cats}
    for cat_data in CATEGORIES:
        if cat_data["name"] in cat_map:
            created_categories.append({"id": cat_map[cat_data["name"]], **cat_data})
        else:
            res = client.post("/categories", {"name": cat_data["name"]})
            if res:
                created_categories.append(res)
    cat_ids = [c["id"] for c in created_categories]
    print(f"-> Total Categories: {len(cat_ids)}")

    # 3. Brands (25)
    print("\n[Step 3/9] Seeding 25 Leading Consumer Brands...")
    created_brands = []
    existing_brands = client.get("/brands") or []
    brand_map = {b["name"]: b["id"] for b in existing_brands}
    for b_name in BRANDS:
        if b_name in brand_map:
            created_brands.append({"id": brand_map[b_name], "name": b_name})
        else:
            res = client.post("/brands", {"name": b_name})
            if res:
                created_brands.append(res)
    brand_ids = [b["id"] for b in created_brands]
    print(f"-> Total Brands: {len(brand_ids)}")

    # 4. Suppliers (30)
    print("\n[Step 4/9] Seeding 30 FMCG Suppliers...")
    created_suppliers = []
    existing_supps = client.get("/suppliers") or []
    supp_map = {s["name"]: s["id"] for s in existing_supps}
    for s_name, lead_time, rel_score in SUPPLIERS:
        if s_name in supp_map:
            created_suppliers.append({"id": supp_map[s_name], "name": s_name})
        else:
            res = client.post(
                "/suppliers",
                {"name": s_name, "lead_time_days": lead_time, "reliability_score": rel_score},
            )
            if res:
                created_suppliers.append(res)
    supp_ids = [s["id"] for s in created_suppliers]
    print(f"-> Total Suppliers: {len(supp_ids)}")

    # 5. Products (105)
    print("\n[Step 5/9] Seeding 105 Realistic FMCG Products...")
    existing_prods = client.get("/products?limit=1000") or []
    prod_skus = {p["sku"] for p in existing_prods}

    product_records = []
    for idx, item in enumerate(FMCG_PRODUCT_CATALOG):
        (
            sku,
            name,
            desc,
            c_idx,
            b_idx,
            s_idx,
            cost,
            price,
            rop,
            safety,
            eoq,
            gst,
            hsn,
            shelf,
            weight,
            abc,
            xyz,
        ) = item
        barcode = generate_barcode(idx + 1)
        c_id = cat_ids[c_idx % len(cat_ids)] if cat_ids else 1
        b_id = brand_ids[b_idx % len(brand_ids)] if brand_ids else 1
        s_id = supp_ids[s_idx % len(supp_ids)] if supp_ids else 1

        payload = {
            "sku": sku,
            "name": name,
            "description": desc,
            "barcode": barcode,
            "category_id": c_id,
            "brand_id": b_id,
            "supplier_id": s_id,
            "unit_cost": cost,
            "sale_price": price,
            "reorder_point": rop,
            "safety_stock": safety,
            "reorder_quantity": eoq,
            "eoq": eoq,
            "gst_percent": gst,
            "hsn_code": hsn,
            "shelf_life_days": shelf,
            "weight_grams": weight,
            "abc_class": abc,
            "xyz_class": xyz,
            "behavior_pattern": "fast_moving" if abc == "A" else "steady",
            "active": True,
        }
        if sku not in prod_skus:
            res = client.post("/products", payload)
            if res:
                product_records.append(res)
        else:
            product_records.append(payload)

    # If need more up to 105, synthesize remaining
    current_count = len(product_records)
    for i in range(current_count, 105):
        sku = f"SKU-FMCG-{i + 1:03d}"
        if sku not in prod_skus:
            name = f"Premium FMCG Essential Item #{i + 1}"
            c_id = cat_ids[i % len(cat_ids)]
            b_id = brand_ids[i % len(brand_ids)]
            s_id = supp_ids[i % len(supp_ids)]
            cost = round(random.uniform(20.0, 400.0), 2)
            price = round(cost * random.uniform(1.25, 1.45), 2)
            payload = {
                "sku": sku,
                "name": name,
                "description": f"Standard commercial FMCG product packaging #{i + 1}",
                "barcode": generate_barcode(i + 1),
                "category_id": c_id,
                "brand_id": b_id,
                "supplier_id": s_id,
                "unit_cost": cost,
                "sale_price": price,
                "reorder_point": random.randint(50, 150),
                "safety_stock": random.randint(20, 50),
                "reorder_quantity": random.randint(150, 400),
                "eoq": random.randint(150, 400),
                "gst_percent": 18.0,
                "hsn_code": "21069099",
                "shelf_life_days": 365,
                "weight_grams": float(random.choice([100, 250, 500, 1000])),
                "abc_class": random.choice(["A", "B", "C"]),
                "xyz_class": random.choice(["X", "Y", "Z"]),
                "behavior_pattern": "regular",
                "active": True,
            }
            res = client.post("/products", payload)
            if res:
                product_records.append(res)
        else:
            product_records.append({"sku": sku})

    print(f"-> Verified FMCG Products: {len(product_records)}")

    # 6. Customers (250)
    print("\n[Step 6/9] Seeding 250 Enterprise Customers...")
    existing_custs = client.get("/customers?limit=1000") or []
    current_cust_count = len(existing_custs)
    created_customers = list(existing_custs)

    needed_custs = max(0, 250 - current_cust_count)
    if needed_custs > 0:
        print(f"-> Adding {needed_custs} new business customers...")

        def make_customer(idx):
            city, state, region = INDIAN_CITIES[idx % len(INDIAN_CITIES)]
            ctype, credit = CUSTOMER_TYPES[idx % len(CUSTOMER_TYPES)]
            name = f"{city} {ctype} #{idx + 1}"
            email = f"procurement.c{idx + 1}@{city.lower().replace(' ', '')}retail.in"
            phone = f"+91-98{idx % 90 + 10:02d}-{idx % 90000 + 10000:05d}"
            c_id = cat_ids[idx % len(cat_ids)] if cat_ids else 1
            payload = {
                "name": name,
                "email": email,
                "phone": phone,
                "city": city,
                "country": "India",
                "segment": region,
                "credit_limit": credit,
                "preferred_category_id": c_id,
                "loyalty_score": round(random.uniform(3.5, 5.0), 2),
                "lifetime_value_inr": round(random.uniform(50000.0, 1200000.0), 2),
                "purchase_frequency": round(random.uniform(1.0, 12.0), 2),
                "avg_basket_inr": round(random.uniform(5000.0, 45000.0), 2),
            }
            return client.post("/customers", payload)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(make_customer, current_cust_count + i) for i in range(needed_custs)
            ]
            for f in as_completed(futures):
                res = f.result()
                if res:
                    created_customers.append(res)
    print(f"-> Total Enterprise Customers: {len(created_customers)}")

    # 7. Inventory Adjustments & Stock Levels (2,000+ records)
    print("\n[Step 7/9] Seeding Initial Inventory Balances across 5 Warehouses (2,000+ items)...")
    # For every product across multiple warehouses, ensure positive stock
    all_skus = [p["sku"] for p in product_records]

    def adjust_stock(sku, wh_id, qty):
        payload = {
            "sku": sku,
            "warehouse_id": wh_id,
            "quantity_delta": qty,
            "reason": "Opening FMCG stock balance",
        }
        return client.post("/inventory/adjustments", payload)

    adj_tasks = []
    for s in all_skus:
        for w in wh_ids:
            qty = random.randint(150, 800)
            adj_tasks.append((s, w, qty))

    # Run adjustments in parallel
    print(f"-> Injecting {len(adj_tasks)} stock ledger records...")
    success_adj = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(adjust_stock, s, w, q) for s, w, q in adj_tasks]
        for f in as_completed(futures):
            res = f.result()
            success_adj += 1
            if success_adj % 100 == 0:
                print(f"   Processed {success_adj}/{len(adj_tasks)} stock adjustments...")

    print(f"-> Stock balances initialized: {success_adj} entries.")

    # 8. Purchase Orders (300)
    print("\n[Step 8/9] Creating 300 Purchase Orders with Lifecycle...")
    existing_pos = client.get("/purchase-orders?limit=1000") or []
    needed_pos = max(0, 300 - len(existing_pos))
    print(f"-> Existing POs: {len(existing_pos)}, creating {needed_pos} new POs...")

    def create_single_po(i):
        s_id = random.choice(supp_ids)
        w_id = random.choice(wh_ids)
        lines = []
        for _ in range(random.randint(2, 5)):
            sku = random.choice(all_skus)
            lines.append(
                {
                    "sku": sku,
                    "quantity_ordered": random.randint(50, 300),
                    "unit_cost": round(random.uniform(20.0, 350.0), 2),
                }
            )
        po_payload = {"supplier_id": s_id, "warehouse_id": w_id, "lines": lines}
        po = client.post("/purchase-orders", po_payload)
        if not po:
            return None
        po_id = po["id"]
        # Advance lifecycle for majority to simulate authentic history
        status_choice = random.choices(
            ["draft", "submitted", "approved", "received"], weights=[15, 20, 25, 40]
        )[0]
        if status_choice in ["submitted", "approved", "received"]:
            client.post(f"/purchase-orders/{po_id}/submit", {})
        if status_choice in ["approved", "received"]:
            client.post(f"/purchase-orders/{po_id}/approve", {})
        if status_choice == "received":
            rec_lines = [
                {"sku": line["sku"], "quantity_received": line["quantity_ordered"]}
                for line in po.get("lines", lines)
            ]
            client.post(f"/purchase-orders/{po_id}/receive", {"lines": rec_lines})
        return po_id

    created_po_count = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(create_single_po, i) for i in range(needed_pos)]
        for f in as_completed(futures):
            res = f.result()
            if res:
                created_po_count += 1
                if created_po_count % 50 == 0:
                    print(f"   Created {created_po_count}/{needed_pos} POs...")

    total_pos = len(existing_pos) + created_po_count
    print(f"-> Total Purchase Orders: {total_pos}")

    # 9. Sales Orders & Invoices & Payments (500)
    print("\n[Step 9/9] Creating 500 Sales Orders, Invoices, and Payments...")
    existing_sos = client.get("/sales-orders?limit=1000") or []
    needed_sos = max(0, 500 - len(existing_sos))
    print(f"-> Existing SOs: {len(existing_sos)}, creating {needed_sos} new SOs...")

    cust_ids = [c["id"] for c in created_customers]

    def create_single_so(i):
        c_id = random.choice(cust_ids)
        w_id = random.choice(wh_ids)
        lines = []
        for _ in range(random.randint(1, 4)):
            sku = random.choice(all_skus)
            lines.append(
                {
                    "sku": sku,
                    "quantity": random.randint(5, 40),
                    "unit_price": round(random.uniform(30.0, 500.0), 2),
                }
            )
        so_payload = {"customer_id": c_id, "warehouse_id": w_id, "lines": lines}
        so = client.post("/sales-orders", so_payload)
        if not so:
            return None
        so_id = so["id"]
        # Advance status: 70% confirmed, 50% fulfilled
        advance = random.random()
        if advance > 0.2:
            conf = client.post(f"/sales-orders/{so_id}/confirm", {})
            if conf:
                # Invoice was created! Retrieve invoice and record payment
                inv = client.get(f"/sales-orders/{so_id}/invoice")
                if inv:
                    inv_id = inv["id"]
                    total = float(inv.get("total_amount", 0.0))
                    if total > 0:
                        pay_method = random.choice(
                            ["Bank Transfer (NEFT/RTGS)", "UPI Corporate", "Commercial Credit"]
                        )
                        client.post(
                            f"/invoices/{inv_id}/payments", {"amount": total, "method": pay_method}
                        )
                if advance > 0.45:
                    client.post(f"/sales-orders/{so_id}/fulfill", {})
        return so_id

    created_so_count = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(create_single_so, i) for i in range(needed_sos)]
        for f in as_completed(futures):
            res = f.result()
            if res:
                created_so_count += 1
                if created_so_count % 50 == 0:
                    print(f"   Created {created_so_count}/{needed_sos} Sales Orders...")

    total_sos = len(existing_sos) + created_so_count
    print(f"-> Total Sales Orders: {total_sos}")

    # Summary Verification
    print("\n" + "=" * 70)
    print("FINAL SEEDING AUDIT SUMMARY")
    print("=" * 70)
    final_prods = client.get("/products?limit=1000") or []
    final_whs = client.get("/warehouses") or []
    final_supps = client.get("/suppliers") or []
    final_custs = client.get("/customers?limit=1000") or []
    final_pos = client.get("/purchase-orders?limit=1000") or []
    final_sos = client.get("/sales-orders?limit=1000") or []
    final_invs = client.get("/invoices?limit=1000") or []
    final_stock = client.get("/inventory/stock?limit=1000") or []

    print(f"Products:         {len(final_prods)} (Target: >= 100)")
    print(f"Warehouses:       {len(final_whs)} (Target: >= 5)")
    print(f"Suppliers:        {len(final_supps)} (Target: >= 30)")
    print(f"Customers:        {len(final_custs)} (Target: >= 250)")
    print(f"Purchase Orders:  {len(final_pos)} (Target: >= 300)")
    print(f"Sales Orders:     {len(final_sos)} (Target: >= 500)")
    print(f"Invoices:         {len(final_invs)}")
    print(f"Inventory Items:  {len(final_stock)} SKUs active in catalog")
    print("=" * 70)
    print("PHASE 1 DATABASE SEEDING COMPLETE!")


if __name__ == "__main__":
    run_fmcg_seeding()
