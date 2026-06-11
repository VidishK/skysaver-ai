"""
SkySaver AI — deep link generators.

Produces external URLs the user can click to complete real-world actions
(book a flight, hail a ride, check into a hotel) without us pretending to
process payments ourselves.
"""

from __future__ import annotations

from urllib.parse import quote_plus


# Lucky-link-style URLs (`&btnI` historically opened the first result; modern
# Google ignores it but the link is still a valid search URL.) We keep the
# search URL so the user can pick the airline's site themselves.
AIRLINE_BOOKING = {
    "EK": "https://www.emirates.com/",
    "SQ": "https://www.singaporeair.com/",
    "BA": "https://www.britishairways.com/",
    "QR": "https://www.qatarairways.com/",
    "AI": "https://www.airindia.com/",
    "AF": "https://www.airfrance.com/",
    "KL": "https://www.klm.com/",
    "LH": "https://www.lufthansa.com/",
    "TK": "https://www.turkishairlines.com/",
    "ET": "https://www.ethiopianairlines.com/",
    "EY": "https://www.etihad.com/",
    "SV": "https://www.saudia.com/",
    "DL": "https://www.delta.com/",
    "AA": "https://www.aa.com/",
    "UA": "https://www.united.com/",
    "WN": "https://www.southwest.com/",
    "AS": "https://www.alaskaair.com/",
    "B6": "https://www.jetblue.com/",
    "AC": "https://www.aircanada.com/",
    "LX": "https://www.swiss.com/",
    "OS": "https://www.austrian.com/",
    "SN": "https://www.brusselsairlines.com/",
    "IB": "https://www.iberia.com/",
    "AY": "https://www.finnair.com/",
    "SK": "https://www.flysas.com/",
    "DY": "https://www.norwegian.com/",
    "AZ": "https://www.ita-airways.com/",
    "LO": "https://www.lot.com/",
    "TP": "https://www.flytap.com/",
    "VS": "https://www.virginatlantic.com/",
    "VA": "https://www.virginaustralia.com/",
    "QF": "https://www.qantas.com/",
    "NZ": "https://www.airnewzealand.com/",
    "JL": "https://www.jal.com/",
    "NH": "https://www.ana.co.jp/",
    "KE": "https://www.koreanair.com/",
    "OZ": "https://flyasiana.com/",
    "CX": "https://www.cathaypacific.com/",
    "PR": "https://www.philippineairlines.com/",
    "TG": "https://www.thaiairways.com/",
    "VN": "https://www.vietnamairlines.com/",
    "GA": "https://www.garuda-indonesia.com/",
    "MH": "https://www.malaysiaairlines.com/",
    "BR": "https://www.evaair.com/",
    "CI": "https://www.china-airlines.com/",
    "MU": "https://www.ceair.com/",
    "CA": "https://www.airchina.com.cn/",
    "CZ": "https://www.csair.com/",
    "ZH": "https://www.shenzhenair.com/",
    "9W": "https://www.jetairways.com/",
    "6E": "https://www.goindigo.in/",
    "SG": "https://www.spicejet.com/",
    "UK": "https://www.airvistara.com/",
    "QH": "https://www.bambooairways.com/",
    "FZ": "https://www.flydubai.com/",
    "G9": "https://www.airarabia.com/",
    "MS": "https://www.egyptair.com/",
    "RJ": "https://www.rj.com/",
    "ME": "https://www.mea.com.lb/",
    "WY": "https://www.omanair.com/",
    "GF": "https://www.gulfair.com/",
    "KQ": "https://www.kenya-airways.com/",
    "SA": "https://www.flysaa.com/",
    "EI": "https://www.aerlingus.com/",
    "FR": "https://www.ryanair.com/",
    "U2": "https://www.easyjet.com/",
    "W6": "https://wizzair.com/",
    "VY": "https://www.vueling.com/",
    "PC": "https://www.flypgs.com/",
    "XQ": "https://www.sunexpress.com/",
}

# Mapping IATA → human-readable airline name (for the smart fallback search).
AIRLINE_NAMES = {
    "EK": "Emirates",
    "SQ": "Singapore Airlines",
    "BA": "British Airways",
    "QR": "Qatar Airways",
    "AI": "Air India",
    "AF": "Air France",
    "KL": "KLM",
    "LH": "Lufthansa",
    "TK": "Turkish Airlines",
    "ET": "Ethiopian Airlines",
    "EY": "Etihad Airways",
    "SV": "Saudia",
    "DL": "Delta Air Lines",
    "AA": "American Airlines",
    "UA": "United Airlines",
    "AC": "Air Canada",
    "QF": "Qantas",
    "CX": "Cathay Pacific",
    "JL": "Japan Airlines",
    "NH": "ANA",
    "KE": "Korean Air",
    "TG": "Thai Airways",
    "MH": "Malaysia Airlines",
    "GA": "Garuda Indonesia",
    "6E": "IndiGo",
    "FZ": "flydubai",
    "MS": "EgyptAir",
}


