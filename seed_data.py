"""
SIOM - Smart Inventory & Order Management System
Comprehensive Database Seeding Engine
Generates 300+ realistic, fully interconnected records across:
- 12 Categories
- 18 Suppliers
- 30 Customers
- 65 Products & Inventory Master Records
- 28 Purchase Orders & Line Items
- 40 Sales Orders & Line Items
- 32 Payments
- 30 Shipments
- 75+ Stock Movement Audit Logs
All foreign keys, stock balances, transaction dates (past 12 months), and financial ledgers are strictly consistent.
"""

import os
import sys
import random
from datetime import datetime, timedelta, date
from decimal import Decimal
import database as db

# Configure UTF-8 encoding for safe cross-platform terminal prints
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_seed():
    print("=" * 70)
    print("SIOM DATABASE SEEDING ENGINE")
    print("=" * 70)

    # 1. Initialize Schema & Migrations
    print("\n[Step 1/10] Initializing Schema & Core Tables...")
    success, msg = db.run_schema_sql("schema.sql")
    if not success:
        print(f"[ERROR] Error applying schema: {msg}")
        return False
    print("  [OK] Database schema verified and ready.")

    # 2. Seed Role-Based Admin Users
    print("\n[Step 2/10] Seeding Admin Accounts...")
    demo_users = [
        ("admin", "admin@siom.local", "Admin!2026Secure", "System Administrator", "Super Admin"),
        ("inv_manager", "inv@siom.local", "Inventory!2026Pass", "Rajesh Varma (Inventory Lead)", "Inventory Manager"),
        ("sales_manager", "sales@siom.local", "Sales!2026Secure", "Priya Sharma (Sales Lead)", "Sales Manager"),
    ]

    for username, email, raw_password, full_name, role in demo_users:
        existing = db.execute_one("SELECT id FROM admins WHERE username = %s", (username,))
        if not existing:
            pass_hash = db.hash_password(raw_password)
            db.execute_insert(
                """
                INSERT INTO admins (username, email, password_hash, full_name, role, status)
                VALUES (%s, %s, %s, %s, %s, 'Active')
                """,
                (username, email, pass_hash, full_name, role)
            )
            print(f"  [OK] Created {role}: username='{username}'")
        else:
            print(f"  [OK] User '{username}' exists.")

    admin_rec = db.execute_one("SELECT id FROM admins WHERE username = 'admin'")
    admin_id = admin_rec["id"] if admin_rec else 1

    # Clear previous transactional data safely to avoid duplicate key or orphaned records on re-seed
    print("\n[Step 3/10] Refreshing Data Tables for Clean Relational Seeding...")
    with db.get_db_transaction() as (cursor, conn):
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for tbl in [
            "stock_movements", "shipments", "payments",
            "sales_order_items", "sales_orders",
            "purchase_order_items", "purchase_orders",
            "inventory", "products", "suppliers", "customers", "categories", "document_sequences"
        ]:
            cursor.execute(f"TRUNCATE TABLE {tbl}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("  [OK] Clean slate established.")

    # 3. Seed 12 Categories
    print("\n[Step 4/10] Seeding Categories (12 Realistic Taxonomies)...")
    category_defs = [
        ("Computer Systems & Laptops", "COMP", "Business laptops, mini PCs, desktop workstations, and servers"),
        ("Computer Accessories", "ACC", "Keyboards, mice, webcams, mousepads, and ergonomic accessories"),
        ("Mobile & Tablet Accessories", "MOB", "Fast chargers, power banks, rugged cases, screen guards, and styluses"),
        ("Office Equipment", "OFF", "Label printers, paper shredders, barcode scanners, and laminators"),
        ("Workstation & Furniture", "FURN", "Ergonomic mesh chairs, motorized standing desks, and monitor arms"),
        ("Networking Hardware", "NET", "Managed Gigabit switches, Wi-Fi 6 routers, patch panels, and access points"),
        ("Data Storage & Memory", "STOR", "NVMe SSDs, external hard drives, DDR4/DDR5 RAM, and high-speed flash drives"),
        ("Printers & Consumables", "PRNT", "Laser printers, thermal receipt printers, toner cartridges, and thermal rolls"),
        ("Audio & Visual Equipment", "AV", "Noise-cancelling headsets, conference speakerphones, 4K monitors, and HDMI capture cards"),
        ("Cables & Adapters", "CAB", "Thunderbolt 4 cables, Cat6 Ethernet patch cords, USB-C hubs, and HDMI 2.1 leads"),
        ("Power Protection & UPS", "PWR", "Line-interactive UPS systems, surge protectors, voltage stabilizers, and power strips"),
        ("Industrial Automation", "IND", "Microcontroller developer kits, RS485 modems, relay boards, and DIN-rail sensors")
    ]

    cat_map = {}
    for name, shortcut, desc in category_defs:
        cat_id = db.execute_insert(
            "INSERT INTO categories (name, shortcut, description, is_active) VALUES (%s, %s, %s, 1)",
            (name, shortcut, desc)
        )
        cat_map[name] = cat_id
    print(f"  [OK] Seeded {len(cat_map)} categories.")

    # 4. Seed 18 Suppliers
    print("\n[Step 5/10] Seeding Suppliers (18 Verified B2B Distributors)...")
    supplier_defs = [
        ("TechWorld Distributors Pvt Ltd", "Sanjay Aggarwal", "+91-9811223344", "orders@techworldindia.com", "Plot 45, Okhla Industrial Area Phase III, New Delhi", "Authorized master distributor for PC components & peripherals"),
        ("Sri Lakshmi Electronics Hub", "K. Venkatesh", "+91-9848011223", "sales@srilakshmielectronics.in", "7-2-1813, Sanath Nagar Industrial Estate, Hyderabad, Telangana", "Primary distributor for passive components, sensors, and power supplies"),
        ("AP Digital Supplies", "M. Ramakrishna", "+91-9866554433", "contact@apdigitalsupplies.com", "D.No 40-1-56, MG Road, Labbipet, Vijayawada, Andhra Pradesh", "Office automation, barcode scanners, and thermal billing peripherals"),
        ("Prime Office Solutions Ltd", "Vikramaditya Roy", "+91-9820198765", "corporate@primeofficesolutions.in", "Godown No 14, Kanjurmarg West, Mumbai, Maharashtra", "Ergonomic seating, motorized desks, and workstation accessories"),
        ("Hyderabad IT Traders Consortium", "Syed Mansoor", "+91-9849123456", "support@hydittraders.co.in", "Shop 12-15, CTC Parklane, Secunderabad, Telangana", "High volume vendor for RAM, NVMe storage, and networking hardware"),
        ("Bangalore Micro Systems", "Arun Kumar Swamy", "+91-9880123987", "sales@bangaloremicro.com", "42/1, 27th Main, BTM Layout 1st Stage, Bangalore, Karnataka", "Specialist in embedded developer boards, Wi-Fi 6 APs, and IoT modules"),
        ("Delta Tech Solutions", "Deepak Chawla", "+91-9711889900", "dtech.orders@deltatech.net", "B-89, Sector 63, Noida, Gautam Buddha Nagar, Uttar Pradesh", "Enterprise routers, managed switches, and rack server cabinets"),
        ("Vardhman Components & Hardware", "Praveen Jain", "+91-9829012345", "vardhman.comp@gmail.com", "102, Chaura Rasta, Jaipur, Rajasthan", "Industrial cables, connectors, wire harnesses, and tools"),
        ("Infotech Distribution India", "Rahul Mehra", "+91-9830054321", "info@infotechdist.co.in", "14/2, Brabourne Road, 3rd Floor, Kolkata, West Bengal", "Printers, imaging toners, laminators, and POS supplies"),
        ("Pacific Peripheral Hub", "Anand Gokhale", "+91-9822331122", "anand@pacificperipherals.com", "F-45, MIDC Industrial Area, Bhosari, Pune, Maharashtra", "Mice, mechanical keyboards, gaming headsets, and monitor mounts"),
        ("Surya Electronics & Power", "Mahesh Naidu", "+91-9440187654", "orders@suryapower.in", "10-50-24, Siripuram Junction, Visakhapatnam, Andhra Pradesh", "Online UPS systems, heavy-duty surge protectors, and SMPS units"),
        ("Metro Hardware Distributors", "T. Balasubramanian", "+91-9444098765", "metro.hw@chennaidist.com", "88, Mount Road, Guindy, Chennai, Tamil Nadu", "Computer chassis, server racks, and cooling fans"),
        ("Sagar Infotech Wholesale", "Nilesh Patel", "+91-9724567890", "sales@sagarinfotech.co.in", "Near Gujarat College, Ellisbridge, Ahmedabad, Gujarat", "Business laptops, mini desktop systems, and docking stations"),
        ("National Telecom Spares", "Gurpreet Singh", "+91-9814056789", "gurpreet@nationaltelecom.in", "Industrial Area B, Ludhiana, Punjab", "Fiber patch cords, Cat6 bulk cable rolls, and networking tools"),
        ("Deccan Component Source", "Pooja Reddy", "+91-9849988776", "pooja@deccancomponents.org", "Plot 18, Phase 2, IDA Cherlapally, Hyderabad, Telangana", "Sensors, industrial relay boards, and DIN-rail automation gear"),
        ("OmniTech Supplies & Logistics", "Karthik Raja", "+91-9884411223", "karthik@omnitechsupplies.in", "Thiru Vi Ka Industrial Estate, Ekkatuthangal, Chennai, Tamil Nadu", "Fast chargers, GaN power adapters, and mobile accessories"),
        ("Zenith Imaging & Print Spares", "Siddharth Joshi", "+91-9825091234", "siddharth@zenithimaging.in", "Alkapuri Commercial Complex, Vadodara, Gujarat", "Laser printer drums, toner cartridges, and thermal printheads"),
        ("Pinnacle Power & Electronics", "Gaurav Malhotra", "+91-9810023456", "pinnacle.power@delhiit.com", "Nehru Place Commercial Hub, New Delhi", "Line-interactive UPS, server battery packs, and voltage stabilizers")
    ]

    supp_map = {}
    for name, cp, phone, email, addr, notes in supplier_defs:
        supp_id = db.execute_insert(
            """
            INSERT INTO suppliers (name, contact_person, phone, email, address, notes, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """,
            (name, cp, phone, email, addr, notes)
        )
        supp_map[name] = supp_id
    print(f"  [OK] Seeded {len(supp_map)} suppliers.")

    # 5. Seed 30 Customers
    print("\n[Step 6/10] Seeding Customers (30 Enterprise & Retail Clients)...")
    customer_defs = [
        ("Suresh Technologies Pvt Ltd", "Suresh R.", "+91-9845012301", "procurement@sureshtech.com", "Plot 12, Hitec City Phase 2, Madhapur, Hyderabad", "IT services client with 250+ employees"),
        ("Ananya Enterprises", "Ananya Deshmukh", "+91-9820012302", "ananya@ananyaenterprises.in", "Shop 4, Linking Road, Bandra West, Mumbai", "Retail electronics and computer shop chain"),
        ("Vijay Solutions & Systems", "Vijay Kulkarni", "+91-9822012303", "vijay@vijaysolutions.co.in", "Senapati Bapat Road, Shivajinagar, Pune", "System integrator and network infrastructure provider"),
        ("Kiran Retail Store", "Kiran Patel", "+91-9723012304", "kiran.retail@gujaratmail.com", "Relief Road, Kalupur, Ahmedabad", "Local retail hardware merchant"),
        ("Ravi Kumar Infoway", "Ravi Kumar", "+91-9848012305", "ravikumar.it@gmail.com", "D.No 5-9-22, Chapel Road, Abids, Hyderabad", "Independent software consultant & hardware contractor"),
        ("Priya Infotech Labs", "Priya Nair", "+91-9880012306", "pnair@priyainfotech.org", "Outer Ring Road, Bellandur, Bangalore", "AI/ML research lab and computing facility"),
        ("Sai Enterprise Solutions", "Sai Prasad", "+91-9866012307", "sales@saienterprises.net", "Main Road, Kothapet, Guntur, Andhra Pradesh", "Regional enterprise equipment supplier"),
        ("Venkateshwara Systems", "T. Venkatesh", "+91-9440012308", "orders@venkateshwarasystems.com", "Dwaraka Nagar 2nd Lane, Visakhapatnam", "Corporate IT reseller & workstation integrator"),
        ("TechVista Solutions", "Amit Sharma", "+91-9811012309", "finance@techvistasolutions.in", "DLF Cyber City, Tower B, Sector 25A, Gurgaon", "Fintech startup hardware procurement account"),
        ("Apex Systems Pvt Ltd", "Rajiv Khanna", "+91-9810012310", "rkhanna@apexsystems.in", "Barakhamba Road, Connaught Place, New Delhi", "Financial advisory and enterprise trading desks"),
        ("CyberTech Labs & Services", "Manoj Verma", "+91-9830012311", "manoj@cybertechlabs.co.in", "Sector V, Salt Lake Electronics Complex, Kolkata", "Cybersecurity operations and network monitoring center"),
        ("Krishna Electricals & IT", "G. Krishna", "+91-9849012312", "krishna.it@yahoo.co.in", "RP Road, Secunderabad, Telangana", "Wholesale electrical & IT peripheral reseller"),
        ("Matrix Cloud Solutions", "Divya Menon", "+91-9884012313", "procure@matrixcloud.io", "Guindy Industrial Estate, Chennai", "Cloud migration and DevOps consultancy firm"),
        ("GreenLeaf Retail Network", "Harish Shah", "+91-9825012314", "harish@greenleafretail.in", "Sayajigunj, Vadodara, Gujarat", "Chain of 6 consumer tech retail outlets"),
        ("Horizon IT Solutions", "Karan Singhania", "+91-9821012315", "karan@horizonitsol.com", "Marol Naka, Andheri East, Mumbai", "Hospitality hardware and POS maintenance contractor"),
        ("Royal Infoway Systems", "Siddharth Rao", "+91-9845012316", "siddharth@royalinfoway.com", "Residency Road, Shanthala Nagar, Bangalore", "Commercial AV, projector, and conference room integrator"),
        ("Zenith Automation Corp", "Vikram Malhotra", "+91-9845012317", "vikram@zenithauto.co.in", "Jeedimetla Industrial Area, Hyderabad", "Factory automation and robotic assembly line integrator"),
        ("Shri Balaji IT Hub", "Ramesh Joshi", "+91-9829012318", "balaji.it@rajasthanmail.com", "MI Road, Panch Batti, Jaipur, Rajasthan", "Government tender hardware contractor"),
        ("Alpha Dynamics Pvt Ltd", "Neha Kapoor", "+91-9818012319", "nkapoor@alphadynamics.in", "Sector 18, Noida, Uttar Pradesh", "Digital media agency and video editing workstations"),
        ("Pioneer Electronics Care", "G. Chandrasekhar", "+91-9445012320", "pioneer.care@chennai.net", "Purasawalkam High Road, Chennai", "IT hardware maintenance and repair service center"),
        ("Omkar Infotech Distributors", "Santosh Patil", "+91-9823012321", "santosh@omkarinfotech.com", "FC Road, Deccan Gymkhana, Pune", "Colleges and educational lab equipment vendor"),
        ("Delta Star Software", "Naveen Reddy", "+91-9849012322", "naveen@deltastar.co", "Financial District, Nanakramguda, Hyderabad", "SaaS company with 180 development laptops"),
        ("Trident Tech Traders", "B. Srinivas", "+91-9866012323", "trident.traders@gmail.com", "Governorpet, Vijayawada, Andhra Pradesh", "Commercial supplies and accessories dealer"),
        ("Modern Workspaces Co", "Sunaina Mehta", "+91-9820012324", "mehta@modernworkspaces.in", "Lower Parel Commercial Hub, Mumbai", "Co-working space provider managing 4 centers"),
        ("SmartEdge IoT Devices", "Arvind Swaminathan", "+91-9880012325", "arvind@smartedgeiot.com", "Koramangala 5th Block, Bangalore", "IoT product engineering company"),
        ("Nexus Global Logistics", "Pradeep Nair", "+91-9847012326", "logistics.it@nexusglobal.in", "Willingdon Island, Kochi, Kerala", "Port logistics and barcode scanner procurement"),
        ("Bright Future Academy", "Sister Mary Thomas", "+91-9441012327", "principal@brightfuture.edu.in", "St. John's Road, Secunderabad", "Educational institution computer labs"),
        ("Capital Financial Systems", "Rohit Agarwal", "+91-9811012328", "ragarwal@capitalfin.in", "Nehru Place, New Delhi", "Stock broking firm and financial trading terminals"),
        ("Everest Tech Hub", "Ashok Chordia", "+91-9828012329", "ashok@everesttech.org", "Sardar Patel Marg, C-Scheme, Jaipur", "Regional hardware supplier & networking installer"),
        ("Universal Digital Media", "Tanvi Sengupta", "+91-9831012330", "tanvi@universaldigital.in", "Park Street, Kolkata, West Bengal", "Animation studio and rendering hardware client")
    ]

    cust_map = {}
    for name, cp, phone, email, addr, notes in customer_defs:
        cust_id = db.execute_insert(
            """
            INSERT INTO customers (name, contact_person, phone, email, address, notes, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """,
            (name, cp, phone, email, addr, notes)
        )
        cust_map[name] = cust_id
    print(f"  [OK] Seeded {len(cust_map)} customers.")

    # 6. Seed 65 Products with realistic INR prices & initial stock levels
    print("\n[Step 7/10] Seeding Products Master & Warehouse Inventory (65 SKUs)...")
    product_defs = [
        # 1. Computer Systems & Laptops (6)
        ("SKU-COMP-001", "ThinkBook 15 Pro (Core i7 / 16GB / 512GB SSD)", "Computer Systems & Laptops", "15.6-inch FHD Antiglare, Intel Core i7 13th Gen, 16GB DDR5, 512GB NVMe SSD, Windows 11 Pro", 54000.00, 68999.00, 5, "units", 22),
        ("SKU-COMP-002", "ProDesk Mini Workstation PC (Core i5 / 16GB / 1TB SSD)", "Computer Systems & Laptops", "Ultra-compact business desktop, Intel Core i5 13500T, 16GB RAM, 1TB NVMe, Dual DisplayPort", 41000.00, 52499.00, 4, "units", 15),
        ("SKU-COMP-003", "Latitude 5440 Enterprise Laptop (Core i5 / 16GB)", "Computer Systems & Laptops", "14-inch FHD, Intel Core i5 13th Gen, 16GB RAM, 512GB SSD, Backlit KB, 3 Yr NBD Warranty", 48500.00, 61999.00, 5, "units", 18),
        ("SKU-COMP-004", "Creator Studio Tower (Ryzen 9 / 32GB / RTX 4070)", "Computer Systems & Laptops", "AMD Ryzen 9 7900X, 32GB DDR5, 1TB NVMe, RTX 4070 12GB, 850W Gold PSU", 112000.00, 142999.00, 2, "units", 6),
        ("SKU-COMP-005", "UltraSlim 14 Touch (Core i7 / 16GB / OLED)", "Computer Systems & Laptops", "14-inch 2.8K OLED 90Hz, Intel Core i7 Evo, 16GB LPDDR5, 1TB SSD, 1.2kg Magnesium Chassis", 69000.00, 87999.00, 3, "units", 9),
        ("SKU-COMP-006", "POS Touch Terminal 15.6-inch All-In-One", "Computer Systems & Laptops", "Intel Celeron J6412 Quad Core, 8GB RAM, 128GB SSD, 10-Point Capacitive Touch, MSR Reader", 22000.00, 28999.00, 4, "units", 12),

        # 2. Computer Accessories (6)
        ("SKU-ACC-001", "Ergonomic Optical Wireless Mouse 2.4GHz", "Computer Accessories", "Silent click, 1600 DPI adjustable sensor, USB nano receiver, 18-month battery life", 420.00, 699.00, 20, "pcs", 85),
        ("SKU-ACC-002", "Mechanical Gaming Keyboard RGB (Red Switches)", "Computer Accessories", "Full-sized 104 keys, hot-swappable linear red switches, detachable braided Type-C cable", 1850.00, 2799.00, 12, "pcs", 42),
        ("SKU-ACC-003", "Full HD 1080p Business Webcam with Privacy Shutter", "Computer Accessories", "1080p 60fps wide-angle lens, dual noise-reducing microphones, tripod mount thread", 1450.00, 2299.00, 15, "pcs", 38),
        ("SKU-ACC-004", "Wireless Keyboard & Mouse Combo (Spill Resistant)", "Computer Accessories", "Full size slim keyboard with multimedia keys and ambidextrous 1200 DPI optical mouse", 950.00, 1499.00, 15, "sets", 55),
        ("SKU-ACC-005", "Extended Desk Mat / Mousepad 900x400mm", "Computer Accessories", "Water-resistant micro-woven cloth surface with stitched anti-fray borders and non-slip rubber base", 320.00, 599.00, 25, "pcs", 6),  # LOW STOCK
        ("SKU-ACC-006", "Adjustable Aluminum Laptop Stand (Foldable)", "Computer Accessories", "Heavy-duty CNC machined aluminum riser, 6 adjustable height angles, silicone protective pads", 550.00, 999.00, 15, "pcs", 48),

        # 3. Mobile & Tablet Accessories (5)
        ("SKU-MOB-001", "65W GaN Dual USB-C Fast Wall Charger", "Mobile & Tablet Accessories", "Gallium Nitride tech, Dual Type-C + USB-A ports, PD 3.0 & PPS fast charging support", 1100.00, 1799.00, 20, "pcs", 62),
        ("SKU-MOB-002", "20,000mAh Power Bank 22.5W Fast Charge", "Mobile & Tablet Accessories", "Triple output ports, LED digital percentage display, flight-approved lithium-polymer battery", 1250.00, 1999.00, 15, "pcs", 35),
        ("SKU-MOB-003", "Braided USB-C to Lightning Cable 1.5M (MFi)", "Mobile & Tablet Accessories", "Apple MFi certified, 480Mbps data transfer, nylon braided jacket rated for 20,000 bends", 380.00, 699.00, 25, "pcs", 70),
        ("SKU-MOB-004", "Magnetic Wireless Car Mount & 15W Charger", "Mobile & Tablet Accessories", "Air vent hook mount with strong N52 neodymium magnets and Qi fast induction charging", 850.00, 1399.00, 10, "pcs", 24),
        ("SKU-MOB-005", "Active Capacitive Stylus Pen for Touchscreens", "Mobile & Tablet Accessories", "Palm rejection, tilt sensitivity, Type-C rechargeable with magnetic iPad attachment", 1050.00, 1699.00, 12, "pcs", 4),  # LOW STOCK

        # 4. Office Equipment (5)
        ("SKU-OFF-001", "Omnidirectional 2D Barcode & QR Scanner", "Office Equipment", "USB plug & play CMOS scanner, reads 1D barcodes and QR codes from paper and phone screens", 1650.00, 2699.00, 10, "pcs", 28),
        ("SKU-OFF-002", "Heavy Duty Cross-Cut Paper Shredder 15-Sheet", "Office Equipment", "P-4 security level, shred credit cards and staples, 20L waste bin with bin-full window", 4600.00, 6999.00, 4, "units", 8),
        ("SKU-OFF-003", "Thermal Label Barcode Printer 4-inch USB/LAN", "Office Equipment", "Direct thermal 203 DPI, 152mm/sec high speed, compatible with shipping and courier labels", 5800.00, 8499.00, 6, "units", 14),
        ("SKU-OFF-004", "A3 Hot & Cold Office Document Laminator", "Office Equipment", "2-minute fast warm-up, 4-roller system, jam release lever, supports 80-250 micron pouches", 1850.00, 2899.00, 6, "units", 16),
        ("SKU-OFF-005", "Digital Electronic Cash Drawer 5-Bill 8-Coin", "Office Equipment", "Heavy gauge steel construction, RJ11 interface for receipt printer trigger, 3-position key lock", 1950.00, 3199.00, 5, "units", 11),

        # 5. Workstation & Furniture (5)
        ("SKU-FURN-001", "Ergonomic High-Back Breathable Mesh Chair", "Workstation & Furniture", "Adjustable 3D armrests, dynamic lumbar support, synchronous tilt lock mechanism, BIFMA Class 4 gas lift", 6800.00, 9999.00, 6, "units", 19),
        ("SKU-FURN-002", "Dual Motor Electric Standing Desk 140x70cm", "Workstation & Furniture", "Digital LED memory controller, height range 65-125cm, anti-collision sensor, teak wood finish tabletop", 16500.00, 23999.00, 3, "units", 7),
        ("SKU-FURN-003", "Heavy Duty Gas Spring Dual Monitor Arm", "Workstation & Furniture", "Supports two 17-32 inch screens up to 9kg each, VESA 75/100, integrated cable routing channels", 2100.00, 3499.00, 8, "pcs", 26),
        ("SKU-FURN-004", "Under-Desk Steel Mobile Pedestal File Cabinet", "Workstation & Furniture", "3-drawer central locking system with anti-tilt fifth wheel, powder coated matte black finish", 3400.00, 4999.00, 4, "units", 10),
        ("SKU-FURN-005", "Adjustable Ergonomic Footrest with Massage Rollers", "Workstation & Furniture", "3 height positions, tilt angle 0-30 degrees, floating platform for leg blood circulation", 650.00, 1199.00, 10, "pcs", 3),  # LOW STOCK

        # 6. Networking Hardware (6)
        ("SKU-NET-001", "24-Port Gigabit Managed L2+ PoE Switch 370W", "Networking Hardware", "24x 10/100/1000Mbps RJ45 ports with 802.3at PoE+, 4x 1G SFP slots, VLAN & QoS management", 14500.00, 20999.00, 4, "units", 12),
        ("SKU-NET-002", "AX3000 Dual-Band Wi-Fi 6 Gigabit Router", "Networking Hardware", "Speeds up to 2402 Mbps on 5GHz + 574 Mbps on 2.4GHz, 4 high-gain external antennas, WPA3 security", 2800.00, 4299.00, 10, "pcs", 34),
        ("SKU-NET-003", "Ceiling Mount Wi-Fi 6 Enterprise Access Point", "Networking Hardware", "OFDMA, MU-MIMO 2x2, seamless roaming 802.11k/v/r, PoE powered, supports 250+ clients", 5200.00, 7899.00, 6, "units", 18),
        ("SKU-NET-004", "8-Port Gigabit Unmanaged Desktop Switch", "Networking Hardware", "Plug and play metal casing, 10/100/1000Mbps auto-negotiation, IEEE 802.3x flow control", 850.00, 1399.00, 15, "pcs", 45),
        ("SKU-NET-005", "Cat6 UTP Solid Copper Cable Roll 305 Meters", "Networking Hardware", "23 AWG pure bare copper conductors, 250MHz bandwidth, verified for high-speed Gigabit LAN", 5400.00, 7699.00, 8, "rolls", 21),
        ("SKU-NET-006", "9U Wall Mount Server Network Rack with Glass Door", "Networking Hardware", "19-inch standard rack depth 550mm, removable side panels, cooling fan and PDU mounting slots", 3100.00, 4699.00, 3, "units", 0),  # OUT OF STOCK

        # 7. Data Storage & Memory (6)
        ("SKU-STOR-001", "1TB NVMe PCIe 4.0 Gen4 M.2 Solid State Drive", "Data Storage & Memory", "Read speed up to 7400 MB/s, write speed 6500 MB/s, 3D TLC NAND with dynamic SLC cache", 4200.00, 5999.00, 12, "pcs", 52),
        ("SKU-STOR-002", "2TB Rugged External USB 3.2 Portable HDD", "Data Storage & Memory", "Military grade shockproof silicone casing, USB 3.2 Gen 1 high-speed transfer, pre-formatted NTFS", 4100.00, 5799.00, 10, "pcs", 29),
        ("SKU-STOR-003", "500GB Portable NVMe USB-C External SSD", "Data Storage & Memory", "Speeds up to 1050 MB/s, aluminum unibody thermal shell, drop-resistant up to 2 meters", 3300.00, 4699.00, 8, "pcs", 22),
        ("SKU-STOR-004", "16GB DDR5 5600MHz Desktop RAM Module", "Data Storage & Memory", "CL36 low-latency, on-die ECC error correction, Intel XMP 3.0 & AMD EXPO profile support", 2900.00, 4199.00, 15, "pcs", 40),
        ("SKU-STOR-005", "32GB DDR4 3200MHz SODIMM Laptop RAM", "Data Storage & Memory", "1.2V low voltage standard, 260-pin unbuffered non-ECC notebook memory upgrade", 3800.00, 5499.00, 8, "pcs", 18),
        ("SKU-STOR-006", "128GB High Endurance MicroSDXC Class 10 U3", "Data Storage & Memory", "V30 video speed class, optimized for 4K security CCTV cameras, dash cams, and drones", 620.00, 999.00, 20, "pcs", 65),

        # 8. Printers & Consumables (5)
        ("SKU-PRNT-001", "Heavy-Duty Monochrome Laser Printer with Duplex", "Printers & Consumables", "30 pages/min print speed, automatic two-sided printing, Wi-Fi, Ethernet & USB connectivity", 9800.00, 13499.00, 4, "units", 14),
        ("SKU-PRNT-002", "80mm Thermal Receipt Billing Printer USB/LAN", "Printers & Consumables", "260mm/sec ultra-fast printing, automatic cutter, cash drawer kick-out port, ESC/POS compatible", 3100.00, 4599.00, 8, "units", 23),
        ("SKU-PRNT-003", "High-Yield Black Laser Toner Cartridge (2,500 Pgs)", "Printers & Consumables", "Premium spherical polymer toner for crisp dark text output and smudge-free prints", 950.00, 1599.00, 15, "boxes", 45),
        ("SKU-PRNT-004", "80mm x 50m Thermal Paper Rolls (Box of 50)", "Printers & Consumables", "BPA-free high sensitivity thermal paper, bright white with dark thermal contrast image", 1150.00, 1799.00, 10, "boxes", 5),  # LOW STOCK
        ("SKU-PRNT-005", "Direct Thermal Shipping Labels 4x6 (Roll of 500)", "Printers & Consumables", "Strong self-adhesive backing, waterproof and oil-proof coating for courier dispatch", 260.00, 449.00, 25, "rolls", 80),

        # 9. Audio & Visual Equipment (5)
        ("SKU-AV-001", "27-inch 4K UHD IPS Professional Monitor (Type-C)", "Audio & Visual Equipment", "3840x2160, 99% sRGB, 65W USB-C Power Delivery, HDR400, Height Adjustable Pivot Stand", 21500.00, 28999.00, 4, "units", 11),
        ("SKU-AV-002", "Active Noise Cancelling Wireless Headset with Mic", "Audio & Visual Equipment", "Hybrid ANC, AI environmental noise cancelling boom microphone, 40-hour playback time", 2900.00, 4499.00, 10, "pcs", 31),
        ("SKU-AV-003", "360-Degree Conference Room USB Speakerphone", "Audio & Visual Equipment", "4 beamforming microphone arrays with 5-meter pickup radius, DSP echo cancellation", 4100.00, 6299.00, 5, "units", 14),
        ("SKU-AV-004", "24-inch Full HD 100Hz Frameless IPS Monitor", "Audio & Visual Equipment", "1920x1080 resolution, 1ms VRB response, HDMI & VGA ports, low blue light eye-care filter", 6800.00, 9299.00, 8, "units", 25),
        ("SKU-AV-005", "USB 3.0 4K HDMI Video Capture Card (60fps)", "Audio & Visual Equipment", "Zero-latency HDMI passthrough, compatible with OBS, Zoom, Teams for streaming and recording", 1350.00, 2199.00, 10, "pcs", 20),

        # 10. Cables & Adapters (6)
        ("SKU-CAB-001", "8-in-1 Aluminum USB-C Hub / Docking Station", "Cables & Adapters", "4K HDMI, 100W PD charging, 3x USB 3.0, SD/MicroSD card reader, 1000Mbps Gigabit RJ45", 1450.00, 2399.00, 15, "pcs", 44),
        ("SKU-CAB-002", "Braided HDMI 2.1 Ultra High Speed Cable 2M (8K 60Hz)", "Cables & Adapters", "48Gbps bandwidth, Dynamic HDR, eARC, 24K gold-plated connectors with zinc alloy housing", 360.00, 649.00, 25, "pcs", 68),
        ("SKU-CAB-003", "Cat6 Gigabit Snagless Ethernet Patch Cable 3M", "Cables & Adapters", "50-micron gold plated RJ45 plugs, 100% stranded pure copper wire, molded strain relief", 90.00, 189.00, 40, "pcs", 110),
        ("SKU-CAB-004", "100W USB-C to USB-C Braided Fast Charge Cable 2M", "Cables & Adapters", "E-Marker smart chip, supports 20V/5A power delivery and 480Mbps fast data sync", 220.00, 449.00, 30, "pcs", 95),
        ("SKU-CAB-005", "DisplayPort 1.4 to HDMI 2.0 4K 60Hz Adapter Cable", "Cables & Adapters", "Unidirectional DP to HDMI conversion, supports 3840x2160 @ 60Hz with audio pass-through", 410.00, 749.00, 15, "pcs", 33),
        ("SKU-CAB-006", "Thunderbolt 4 Certified Cable 40Gbps 1M", "Cables & Adapters", "Full 40Gbps data bandwidth, 240W EPR power delivery, supports single 8K or dual 4K displays", 1650.00, 2699.00, 8, "pcs", 0),  # OUT OF STOCK

        # 11. Power Protection & UPS (5)
        ("SKU-PWR-001", "1000VA Line-Interactive UPS with AVR (3 Sockets)", "Power Protection & UPS", "Microprocessor controlled automatic voltage regulation, battery backup up to 45 mins", 3900.00, 5699.00, 5, "units", 15),
        ("SKU-PWR-002", "Heavy Duty 6-Way Spike Buster Surge Protector 2M", "Power Protection & UPS", "Thermal circuit breaker reset switch, 525 Joules surge protection, safety shutter sockets", 420.00, 799.00, 20, "pcs", 50),
        ("SKU-PWR-003", "650VA Desktop PC Backup UPS with Generator Support", "Power Protection & UPS", "Fast recharge in 4 hours, cold start function, audible alarms for overload and low battery", 2150.00, 3199.00, 8, "units", 22),
        ("SKU-PWR-004", "2000VA / 2kVA Online Pure Sine Wave UPS", "Power Protection & UPS", "Zero transfer time, high frequency double conversion topology, LCD parameter monitoring", 14800.00, 21999.00, 2, "units", 4),
        ("SKU-PWR-005", "12V 9Ah Rechargeable Sealed Lead-Acid UPS Battery", "Power Protection & UPS", "Maintenance-free AGM technology, high discharge rate performance for standby backup", 780.00, 1299.00, 15, "pcs", 4),  # LOW STOCK

        # 12. Industrial Automation & Sensors (5)
        ("SKU-IND-001", "ESP32-S3 Dual-Core Wi-Fi & BLE 5.0 Dev Board", "Industrial Automation", "Xtensa 32-bit LX7 MCU, 8MB PSRAM, 16MB Flash, USB-OTG and JTAG interface headers", 380.00, 649.00, 25, "pcs", 75),
        ("SKU-IND-002", "Industrial RS485 Modbus RTU to Ethernet Gateway", "Industrial Automation", "DIN-rail mounting, 10/100M Ethernet port, 15KV ESD protection, web server configuration", 1950.00, 3199.00, 8, "units", 17),
        ("SKU-IND-003", "8-Channel 24V Relay Module with Optocoupler Isolation", "Industrial Automation", "High current 10A AC250V / DC30V output, standard interface directly controllable by MCU", 450.00, 799.00, 15, "pcs", 38),
        ("SKU-IND-004", "Precision Industrial Digital Caliper 150mm (0.01mm)", "Industrial Automation", "Stainless steel frame, extra large LCD screen, IP54 dust and splash resistant, zero set", 720.00, 1299.00, 10, "pcs", 27),
        ("SKU-IND-005", "12M Optical Time-of-Flight LiDAR Distance Sensor", "Industrial Automation", "UART/I2C communication, high frequency up to 100Hz, outdoor ambient light resistance", 1600.00, 2599.00, 8, "pcs", 19)
    ]

    prod_map = {}  # sku -> prod_id
    prod_info = {}  # prod_id -> {sku, cost, sell, unit, name}

    for sku, name, cat_name, desc, cost, sell, reorder, unit, init_stock in product_defs:
        cat_id = cat_map[cat_name]
        prod_id = db.execute_insert(
            """
            INSERT INTO products 
            (sku, name, category_id, description, cost_price, selling_price, reorder_level, unit, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (sku, name, cat_id, desc, Decimal(str(cost)), Decimal(str(sell)), reorder, unit)
        )
        prod_map[sku] = prod_id
        prod_info[prod_id] = {
            "sku": sku, "name": name, "cost": Decimal(str(cost)),
            "sell": Decimal(str(sell)), "unit": unit, "reorder": reorder
        }

        # Insert initial warehouse inventory
        db.execute_insert(
            """
            INSERT INTO inventory (product_id, quantity_on_hand, reorder_point)
            VALUES (%s, %s, %s)
            """,
            (prod_id, init_stock, reorder)
        )

        # Initial stock movement audit log
        if init_stock > 0:
            db.execute_insert(
                """
                INSERT INTO stock_movements 
                (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id, created_at)
                VALUES (%s, 'INITIAL_STOCK', %s, %s, 'INITIAL_STOCK', NULL, 'Master warehouse opening stock balance initialization', %s, %s)
                """,
                (prod_id, init_stock, init_stock, admin_id, datetime.now() - timedelta(days=360))
            )

    print(f"  [OK] Seeded {len(prod_map)} products with live inventory records & stock movements.")

    # 7. Seed 28 Purchase Orders with Line Items & Stock Receipts
    print("\n[Step 8/10] Seeding Purchase Orders (28 POs & Inbound Receipts across 12 months)...")
    supp_ids = list(supp_map.values())
    prod_ids = list(prod_info.keys())
    
    # Generate dates across past 12 months (360 days down to 5 days ago)
    base_date = date.today()
    po_statuses = ["Received"] * 20 + ["Partially Received"] * 3 + ["Ordered"] * 3 + ["Draft"] * 1 + ["Cancelled"] * 1
    random.seed(42)  # Deterministic seed for reproducible testing
    random.shuffle(po_statuses)

    total_po_items_count = 0
    total_po_movements = 0

    for idx, status in enumerate(po_statuses, start=1):
        po_num = f"PO-2025-{idx:04d}" if idx <= 18 else f"PO-2026-{idx:04d}"
        days_ago = max(5, int(350 - (idx * 11.5) + random.randint(-5, 5)))
        po_date = base_date - timedelta(days=days_ago)
        expected_date = po_date + timedelta(days=random.randint(4, 12))
        supplier_id = supp_ids[(idx - 1) % len(supp_ids)]

        # Pick 2-4 distinct products for this PO
        selected_p_ids = random.sample(prod_ids, k=random.randint(2, 4))
        
        # Calculate items
        items_data = []
        subtotal = Decimal("0.00")

        for pid in selected_p_ids:
            p_data = prod_info[pid]
            qty_ordered = random.randint(10, 40)
            unit_cost = p_data["cost"]
            line_tot = Decimal(str(qty_ordered)) * unit_cost
            subtotal += line_tot

            if status == "Received":
                qty_received = qty_ordered
            elif status == "Partially Received":
                qty_received = int(qty_ordered * 0.5)
            else:
                qty_received = 0

            items_data.append({
                "product_id": pid,
                "qty_ordered": qty_ordered,
                "qty_received": qty_received,
                "unit_cost": unit_cost,
                "line_total": line_tot
            })

        tax_amount = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        total_amount = subtotal + tax_amount

        # Insert PO header
        po_id = db.execute_insert(
            """
            INSERT INTO purchase_orders 
            (po_number, supplier_id, order_date, expected_date, status, subtotal, tax_amount, total_amount, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                po_num, supplier_id, po_date, expected_date, status,
                subtotal, tax_amount, total_amount,
                f"Procurement order {po_num} for warehouse restocking",
                datetime.combine(po_date, datetime.min.time()) + timedelta(hours=10)
            )
        )

        # Insert PO items and update stock if received
        for item in items_data:
            db.execute_insert(
                """
                INSERT INTO purchase_order_items 
                (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_cost, line_total)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (po_id, item["product_id"], item["qty_ordered"], item["qty_received"], item["unit_cost"], item["line_total"])
            )
            total_po_items_count += 1

            if item["qty_received"] > 0:
                # Update inventory quantity
                db.execute_update(
                    "UPDATE inventory SET quantity_on_hand = quantity_on_hand + %s WHERE product_id = %s",
                    (item["qty_received"], item["product_id"])
                )
                curr_bal = db.execute_one("SELECT quantity_on_hand FROM inventory WHERE product_id = %s", (item["product_id"],))["quantity_on_hand"]
                
                # Record PO_RECEIPT stock movement
                db.execute_insert(
                    """
                    INSERT INTO stock_movements 
                    (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id, created_at)
                    VALUES (%s, 'PO_RECEIPT', %s, %s, 'PURCHASE_ORDER', %s, %s, %s, %s)
                    """,
                    (
                        item["product_id"], item["qty_received"], curr_bal, po_id,
                        f"Goods received under {po_num}", admin_id,
                        datetime.combine(expected_date, datetime.min.time()) + timedelta(hours=14)
                    )
                )
                total_po_movements += 1

    print(f"  [OK] Seeded {len(po_statuses)} Purchase Orders ({total_po_items_count} line items, {total_po_movements} stock receipts).")

    # 8. Seed 40 Sales Orders with Line Items, Stock Deductions, Payments & Shipments
    print("\n[Step 9/10] Seeding Sales Orders, Payments & Carrier Shipments (40 Orders across 12 months)...")
    cust_ids = list(cust_map.values())
    so_statuses = ["Delivered"] * 24 + ["Shipped"] * 6 + ["Processing"] * 4 + ["Confirmed"] * 3 + ["Draft"] * 2 + ["Cancelled"] * 1
    random.shuffle(so_statuses)

    total_so_items_count = 0
    total_so_movements = 0
    total_payments_count = 0
    total_shipments_count = 0

    payment_methods = ["UPI", "Bank Transfer", "Credit Card", "Debit Card", "Cheque", "Cash"]
    carriers = ["BlueDart Express", "Delhivery Logistics", "DTDC Express", "FedEx India", "Ekart Logistics", "Speed Post"]

    for idx, status in enumerate(so_statuses, start=1):
        so_num = f"SO-2025-{idx:04d}" if idx <= 26 else f"SO-2026-{idx:04d}"
        days_ago = max(2, int(340 - (idx * 8.2) + random.randint(-4, 4)))
        so_date = base_date - timedelta(days=days_ago)
        customer_id = cust_ids[(idx - 1) % len(cust_ids)]

        # Pick 2-3 products for this sales order
        selected_p_ids = random.sample(prod_ids, k=random.randint(2, 3))
        items_data = []
        subtotal = Decimal("0.00")

        # Determine if stock should be deducted
        should_deduct = status in ["Delivered", "Shipped", "Processing"]

        for pid in selected_p_ids:
            p_data = prod_info[pid]
            qty = random.randint(1, 5)
            unit_price = p_data["sell"]
            line_tot = Decimal(str(qty)) * unit_price
            subtotal += line_tot

            items_data.append({
                "product_id": pid,
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": line_tot
            })

        discount = Decimal(str(random.choice([0, 0, 100, 250, 500])))
        if discount >= subtotal:
            discount = Decimal("0.00")
        
        tax_amount = ((subtotal - discount) * Decimal("0.18")).quantize(Decimal("0.01"))
        total_amount = (subtotal - discount) + tax_amount

        # Insert SO header
        so_id = db.execute_insert(
            """
            INSERT INTO sales_orders 
            (order_number, customer_id, order_date, status, subtotal, discount_amount, tax_amount, total_amount, notes, stock_deducted, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                so_num, customer_id, so_date, status,
                subtotal, discount, tax_amount, total_amount,
                f"Customer order {so_num} - standard commercial supply",
                1 if should_deduct else 0,
                datetime.combine(so_date, datetime.min.time()) + timedelta(hours=11)
            )
        )

        # Insert SO items and deduct stock if applicable
        for item in items_data:
            db.execute_insert(
                """
                INSERT INTO sales_order_items 
                (sales_order_id, product_id, quantity, unit_price, line_total)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (so_id, item["product_id"], item["quantity"], item["unit_price"], item["line_total"])
            )
            total_so_items_count += 1

            if should_deduct:
                # Deduct inventory safely
                db.execute_update(
                    """
                    UPDATE inventory 
                    SET quantity_on_hand = GREATEST(0, quantity_on_hand - %s) 
                    WHERE product_id = %s
                    """,
                    (item["quantity"], item["product_id"])
                )
                curr_bal = db.execute_one("SELECT quantity_on_hand FROM inventory WHERE product_id = %s", (item["product_id"],))["quantity_on_hand"]

                # Record SO_FULFILLMENT stock movement
                db.execute_insert(
                    """
                    INSERT INTO stock_movements 
                    (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id, created_at)
                    VALUES (%s, 'SO_FULFILLMENT', %s, %s, 'SALES_ORDER', %s, %s, %s, %s)
                    """,
                    (
                        item["product_id"], item["quantity"], curr_bal, so_id,
                        f"Dispatched & fulfilled for sales order {so_num}", admin_id,
                        datetime.combine(so_date, datetime.min.time()) + timedelta(hours=15)
                    )
                )
                total_so_movements += 1

        # Seed Payments for Confirmed, Processing, Shipped, Delivered orders (approx 32 payments)
        if status in ["Delivered", "Shipped", "Processing"]:
            pay_num = f"PAY-2025-{idx:04d}" if idx <= 26 else f"PAY-2026-{idx:04d}"
            pay_date = so_date + timedelta(days=random.randint(0, 3))
            method = random.choice(payment_methods)
            ref_no = f"TXN-{random.randint(10000000, 99999999)}"

            # 85% full payment, 15% partial payment
            is_full = (random.random() > 0.15)
            pay_amount = total_amount if is_full else (total_amount * Decimal("0.6")).quantize(Decimal("0.01"))
            pay_status = "Completed"

            db.execute_insert(
                """
                INSERT INTO payments 
                (payment_number, sales_order_id, payment_date, amount, payment_method, reference_number, status, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pay_num, so_id, pay_date, pay_amount, method, ref_no, pay_status,
                    f"Payment received against {so_num} via {method}",
                    datetime.combine(pay_date, datetime.min.time()) + timedelta(hours=16)
                )
            )
            total_payments_count += 1

        # Seed Shipments for Shipped and Delivered orders (approx 30 shipments)
        if status in ["Delivered", "Shipped"]:
            shp_num = f"SHP-2025-{idx:04d}" if idx <= 26 else f"SHP-2026-{idx:04d}"
            carrier = random.choice(carriers)
            track_no = f"{carrier[:3].upper()}-{random.randint(10000000, 99999999)}"
            dispatch_d = so_date + timedelta(days=1)
            est_deliv = dispatch_d + timedelta(days=random.randint(2, 5))
            actual_deliv = est_deliv if status == "Delivered" else None
            shp_status = "Delivered" if status == "Delivered" else "In Transit"

            db.execute_insert(
                """
                INSERT INTO shipments 
                (shipment_number, sales_order_id, carrier, tracking_number, dispatch_date, estimated_delivery, actual_delivery, status, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    shp_num, so_id, carrier, track_no, dispatch_d, est_deliv, actual_deliv,
                    shp_status, f"Logistics carrier dispatch for order {so_num}",
                    datetime.combine(dispatch_d, datetime.min.time()) + timedelta(hours=12)
                )
            )
            total_shipments_count += 1

    print(f"  [OK] Seeded {len(so_statuses)} Sales Orders ({total_so_items_count} line items, {total_so_movements} fulfillment deductions).")
    print(f"  [OK] Seeded {total_payments_count} Payment Transactions.")
    print(f"  [OK] Seeded {total_shipments_count} Logistics Shipments.")

    # 9. Seed Manual Warehouse Stock Adjustments for Audit Richness
    print("\n[Step 10/10] Seeding Warehouse Adjustment Logs (Audit Ledger Complete)...")
    adjustment_samples = [
        (prod_map["SKU-ACC-001"], "ADJUSTMENT_ADD", 10, "Physical Inventory Count Discrepancy", "Found extra sealed master carton in rack B-04 during annual audit"),
        (prod_map["SKU-STOR-001"], "ADJUSTMENT_SUB", 2, "Damaged Goods Write-off", "Corner packaging damaged during internal warehouse forklift transit"),
        (prod_map["SKU-NET-002"], "ADJUSTMENT_ADD", 5, "Customer Return to Stock", "Unopened customer order return RMA-4019 inspected and restocked"),
        (prod_map["SKU-CAB-001"], "ADJUSTMENT_SUB", 3, "Supplier Return / Defect", "Defective pin header batch returned to supplier for warranty replacement"),
        (prod_map["SKU-OFF-001"], "ADJUSTMENT_ADD", 2, "Warehouse Relocation Re-count", "Reconciled floor balance after shelf relocation to aisle 3")
    ]

    for pid, m_type, qty, reason_cat, reason_notes in adjustment_samples:
        is_add = (m_type == "ADJUSTMENT_ADD")
        if is_add:
            db.execute_update("UPDATE inventory SET quantity_on_hand = quantity_on_hand + %s WHERE product_id = %s", (qty, pid))
        else:
            db.execute_update("UPDATE inventory SET quantity_on_hand = GREATEST(0, quantity_on_hand - %s) WHERE product_id = %s", (qty, pid))

        bal = db.execute_one("SELECT quantity_on_hand FROM inventory WHERE product_id = %s", (pid,))["quantity_on_hand"]
        db.execute_insert(
            """
            INSERT INTO stock_movements 
            (product_id, movement_type, quantity, balance_after, reference_type, reference_id, notes, created_by_admin_id, created_at)
            VALUES (%s, %s, %s, %s, 'MANUAL_ADJUSTMENT', NULL, %s, %s, %s)
            """,
            (pid, m_type, qty, bal, f"[{reason_cat}] {reason_notes}", admin_id, datetime.now() - timedelta(days=random.randint(10, 80)))
        )

    # 10. Summary Report
    print("\n" + "=" * 70)
    print("DATABASE SEEDING COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    
    counts = {
        "Categories": db.execute_one("SELECT COUNT(*) as c FROM categories")["c"],
        "Suppliers": db.execute_one("SELECT COUNT(*) as c FROM suppliers")["c"],
        "Customers": db.execute_one("SELECT COUNT(*) as c FROM customers")["c"],
        "Products Master": db.execute_one("SELECT COUNT(*) as c FROM products")["c"],
        "Inventory Records": db.execute_one("SELECT COUNT(*) as c FROM inventory")["c"],
        "Purchase Orders": db.execute_one("SELECT COUNT(*) as c FROM purchase_orders")["c"],
        "PO Line Items": db.execute_one("SELECT COUNT(*) as c FROM purchase_order_items")["c"],
        "Sales Orders": db.execute_one("SELECT COUNT(*) as c FROM sales_orders")["c"],
        "SO Line Items": db.execute_one("SELECT COUNT(*) as c FROM sales_order_items")["c"],
        "Payments": db.execute_one("SELECT COUNT(*) as c FROM payments")["c"],
        "Shipments": db.execute_one("SELECT COUNT(*) as c FROM shipments")["c"],
        "Stock Movements": db.execute_one("SELECT COUNT(*) as c FROM stock_movements")["c"],
    }
    
    total_records = sum(counts.values())
    for tbl, cnt in counts.items():
        print(f"  * {tbl:<25}: {cnt:>5} records")
    print("-" * 70)
    print(f"  TOTAL DATASET GENERATED: {total_records} interconnected records across all modules.")
    print("=" * 70 + "\n")
    return True

if __name__ == "__main__":
    run_seed()
