from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Union

from .checkin_scheduler import VIEW_RESERVATION_URL
from .flight import Flight
from .log import get_logger
from .utils import make_request, get_airport_code

if TYPE_CHECKING:  # pragma: no cover
    from .flight_retriever import FlightRetriever

# Type alias for JSON
JSON = Dict[str, Any]

BOOKING_URL = "mobile-air-booking/"
SHOPPING_URL = "mobile-air-shopping/v1/mobile-air-shopping/page/flights/products"

logger = get_logger(__name__)


class PassengerChecker:
    def __init__(self, flight_retriever: FlightRetriever) -> None:
        self.flight_retriever = flight_retriever
        self.headers = flight_retriever.checkin_scheduler.headers

    def check_passenger_availability(self, flight: Flight) -> None:
        """
        Check if there are at least 8 seats available for this flight.
        If not, send a notification as a reminder to book companion pass.
        """
        logger.debug("Checking for flight availability for 8 passengers...")
        flights_available = self._search_for_new_booking_on_same_flight(flight)
        matching_flight = self._find_matching_flight(flight, flights_available)
        if matching_flight["startingFromPrice"] is None:
            logger.debug("Less than 8 seats were found, sending notification.")
            self.flight_retriever.notification_handler.flight_unavailable(flight)
        else:
            logger.debug("At least 8 seats were found for this flight.")

        # The sign key will not exist if the price amount is 0
            
    def _find_matching_flight(self, flight: Flight, flights_available: JSON) -> JSON:
        for available_flight in flights_available:
            if available_flight["departureTime"] == flight.local_departure_time:
                matching_flight = available_flight
                return matching_flight

            
    def _search_for_new_booking_on_same_flight(self, flight: Flight) -> JSON:
        info = {"origination-airport": None, "destination-airport": None, "departure-date": None, "number-adult-passengers": "8", "currency": "USD"}
        info["origination-airport"] = get_airport_code(flight.departure_airport)
        info["destination-airport"] = get_airport_code(flight.destination_airport)
        departure_time = str(flight.departure_time)
        departure_date = departure_time.split(" ")[0]
        info["departure-date"] = departure_date
        site = SHOPPING_URL
        response = make_request("GET", site, self.headers, info, max_attempts=7)
        flights_available = response["flightShoppingPage"]["outboundPage"]["cards"]
        return flights_available