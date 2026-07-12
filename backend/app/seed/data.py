"""Static demo-data definitions for the seed script (no DB access here)."""

import base64

# 1x1 green PNG used as the physical file behind every seeded proof upload.
PROOF_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

DEMO_PASSWORD = "Demo@123"

DEPARTMENTS = [
    # (name, parent_name)
    ("Corporate", None),
    ("Operations", "Corporate"),
    ("Manufacturing", "Operations"),
    ("Assembly Line", "Manufacturing"),
    ("Logistics", "Operations"),
    ("Sustainability & ESG", "Corporate"),
    ("Human Resources", "Corporate"),
    ("Finance", "Corporate"),
    ("IT & Digital", "Corporate"),
    ("Sales & Marketing", "Corporate"),
]

CSR_CATEGORIES = ["Community Development", "Environment", "Education", "Health & Wellbeing"]
CHALLENGE_CATEGORIES = ["Sustainability", "Transportation", "Energy Saving", "CSR", "Governance"]

# (name, source_type, unit, factor_value, scope, version, status)
EMISSION_FACTORS = [
    ("Diesel (Purchase)", "purchase", "L", 2.68, "scope1", 1, "active"),
    ("Petrol (Purchase)", "purchase", "L", 2.31, "scope1", 1, "active"),
    ("Steel (Purchased Goods)", "purchase", "kg", 1.85, "scope3", 1, "active"),
    ("Grid Electricity (Expense)", "expense", "kWh", 0.85, "scope2", 1, "inactive"),
    ("Grid Electricity (Expense)", "expense", "kWh", 0.82, "scope2", 2, "active"),
    ("Furnace Oil (Manufacturing)", "manufacturing", "L", 3.15, "scope1", 1, "active"),
    ("Process Energy (Manufacturing)", "manufacturing", "kWh", 0.82, "scope2", 1, "active"),
    ("Diesel Fleet", "fleet", "L", 2.68, "scope1", 1, "active"),
    ("Road Freight (Fleet)", "fleet", "km", 0.12, "scope3", 1, "active"),
]

# (name, rule_type, rule_value, icon, description)
BADGES = [
    ("First Steps", "xp_threshold", 50, "🌱", "Earn your first 50 XP"),
    ("Rising Star", "xp_threshold", 150, "⭐", "Earn 150 lifetime XP"),
    ("Eco Warrior", "xp_threshold", 300, "🌿", "Earn 300 lifetime XP"),
    ("Sustainability Champion", "xp_threshold", 600, "🏆", "Earn 600 lifetime XP"),
    ("Planet Guardian", "xp_threshold", 1000, "🌍", "Earn 1000 lifetime XP"),
    ("Challenger", "challenge_count", 1, "🎯", "Complete your first challenge"),
    ("Go-Getter", "challenge_count", 3, "🚀", "Complete 3 challenges"),
    ("Habit Builder", "challenge_count", 5, "🔁", "Complete 5 challenges"),
    ("Challenge Master", "challenge_count", 10, "👑", "Complete 10 challenges"),
    ("Helping Hand", "csr_count", 1, "🤝", "Join and complete your first CSR activity"),
    ("Community Builder", "csr_count", 3, "🏘️", "Complete 3 CSR activities"),
    ("Social Star", "csr_count", 5, "💫", "Complete 5 CSR activities"),
    ("CSR Legend", "csr_count", 10, "🦸", "Complete 10 CSR activities"),
    ("Founder's Award", "manual", None, "🎖️", "Awarded personally by the leadership team"),
    ("Green Innovator", "manual", None, "💡", "Awarded for an outstanding sustainability idea"),
]

# (name, points_cost, stock, description)
REWARDS = [
    ("Steel Water Bottle", 100, 40, "Insulated reusable bottle with EcoSphere branding"),
    ("Canvas Tote Bag", 120, 35, "Handmade organic-cotton tote"),
    ("Plant a Tree in Your Name", 150, 100, "We plant a native tree and send you the geotag"),
    ("Organic Snack Box", 200, 25, "A month of organic, plastic-free snacks"),
    ("Bamboo Desk Kit", 250, 20, "Bamboo organiser, pen stand and coasters"),
    ("Solar Power Bank", 400, 15, "10,000 mAh solar-charging power bank"),
    ("Sustainable Store Voucher ₹500", 500, 30, "Voucher for partner zero-waste stores"),
    ("EcoSphere Hoodie (Limited)", 800, 0, "Recycled-fibre hoodie — limited edition"),
    ("Extra Day Off", 1000, 5, "One additional paid leave day this fiscal year"),
    ("E-bike Weekend Rental", 650, 8, "Weekend rental of an electric bike"),
]

POLICIES = [
    # (title, ack_deadline_days, status, version)
    ("Code of Environmental Conduct", 14, "published", 1),
    ("Anti-Bribery & Corruption Policy", 14, "published", 2),  # republished → re-ack demo
    ("Waste Segregation & Recycling Policy", 21, "published", 1),
    ("Supplier ESG Screening Policy", 30, "published", 1),
    ("Remote Work Emissions Guideline", 14, "draft", 1),
]

TRAININGS = [
    ("ESG Fundamentals", "Company-wide introduction to our ESG framework"),
    ("Carbon Accounting Basics", "Scopes 1-3, emission factors and reporting"),
    ("Workplace Safety & Ethics", "Annual mandatory compliance training"),
]