def google_flights_link(origin: str, destination: str, date: str | None = None) -> str:
    """Open Google Flights pre-filtered to a route."""
    base = "https://www.google.com/travel/flights"
    if date:
        return f"{base}?q={quote_plus(f'Flights from {origin} to {destination} on {date}')}"
    return f"{base}?q={quote_plus(f'Flights from {origin} to {destination}')}"


def _emirates_deeplink(origin: str, dest: str, date: str) -> str:
    return (
        "https://www.emirates.com/english/book/flights/booking/"
        f"?cabinClass=Y&travelType=O&numberOfPassengers=1"
        f"&origin={origin}&destination={dest}&departureDate={date}"
    )


def _ba_deeplink(origin: str, dest: str, date: str) -> str:
    return (
        "https://www.britishairways.com/travel/fx/public/en_gb"
        f"?eId=106003&from={origin}&to={dest}&depDate={date}"
    )


def _qatar_deeplink(origin: str, dest: str, date: str) -> str:
    return (
        "https://book.qatarairways.com/nsp/views/showBooking.action"
        f"?searchType=F&tripType=O&fromStation={origin}&toStation={dest}&departureDate={date}"
    )


def _lufthansa_deeplink(origin: str, dest: str, date: str) -> str:
    return (
        "https://www.lufthansa.com/de/en/flight-search"
        f"?travelers=1ADT&cabin=ECO&trip=oneway&flights={origin}-{dest},{date}"
    )


def _delta_deeplink(origin: str, dest: str, date: str) -> str:
    return (
        "https://www.delta.com/flight-search/search"
        f"?tripType=ONE_WAY&from={origin}&to={dest}&departureDate={date}&passenger_count=1"
    )


# Airlines with documented URL parameter support — we pass route + date.
AIRLINE_DEEPLINKS = {
    "EK": _emirates_deeplink,
    "BA": _ba_deeplink,
    "QR": _qatar_deeplink,
    "LH": _lufthansa_deeplink,
    "DL": _delta_deeplink,
}


def airline_booking_link(
    airline_code: str | None,
    fallback_origin: str = "",
    fallback_dest: str = "",
    airline_name: str | None = None,
    departure_date: str | None = None,
) -> str:
    """Best-available link for booking on the specific airline.

    Priority order:
      1. Deep link with route + date if the airline supports it (EK, BA, QR, LH, DL).
      2. The airline's homepage if we know it.
      3. A Google search for the airline's official booking page.
      4. A Google search for the route — last resort.

    Never falls back to Google Flights (use `google_flights_link()` for that
    explicitly when you want it as a separate option).
    """
    code = (airline_code or "").upper()

    # 1. Deep link with full route + date
    if code in AIRLINE_DEEPLINKS and fallback_origin and fallback_dest and departure_date:
        return AIRLINE_DEEPLINKS[code](fallback_origin, fallback_dest, departure_date)

    # 2. Homepage we know
    if code in AIRLINE_BOOKING:
        return AIRLINE_BOOKING[code]

    # 3. Search for the airline name
    if code in AIRLINE_NAMES:
        return f"https://www.google.com/search?q={quote_plus(AIRLINE_NAMES[code] + ' official site book flights')}&btnI"
    if airline_name and airline_name.strip():
        return f"https://www.google.com/search?q={quote_plus(airline_name.strip() + ' official site book flights')}&btnI"

    # 4. Last resort
    return f"https://www.google.com/search?q={quote_plus(f'flights from {fallback_origin} to {fallback_dest} airline website')}"


def uber_link(pickup: str | None = None, dropoff: str | None = None) -> str:
    """Open Uber's web booking page with pickup/dropoff if provided."""
    base = "https://m.uber.com/ul/"
    if not (pickup or dropoff):
        return base
    params = ["action=setPickup"]
    if pickup:
        params.append(f"pickup={quote_plus(pickup)}")
    if dropoff:
        params.append(f"dropoff[formatted_address]={quote_plus(dropoff)}")
    return base + "?" + "&".join(params)


def hotel_search_link(hotel_name: str, city: str = "") -> str:
    """Booking.com search for the hotel."""
    query = hotel_name + (" " + city if city else "")
    return f"https://www.booking.com/search.html?ss={quote_plus(query)}"


def hotel_manage_link(hotel_name: str) -> str:
    """Best-effort: search Google for 'manage booking {hotel}'."""
    return f"https://www.google.com/search?q={quote_plus('manage booking ' + hotel_name)}"


def google_calendar_link() -> str:
    """Direct user to Google Calendar import."""
    return "https://calendar.google.com/calendar/u/0/r/settings/export"
