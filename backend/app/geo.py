"""Grobe Entfernungsschätzung über deutsche Postleitzahlen.

BEWUSST eine Näherung, keine Geodatenbank: Für jede PLZ-Leitregion (die ersten
ZWEI Ziffern, ~95 Stück) ist ein repräsentativer Ort mit Koordinaten hinterlegt.
Die Entfernung ist die Luftlinie zwischen zwei solchen Regionsmittelpunkten.

Konsequenzen, die man kennen muss:
- Genauigkeit grob ±30 km — gut genug für Moderationsangaben
  ("weitester Anreiseweg ca. 600 km"), NICHT für exakte Auswertungen.
- Gleiche Leitregion -> 0 km (z. B. Gröbenzell und Starnberg sind beide "82").
  Deshalb werden Entfernungen im Frontend als Spannen dargestellt.
- Nur deutsche PLZ (5 Ziffern). Alles andere liefert None.
"""

from __future__ import annotations

import math

# PLZ-Leitregion (2 Ziffern) -> (Breite, Länge, Name) eines repräsentativen Ortes.
# Nicht vergebene Leitregionen (00, 05, 11, 43, 62) fehlen bewusst.
_REGIONS: dict[str, tuple[float, float, str]] = {
    "01": (51.05, 13.74, "Dresden"),
    "02": (51.18, 14.43, "Bautzen/Görlitz"),
    "03": (51.76, 14.33, "Cottbus"),
    "04": (51.34, 12.37, "Leipzig"),
    "06": (51.48, 11.97, "Halle"),
    "07": (50.88, 12.08, "Gera/Jena"),
    "08": (50.72, 12.49, "Zwickau"),
    "09": (50.83, 12.92, "Chemnitz"),
    "10": (52.52, 13.40, "Berlin-Mitte"),
    "12": (52.47, 13.43, "Berlin-Süd"),
    "13": (52.57, 13.35, "Berlin-Nord"),
    "14": (52.40, 13.06, "Potsdam"),
    "15": (52.35, 14.55, "Frankfurt (Oder)"),
    "16": (52.83, 13.82, "Eberswalde"),
    "17": (53.56, 13.26, "Neubrandenburg"),
    "18": (54.09, 12.14, "Rostock"),
    "19": (53.63, 11.41, "Schwerin"),
    "20": (53.55, 9.99, "Hamburg"),
    "21": (53.46, 9.98, "Hamburg-Harburg"),
    "22": (53.60, 10.05, "Hamburg-Nord"),
    "23": (53.87, 10.69, "Lübeck"),
    "24": (54.32, 10.14, "Kiel"),
    "25": (53.93, 9.51, "Itzehoe"),
    "26": (53.14, 8.21, "Oldenburg"),
    "27": (53.54, 8.58, "Bremerhaven"),
    "28": (53.08, 8.81, "Bremen"),
    "29": (52.62, 10.08, "Celle"),
    "30": (52.37, 9.73, "Hannover"),
    "31": (52.15, 9.95, "Hildesheim"),
    "32": (52.29, 8.92, "Minden"),
    "33": (52.02, 8.53, "Bielefeld"),
    "34": (51.31, 9.49, "Kassel"),
    "35": (50.58, 8.68, "Gießen"),
    "36": (50.55, 9.68, "Fulda"),
    "37": (51.53, 9.93, "Göttingen"),
    "38": (52.27, 10.52, "Braunschweig"),
    "39": (52.13, 11.63, "Magdeburg"),
    "40": (51.22, 6.78, "Düsseldorf"),
    "41": (51.19, 6.44, "Mönchengladbach"),
    "42": (51.26, 7.18, "Wuppertal"),
    "44": (51.51, 7.47, "Dortmund"),
    "45": (51.46, 7.01, "Essen"),
    "46": (51.47, 6.85, "Oberhausen"),
    "47": (51.43, 6.76, "Duisburg"),
    "48": (51.96, 7.63, "Münster"),
    "49": (52.28, 8.05, "Osnabrück"),
    "50": (50.94, 6.96, "Köln"),
    "51": (51.03, 7.00, "Leverkusen"),
    "52": (50.78, 6.08, "Aachen"),
    "53": (50.73, 7.10, "Bonn"),
    "54": (49.75, 6.64, "Trier"),
    "55": (50.00, 8.27, "Mainz"),
    "56": (50.36, 7.59, "Koblenz"),
    "57": (50.87, 8.02, "Siegen"),
    "58": (51.36, 7.47, "Hagen"),
    "59": (51.68, 7.82, "Hamm"),
    "60": (50.11, 8.68, "Frankfurt am Main"),
    "61": (50.23, 8.62, "Bad Homburg"),
    "63": (50.10, 8.77, "Offenbach/Aschaffenburg"),
    "64": (49.87, 8.65, "Darmstadt"),
    "65": (50.08, 8.24, "Wiesbaden"),
    "66": (49.24, 6.99, "Saarbrücken"),
    "67": (49.48, 8.44, "Ludwigshafen"),
    "68": (49.49, 8.47, "Mannheim"),
    "69": (49.40, 8.69, "Heidelberg"),
    "70": (48.78, 9.18, "Stuttgart"),
    "71": (48.90, 9.19, "Ludwigsburg"),
    "72": (48.52, 9.06, "Tübingen"),
    "73": (48.70, 9.65, "Göppingen"),
    "74": (49.14, 9.22, "Heilbronn"),
    "75": (48.89, 8.70, "Pforzheim"),
    "76": (49.01, 8.40, "Karlsruhe"),
    "77": (48.47, 7.94, "Offenburg"),
    "78": (48.06, 8.46, "Villingen-Schwenningen"),
    "79": (47.99, 7.85, "Freiburg"),
    "80": (48.14, 11.58, "München"),
    "81": (48.11, 11.60, "München-Ost"),
    "82": (48.05, 11.30, "Starnberg/Fürstenfeldbruck"),
    "83": (47.86, 12.13, "Rosenheim"),
    "84": (48.54, 12.15, "Landshut"),
    "85": (48.55, 11.60, "Ingolstadt/Erding"),
    "86": (48.37, 10.90, "Augsburg"),
    "87": (47.73, 10.31, "Kempten"),
    "88": (47.78, 9.61, "Ravensburg"),
    "89": (48.40, 9.99, "Ulm"),
    "90": (49.45, 11.08, "Nürnberg"),
    "91": (49.50, 10.90, "Erlangen/Ansbach"),
    "92": (49.44, 11.86, "Amberg"),
    "93": (49.02, 12.10, "Regensburg"),
    "94": (48.57, 13.46, "Passau"),
    "95": (49.95, 11.58, "Bayreuth/Hof"),
    "96": (49.89, 10.89, "Bamberg"),
    "97": (49.79, 9.94, "Würzburg"),
    "98": (50.61, 10.69, "Suhl"),
    "99": (50.98, 11.03, "Erfurt"),
}

