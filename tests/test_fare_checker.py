import pytest
from pytest_mock import MockerFixture

from lib.config import Config
from lib.fare_checker import BOOKING_URL, FareChecker
from lib.flight import Flight
from lib.flight_retriever import FlightRetriever
from lib.notification_handler import NotificationHandler

# This needs to be accessed to be tested
# pylint: disable=protected-access


# Don't read the config file
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch.object(Config, "_read_config")


@pytest.fixture
def test_flight(mocker: MockerFixture) -> Flight:
    mocker.patch.object(Flight, "_get_flight_time")
    flight_info = {
        "departureAirport": {"name": None},
        "arrivalAirport": {"name": None},
        "departureTime": None,
    }
    return Flight(flight_info, "")


def test_check_flight_price_sends_notification_on_lower_fares(mocker: MockerFixture) -> None:
    flight_price = {"sign": "-", "amount": "10", "currencyCode": "USD"}
    mocker.patch.object(FareChecker, "_get_flight_price", return_value=flight_price)
    mock_lower_fare_notification = mocker.patch.object(NotificationHandler, "lower_fare")

    fare_checker = FareChecker(FlightRetriever(Config()))
    fare_checker.check_flight_price("test_flight")

    mock_lower_fare_notification.assert_called_once()


def test_check_flight_price_does_not_send_notifications_when_fares_are_higher(
    mocker: MockerFixture,
) -> None:
    flight_price = {"sign": "+", "amount": "10", "currencyCode": "USD"}
    mocker.patch.object(FareChecker, "_get_flight_price", return_value=flight_price)
    mock_lower_fare_notification = mocker.patch.object(NotificationHandler, "lower_fare")

    fare_checker = FareChecker(FlightRetriever(Config()))
    fare_checker.check_flight_price("test_flight")

    mock_lower_fare_notification.assert_not_called()


def test_get_flight_price_gets_flight_price_matching_current_flight(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    flights = [
        {"departureTime": "10:30"},
        {"departureTime": "11:30", "startingFromPriceDifference": "price"},
    ]
    mocker.patch.object(FareChecker, "_get_matching_flights", return_value=flights)

    test_flight.local_departure_time = "11:30"
    fare_checker = FareChecker(FlightRetriever(Config()))
    price = fare_checker._get_flight_price(test_flight)

    assert price == "price"


# This scenario should not happen because Southwest should always have a flight
# at the same time (as it is a scheduled flight)
def test_get_flight_price_returns_nothing_when_no_matching_flights_appear(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    flights = [{"departureTime": "10:30"}, {"departureTime": "11:30"}]
    mocker.patch.object(FareChecker, "_get_matching_flights", return_value=flights)

    test_flight.local_departure_time = "12:00"
    fare_checker = FareChecker(FlightRetriever(Config()))
    price = fare_checker._get_flight_price(test_flight)

    assert price is None


@pytest.mark.parametrize("bound", ["outbound", "inbound"])
def test_get_matching_flights_retrieves_correct_bound_page(
    mocker: MockerFixture, bound: str
) -> None:
    change_flight_page = {"_links": {"changeShopping": {"href": "test_link"}}}
    mocker.patch.object(FareChecker, "_get_change_flight_page", return_value=change_flight_page)

    search_query = {"outbound": {"isChangeBound": False}}
    search_query.update({bound: {"isChangeBound": True}})
    mocker.patch.object(FareChecker, "_get_search_query", return_value=search_query)

    response = {"changeShoppingPage": {"flights": {f"{bound}Page": {"cards": "test_cards"}}}}
    mocker.patch("lib.fare_checker.make_request", return_value=response)

    fare_checker = FareChecker(FlightRetriever(Config()))
    matching_flights = fare_checker._get_matching_flights(None)

    assert matching_flights == "test_cards"


def test_get_change_flight_page_retrieves_change_flight_page(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    reservation_info = {
        "viewReservationViewPage": {"_links": {"change": {"href": "test_link", "query": "query"}}}
    }
    expected_page = {"changeFlightPage": "test_page"}
    mock_make_request = mocker.patch(
        "lib.fare_checker.make_request", side_effect=[reservation_info, expected_page]
    )

    fare_checker = FareChecker(FlightRetriever(Config()))
    change_flight_page = fare_checker._get_change_flight_page(test_flight)

    assert change_flight_page == "test_page"

    call_args = mock_make_request.call_args[0]
    assert call_args[1] == BOOKING_URL + "test_link"
    assert call_args[3] == "query"


def test_get_search_query_returns_the_correct_query_for_one_way(test_flight: Flight) -> None:
    bound_one = {
        "originalDate": "1/1",
        "toAirportCode": "LAX",
        "fromAirportCode": "MIA",
        "timeDeparts": "12:00",
    }
    flight_page = {
        "boundSelections": [bound_one],
        "_links": {"changeShopping": {"body": [{"boundReference": "bound_1"}]}},
    }

    test_flight.local_departure_time = "12:00"
    fare_checker = FareChecker(FlightRetriever(Config()))
    search_query = fare_checker._get_search_query(flight_page, test_flight)

    assert len(search_query) == 1
    assert search_query.get("outbound") == {
        "boundReference": "bound_1",
        "date": "1/1",
        "destination-airport": "LAX",
        "origin-airport": "MIA",
        "isChangeBound": True,
    }


def test_get_search_query_returns_the_correct_query_for_round_trip(test_flight: Flight) -> None:
    bound_one = {
        "originalDate": "1/1",
        "toAirportCode": "LAX",
        "fromAirportCode": "MIA",
        "timeDeparts": "12:00",
    }
    bound_two = {
        "originalDate": "1/2",
        "toAirportCode": "MIA",
        "fromAirportCode": "LAX",
        "timeDeparts": "1:00",
    }
    flight_page = {
        "boundSelections": [bound_one, bound_two],
        "_links": {
            "changeShopping": {
                "body": [{"boundReference": "bound_1"}, {"boundReference": "bound_2"}]
            }
        },
    }

    test_flight.local_departure_time = "1:00"
    fare_checker = FareChecker(FlightRetriever(Config()))
    search_query = fare_checker._get_search_query(flight_page, test_flight)

    assert len(search_query) == 2
    assert search_query.get("outbound") == {
        "boundReference": "bound_1",
        "date": "1/1",
        "destination-airport": "LAX",
        "origin-airport": "MIA",
        "isChangeBound": False,
    }
    assert search_query.get("inbound") == {
        "boundReference": "bound_2",
        "date": "1/2",
        "destination-airport": "MIA",
        "origin-airport": "LAX",
        "isChangeBound": True,
    }