CSR_TITLES = [
    "Lake Cleanup Drive", "Tree Plantation Marathon", "Blood Donation Camp",
    "Digital Literacy Workshop", "Rural School Renovation", "Beach Waste Audit",
    "Community Kitchen Volunteering", "E-waste Collection Day", "Cycle to Work Rally",
    "Orphanage Study Support", "Green Diwali Awareness", "River Bank Restoration",
    "Health Checkup Camp", "Slum Sanitation Drive", "Animal Shelter Support",
    "Solar Lamp Assembly for Villages", "Plastic-Free Market Campaign",
    "Elderly Care Visit", "Career Mentoring for Students", "Rainwater Harvesting Build",
]

CHALLENGES = [
    # (title, category, xp, difficulty, evidence)
    ("No-Plastic Week", "Sustainability", 80, "easy", "inherit"),
    ("Cycle to Work — 10 Days", "Transportation", 150, "medium", "required"),
    ("Carpool Month", "Transportation", 120, "medium", "inherit"),
    ("Zero Food Waste Fortnight", "Sustainability", 100, "easy", "inherit"),
    ("Office Lights-Off Champion", "Energy Saving", 60, "easy", "not_required"),
    ("Home Energy Audit", "Energy Saving", 130, "medium", "required"),
    ("Volunteer 20 Hours", "CSR", 200, "hard", "required"),
    ("Policy Pro Quiz Streak", "Governance", 70, "easy", "not_required"),
    ("Paperless Month", "Governance", 90, "medium", "inherit"),
    ("Plant & Nurture 5 Saplings", "Sustainability", 180, "hard", "required"),
]

COMPLIANCE_ISSUES = [
    # (title, severity, dept_name, status_key)
    # status_key: overdue_open / overdue_progress / open / in_progress / resolved / closed
    ("Fire-exit obstruction in Plant 2", "critical", "Manufacturing", "overdue_open"),
    ("Missing effluent treatment log — June", "high", "Manufacturing", "overdue_open"),
    ("Expired forklift operator certifications", "high", "Logistics", "overdue_progress"),
    ("Unreported diesel spillage (minor)", "medium", "Assembly Line", "overdue_open"),
    ("Overdue statutory ESG disclosure draft", "critical", "Sustainability & ESG", "overdue_progress"),
    ("Contractor safety induction gaps", "medium", "Operations", "open"),
    ("Air-quality sensor calibration due", "low", "Manufacturing", "open"),
    ("Data-retention policy exceptions", "medium", "IT & Digital", "open"),
    ("Vendor code-of-conduct signatures pending", "medium", "Sales & Marketing", "open"),
    ("Battery disposal contract renewal", "high", "Logistics", "in_progress"),
    ("PF/ESI filing mismatch", "high", "Finance", "in_progress"),
    ("Workplace harassment training overdue for 12 staff", "high", "Human Resources", "in_progress"),
    ("Noise-level readings above limit — night shift", "medium", "Assembly Line", "in_progress"),
    ("Grievance register digitisation", "low", "Human Resources", "open"),
    ("Solar inverter warranty lapse", "low", "Operations", "resolved"),
    ("Q4 water usage over permit", "high", "Manufacturing", "resolved"),
    ("Missing MSDS sheets for new solvent", "critical", "Manufacturing", "resolved"),
    ("Canteen food-safety license renewal", "medium", "Human Resources", "closed"),
    ("Diesel generator emissions test", "medium", "Operations", "closed"),
    ("Fire drill documentation gap", "low", "Corporate", "closed"),
]

GOALS = [
    # (name, unit, baseline, target, current, dept, linked_factor)
    ("Reduce diesel usage 10% vs FY25", "L", 12000, 10800, 11450, "Manufacturing", "Diesel (Purchase)"),
    ("Cut electricity consumption 15%", "kWh", 250000, 212500, 234000, "Operations", "Grid Electricity (Expense)"),
    ("Fleet fuel per km down 12%", "L", 8000, 7040, 7590, "Logistics", "Diesel Fleet"),
    ("Reduce paper purchase 30%", "kg", 900, 630, 720, "Corporate", None),
    ("Scope 2 emissions down 20% by FY27", "kgCO2e", 205000, 164000, 192000, "Sustainability & ESG", None),
]

PRODUCTS = [
    # (name, sku, category, unit, price, energy_rating, recycled_pct, end_of_life)
    ("EcoSteel Bottle 750ml", "SKU-EB-750", "Merchandise", "unit", 549, "A", 65, "recyclable"),
    ("Recycled Paper Ream A4", "SKU-RP-A4", "Office Supplies", "ream", 289, None, 100, "recyclable"),
    ("Solar Garden Light", "SKU-SG-01", "Energy", "unit", 1299, "A+", 30, "take_back"),
    ("Industrial Solvent X2", "SKU-IS-X2", "Chemicals", "L", 850, None, 0, "hazardous"),
    ("Bamboo Packaging Crate", "SKU-BP-CR", "Packaging", "unit", 199, None, 80, "compostable"),
    ("LED High-Bay Lamp", "SKU-LED-HB", "Energy", "unit", 2499, "A+", 20, "take_back"),
]