EARTH_RADIUS_KM = 6371.0


def region_of(postal_code: str | None) -> str | None:
    """Leitregion (2 Ziffern) einer deutschen PLZ; None wenn unbrauchbar."""
    digits = "".join(ch for ch in (postal_code or "") if ch.isdigit())
    if len(digits) != 5:
        return None
    return digits[:2] if digits[:2] in _REGIONS else None


def coords_of(postal_code: str | None) -> tuple[float, float] | None:
    region = region_of(postal_code)
    if region is None:
        return None
    lat, lon, _name = _REGIONS[region]
    return lat, lon


def region_name(region: str | None) -> str | None:
    """Repräsentativer Ort einer Leitregion – für die Anzeige ("Raum München")."""
    return _REGIONS[region][2] if region in _REGIONS else None


def region_codes() -> list[str]:
    """Alle bekannten Leitregionen (z. B. um Testdaten zu streuen)."""
    return list(_REGIONS)


def distance_km(a: str | None, b: str | None) -> float | None:
    """Luftlinie zwischen zwei PLZ-Leitregionen (Haversine), None wenn eine der
    beiden PLZ unbekannt ist. Gleiche Region -> 0.0."""
    pa, pb = coords_of(a), coords_of(b)
    if pa is None or pb is None:
        return None
    lat1, lon1 = math.radians(pa[0]), math.radians(pa[1])
    lat2, lon2 = math.radians(pb[0]), math.radians(pb[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
