"""
SkySaver AI — airport lookup.

A curated list of major international airports so the UI can offer real
autocomplete (city + IATA) instead of asking users to type raw codes.
This is intentionally short — the busiest ~120 hubs cover almost every
realistic hackathon demo route.
"""

from __future__ import annotations


AIRPORTS: list[tuple[str, str, str]] = [
    # (IATA, City, Country)
    ("LHR", "London Heathrow", "United Kingdom"),
    ("LGW", "London Gatwick", "United Kingdom"),
    ("STN", "London Stansted", "United Kingdom"),
    ("LCY", "London City", "United Kingdom"),
    ("MAN", "Manchester", "United Kingdom"),
    ("EDI", "Edinburgh", "United Kingdom"),
    ("DUB", "Dublin", "Ireland"),
    ("CDG", "Paris Charles de Gaulle", "France"),
    ("ORY", "Paris Orly", "France"),
    ("AMS", "Amsterdam Schiphol", "Netherlands"),
    ("FRA", "Frankfurt", "Germany"),
    ("MUC", "Munich", "Germany"),
    ("BER", "Berlin", "Germany"),
    ("MAD", "Madrid Barajas", "Spain"),
    ("BCN", "Barcelona", "Spain"),
    ("FCO", "Rome Fiumicino", "Italy"),
    ("MXP", "Milan Malpensa", "Italy"),
    ("ZRH", "Zurich", "Switzerland"),
    ("VIE", "Vienna", "Austria"),
    ("CPH", "Copenhagen", "Denmark"),
    ("ARN", "Stockholm Arlanda", "Sweden"),
    ("OSL", "Oslo", "Norway"),
    ("HEL", "Helsinki", "Finland"),
    ("LIS", "Lisbon", "Portugal"),
    ("ATH", "Athens", "Greece"),
    ("IST", "Istanbul", "Turkey"),
    ("SAW", "Istanbul Sabiha Gokcen", "Turkey"),
    ("WAW", "Warsaw", "Poland"),
    ("PRG", "Prague", "Czech Republic"),
    ("BRU", "Brussels", "Belgium"),

    ("JFK", "New York JFK", "United States"),
    ("LGA", "New York LaGuardia", "United States"),
    ("EWR", "New York Newark", "United States"),
    ("BOS", "Boston Logan", "United States"),
    ("PHL", "Philadelphia", "United States"),
    ("IAD", "Washington Dulles", "United States"),
    ("DCA", "Washington Reagan", "United States"),
    ("MIA", "Miami", "United States"),
    ("MCO", "Orlando", "United States"),
    ("ATL", "Atlanta", "United States"),
    ("DFW", "Dallas Fort Worth", "United States"),
    ("IAH", "Houston Intercontinental", "United States"),
    ("ORD", "Chicago O'Hare", "United States"),
    ("MDW", "Chicago Midway", "United States"),
    ("DTW", "Detroit", "United States"),
    ("MSP", "Minneapolis St Paul", "United States"),
    ("DEN", "Denver", "United States"),
    ("SLC", "Salt Lake City", "United States"),
    ("PHX", "Phoenix", "United States"),
    ("LAS", "Las Vegas", "United States"),
    ("LAX", "Los Angeles", "United States"),
    ("SFO", "San Francisco", "United States"),
    ("SAN", "San Diego", "United States"),
    ("SEA", "Seattle Tacoma", "United States"),
    ("PDX", "Portland", "United States"),
    ("YYZ", "Toronto Pearson", "Canada"),
    ("YVR", "Vancouver", "Canada"),
    ("YUL", "Montreal", "Canada"),
    ("MEX", "Mexico City", "Mexico"),
    ("CUN", "Cancun", "Mexico"),
    ("GRU", "Sao Paulo Guarulhos", "Brazil"),
    ("EZE", "Buenos Aires Ezeiza", "Argentina"),
    ("BOG", "Bogota", "Colombia"),
    ("LIM", "Lima", "Peru"),

    ("DXB", "Dubai", "United Arab Emirates"),
    ("AUH", "Abu Dhabi", "United Arab Emirates"),
    ("DOH", "Doha Hamad", "Qatar"),
    ("BAH", "Bahrain", "Bahrain"),
    ("RUH", "Riyadh", "Saudi Arabia"),
    ("JED", "Jeddah", "Saudi Arabia"),
    ("KWI", "Kuwait", "Kuwait"),
    ("TLV", "Tel Aviv", "Israel"),
    ("CAI", "Cairo", "Egypt"),
    ("JNB", "Johannesburg", "South Africa"),
    ("CPT", "Cape Town", "South Africa"),
    ("LOS", "Lagos", "Nigeria"),
    ("NBO", "Nairobi", "Kenya"),
    ("ADD", "Addis Ababa", "Ethiopia"),

    ("BOM", "Mumbai", "India"),
    ("DEL", "Delhi", "India"),
    ("BLR", "Bangalore", "India"),
    ("MAA", "Chennai", "India"),
    ("HYD", "Hyderabad", "India"),
    ("CCU", "Kolkata", "India"),
    ("GOI", "Goa", "India"),
    ("COK", "Kochi", "India"),
    ("CMB", "Colombo", "Sri Lanka"),
    ("KTM", "Kathmandu", "Nepal"),
    ("DAC", "Dhaka", "Bangladesh"),

    ("BKK", "Bangkok Suvarnabhumi", "Thailand"),
    ("DMK", "Bangkok Don Mueang", "Thailand"),
    ("HKT", "Phuket", "Thailand"),
    ("CNX", "Chiang Mai", "Thailand"),
    ("SIN", "Singapore Changi", "Singapore"),
    ("KUL", "Kuala Lumpur", "Malaysia"),
    ("CGK", "Jakarta", "Indonesia"),
    ("DPS", "Bali Denpasar", "Indonesia"),
    ("MNL", "Manila", "Philippines"),
    ("HAN", "Hanoi", "Vietnam"),
    ("SGN", "Ho Chi Minh City", "Vietnam"),
    ("PNH", "Phnom Penh", "Cambodia"),

    ("HKG", "Hong Kong", "Hong Kong"),
    ("TPE", "Taipei Taoyuan", "Taiwan"),
    ("PEK", "Beijing Capital", "China"),
    ("PKX", "Beijing Daxing", "China"),
    ("PVG", "Shanghai Pudong", "China"),
    ("SHA", "Shanghai Hongqiao", "China"),
    ("CAN", "Guangzhou", "China"),
    ("SZX", "Shenzhen", "China"),
    ("ICN", "Seoul Incheon", "South Korea"),
    ("GMP", "Seoul Gimpo", "South Korea"),
    ("HND", "Tokyo Haneda", "Japan"),
    ("NRT", "Tokyo Narita", "Japan"),
    ("KIX", "Osaka Kansai", "Japan"),
    ("FUK", "Fukuoka", "Japan"),

    ("SYD", "Sydney", "Australia"),
    ("MEL", "Melbourne", "Australia"),
    ("BNE", "Brisbane", "Australia"),
    ("PER", "Perth", "Australia"),
    ("ADL", "Adelaide", "Australia"),
    ("AKL", "Auckland", "New Zealand"),
    ("WLG", "Wellington", "New Zealand"),
]


def display_label(iata: str, city: str, country: str) -> str:
    return f"{city} ({iata}) · {country}"


# Pre-built display list and lookup map for the UI.
LABELS: list[str] = sorted(display_label(c, city, country) for c, city, country in AIRPORTS)


def iata_from_label(label: str | None) -> str:
    """Pull the IATA code out of a 'City (IATA) · Country' label."""
    if not label:
        return ""
    if "(" in label and ")" in label:
        return label.split("(", 1)[1].split(")", 1)[0].strip().upper()
    return label.strip().upper()


def label_from_iata(iata: str) -> str | None:
    """Find the display label for a given IATA code, if known."""
    iata_u = (iata or "").strip().upper()
    for code, city, country in AIRPORTS:
        if code == iata_u:
            return display_label(code, city, country)
    return None
